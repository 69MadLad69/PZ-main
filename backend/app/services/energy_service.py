"""
Service layer for EMS business logic.
Services orchestrate repositories and are the interface for LabWork 2-4.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy.orm import Session

from backend.app.repositories.repositories import (
    BatteryRepository,
    BaselineRepository,
    MeasurementRepository,
    MeterRepository,
    MetricsRepository,
    ObjectRepository,
    SolarRepository,
    TariffRepository,
    WeatherRepository,
)
from backend.config.config import get_settings

settings = get_settings()
CO2_FACTOR_KG_KWH = 0.302  # Ukrainian grid emission factor 2024


class EnergyService:
    """
    Core energy analytics service.
    Consumed by: LabWork 1 (reporting), LabWork 2 (forecasting features),
                 LabWork 3 (EMS simulation), LabWork 4 (REST endpoints).
    """

    def __init__(self, db: Session):
        self.db = db
        self.obj_repo = ObjectRepository(db)
        self.meter_repo = MeterRepository(db)
        self.meas_repo = MeasurementRepository(db)
        self.weather_repo = WeatherRepository(db)
        self.tariff_repo = TariffRepository(db)
        self.solar_repo = SolarRepository(db)
        self.battery_repo = BatteryRepository(db)
        self.baseline_repo = BaselineRepository(db)
        self.metrics_repo = MetricsRepository(db)

    # ── Consumption ─────────────────────────────────────────────────────────

    def get_hourly_consumption(
        self, object_id: int, start: datetime, end: datetime
    ) -> pd.DataFrame:
        """Return hourly kWh for the main (level-1) meter."""
        main = self.meter_repo.get_main_meter(object_id)
        if main is None:
            return pd.DataFrame()
        return self.meas_repo.to_dataframe(main.id, start, end)

    def get_daily_consumption(
        self, object_id: int, start: datetime, end: datetime
    ) -> pd.DataFrame:
        main = self.meter_repo.get_main_meter(object_id)
        if main is None:
            return pd.DataFrame()
        return self.meas_repo.daily_sum(main.id, start, end)

    def get_monthly_consumption(self, object_id: int, year: int) -> pd.DataFrame:
        main = self.meter_repo.get_main_meter(object_id)
        if main is None:
            return pd.DataFrame()
        return self.meas_repo.monthly_sum(main.id, year)

    def get_zone_consumption(
        self, object_id: int, start: datetime, end: datetime
    ) -> pd.DataFrame:
        """Level-2: per-zone consumption breakdown."""
        meters = self.meter_repo.get_by_level(2)
        frames = []
        for m in meters:
            df = self.meas_repo.to_dataframe(m.id, start, end)
            if not df.empty:
                df.columns = [f"{m.name}_{c}" for c in df.columns]
                frames.append(df)
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, axis=1)

    # ── Tariff ──────────────────────────────────────────────────────────────

    def calculate_cost(
        self, object_id: int, start: datetime, end: datetime
    ) -> Dict[str, float]:
        """Return day/night/total electricity cost in UAH."""
        df = self.get_hourly_consumption(object_id, start, end)
        if df.empty:
            return {"day": 0.0, "night": 0.0, "total": 0.0}

        tariff = self.tariff_repo.get_active()
        day_rate = next((z.rate_uah_kwh for z in tariff if z.zone_type == "day"), 6.9)
        night_rate = next((z.rate_uah_kwh for z in tariff if z.zone_type == "night"), 5.6)

        df = df.copy()
        df["hour"] = pd.to_datetime(df.index).hour
        df["is_day"] = df["hour"].between(7, 22)
        day_kwh = df.loc[df["is_day"], "energy_kwh"].sum()
        night_kwh = df.loc[~df["is_day"], "energy_kwh"].sum()

        return {
            "day_kwh": round(day_kwh, 2),
            "night_kwh": round(night_kwh, 2),
            "day_uah": round(day_kwh * day_rate, 2),
            "night_uah": round(night_kwh * night_rate, 2),
            "total_uah": round(day_kwh * day_rate + night_kwh * night_rate, 2),
        }

    # ── Anomaly Detection ────────────────────────────────────────────────────

    def detect_anomalies(
        self, object_id: int, start: datetime, end: datetime
    ) -> pd.DataFrame:
        """
        Flag hourly readings that deviate >20% from hourly baseline.
        Returns DataFrame of anomalous rows with deviation_pct column.
        """
        df = self.get_hourly_consumption(object_id, start, end)
        if df.empty:
            return pd.DataFrame()

        threshold = settings.analytics.anomaly_threshold_pct
        anomalies = []

        for ts, row in df.iterrows():
            month = ts.month
            hour = ts.hour
            day_type = "weekend" if ts.dayofweek >= 5 else "weekday"
            baseline_rows = self.baseline_repo.get_profile(object_id, month, day_type)
            baseline_map = {b.hour_of_day: b.expected_kwh for b in baseline_rows}
            expected = baseline_map.get(hour, 0)
            if expected > 0:
                deviation = abs(row["energy_kwh"] - expected) / expected
                if deviation > threshold:
                    anomalies.append(
                        {
                            "timestamp": ts,
                            "actual_kwh": row["energy_kwh"],
                            "expected_kwh": expected,
                            "deviation_pct": round(deviation * 100, 1),
                        }
                    )

        return pd.DataFrame(anomalies)

    # ── Specific Consumption ─────────────────────────────────────────────────

    def specific_consumption_kwh_m2(
        self, object_id: int, start: datetime, end: datetime
    ) -> float:
        obj = self.obj_repo.get_or_raise(object_id)
        df = self.get_daily_consumption(object_id, start, end)
        if df.empty:
            return 0.0
        total_kwh = df["total_kwh"].sum()
        return round(total_kwh / obj.area_m2, 3)

    # ── Solar & Battery ──────────────────────────────────────────────────────

    def get_solar_summary(
        self, start: datetime, end: datetime
    ) -> Dict[str, float]:
        rows = self.solar_repo.get_range(start, end)
        if not rows:
            return {}
        total_kwh = sum(r.energy_kwh for r in rows)
        peak_kw = max(r.power_kw for r in rows)
        return {
            "total_generation_kwh": round(total_kwh, 2),
            "peak_power_kw": round(peak_kw, 2),
            "hours_generating": sum(1 for r in rows if r.power_kw > 0.1),
        }

    # ── CO₂ Estimation ───────────────────────────────────────────────────────

    def co2_saved_by_solar(self, start: datetime, end: datetime) -> float:
        summary = self.get_solar_summary(start, end)
        return round(summary.get("total_generation_kwh", 0) * CO2_FACTOR_KG_KWH, 2)


class TariffService:
    """
    Tariff classification and cost computation.
    Re-used by LabWork 3 (dispatch optimization) and LabWork 4 (API).
    """

    def __init__(self, db: Session):
        self.tariff_repo = TariffRepository(db)

    def classify_hour(self, hour: int) -> str:
        """Returns 'day' or 'night' based on active tariff zones."""
        zones = self.tariff_repo.get_active()
        for zone in zones:
            s, e = zone.start_hour, zone.end_hour
            if s < e:
                if s <= hour < e:
                    return zone.zone_type
            else:
                if hour >= s or hour < e:
                    return zone.zone_type
        return "day"

    def rate_for_hour(self, hour: int) -> float:
        return self.tariff_repo.get_rate_for_hour(hour)

    def annual_cost_estimate(self, annual_kwh: float) -> float:
        """Rough estimate using typical day/night split (16h day, 8h night)."""
        day_share = 16 / 24
        night_share = 8 / 24
        day_rate = 6.9
        night_rate = 5.6
        zones = self.tariff_repo.get_active()
        for z in zones:
            if z.zone_type == "day":
                day_rate = z.rate_uah_kwh
            elif z.zone_type == "night":
                night_rate = z.rate_uah_kwh
        return round(
            annual_kwh * (day_share * day_rate + night_share * night_rate), 2
        )
