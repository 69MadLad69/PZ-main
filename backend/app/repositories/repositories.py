from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

import pandas as pd
from sqlalchemy import and_, func, select, text
from sqlalchemy.orm import Session

from backend.app.models.models import (
    BaselineConsumption,
    BatteryState,
    EnergyEfficiencyMetric,
    EnergyObject,
    Measurement,
    Meter,
    SolarGeneration,
    TariffZone,
    WeatherData,
)
from backend.app.repositories.base import BaseRepository

class ObjectRepository(BaseRepository[EnergyObject]):
    def __init__(self, db: Session):
        super().__init__(EnergyObject, db)

    def get_by_name(self, name: str) -> Optional[EnergyObject]:
        return self.first_by(name=name)

class MeterRepository(BaseRepository[Meter]):
    def __init__(self, db: Session):
        super().__init__(Meter, db)

    def get_by_object(self, object_id: int) -> List[Meter]:
        return self.filter_by(object_id=object_id)

    def get_by_level(self, level: int) -> List[Meter]:
        return self.filter_by(level=level)

    def get_main_meter(self, object_id: int) -> Optional[Meter]:
        stmt = select(Meter).where(
            and_(Meter.object_id == object_id, Meter.type == "main")
        ).limit(1)
        return self.db.scalars(stmt).first()

class MeasurementRepository(BaseRepository[Measurement]):
    def __init__(self, db: Session):
        super().__init__(Measurement, db)

    def get_range(
        self,
        meter_id: int,
        start: datetime,
        end: datetime,
    ) -> List[Measurement]:
        stmt = (
            select(Measurement)
            .where(
                and_(
                    Measurement.meter_id == meter_id,
                    Measurement.timestamp >= start,
                    Measurement.timestamp < end,
                )
            )
            .order_by(Measurement.timestamp)
        )
        return list(self.db.scalars(stmt))

    def to_dataframe(
        self,
        meter_id: int,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        rows = self.get_range(meter_id, start, end)
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(
            [
                {
                    "timestamp": r.timestamp,
                    "active_power_kw": r.active_power_kw,
                    "reactive_power_kvar": r.reactive_power_kvar,
                    "energy_kwh": r.energy_kwh,
                    "power_factor": r.power_factor,
                }
                for r in rows
            ]
        ).set_index("timestamp")

    def daily_sum(self, meter_id: int, start: datetime, end: datetime) -> pd.DataFrame:
        stmt = text("""
            SELECT
                DATE(timestamp AT TIME ZONE 'Europe/Kyiv') AS day,
                SUM(energy_kwh) AS total_kwh,
                MAX(active_power_kw) AS peak_kw,
                AVG(active_power_kw) AS avg_kw
            FROM measurements
            WHERE meter_id = :mid
              AND timestamp >= :start
              AND timestamp < :end
            GROUP BY day
            ORDER BY day
        """)
        result = self.db.execute(stmt, {"mid": meter_id, "start": start, "end": end})
        return pd.DataFrame(result.fetchall(), columns=result.keys())

    def monthly_sum(self, meter_id: int, year: int) -> pd.DataFrame:
        stmt = text("""
            SELECT
                EXTRACT(MONTH FROM timestamp AT TIME ZONE 'Europe/Kyiv') AS month,
                SUM(energy_kwh) AS total_kwh,
                MAX(active_power_kw) AS peak_kw,
                AVG(active_power_kw) AS avg_kw,
                COUNT(*) AS readings
            FROM measurements
            WHERE meter_id = :mid
              AND EXTRACT(YEAR FROM timestamp AT TIME ZONE 'Europe/Kyiv') = :year
            GROUP BY month
            ORDER BY month
        """)
        result = self.db.execute(stmt, {"mid": meter_id, "year": year})
        return pd.DataFrame(result.fetchall(), columns=result.keys())

    def last_n_hours(self, meter_id: int, n: int = 24) -> List[Measurement]:
        stmt = (
            select(Measurement)
            .where(Measurement.meter_id == meter_id)
            .order_by(Measurement.timestamp.desc())
            .limit(n)
        )
        return list(self.db.scalars(stmt))

class WeatherRepository(BaseRepository[WeatherData]):
    def __init__(self, db: Session):
        super().__init__(WeatherData, db)

    def get_range(self, start: datetime, end: datetime) -> List[WeatherData]:
        stmt = (
            select(WeatherData)
            .where(and_(WeatherData.timestamp >= start, WeatherData.timestamp < end))
            .order_by(WeatherData.timestamp)
        )
        return list(self.db.scalars(stmt))

    def to_dataframe(self, start: datetime, end: datetime) -> pd.DataFrame:
        rows = self.get_range(start, end)
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(
            [
                {
                    "timestamp": r.timestamp,
                    "temperature_c": r.temperature_c,
                    "solar_irradiance_wm2": r.solar_irradiance_wm2,
                    "humidity_pct": r.humidity_pct,
                    "wind_speed_ms": r.wind_speed_ms,
                    "hdd": r.hdd,
                    "cdd": r.cdd,
                }
                for r in rows
            ]
        ).set_index("timestamp")

class TariffRepository(BaseRepository[TariffZone]):
    def __init__(self, db: Session):
        super().__init__(TariffZone, db)

    def get_active(self) -> List[TariffZone]:
        return self.filter_by(is_active=True)

    def get_rate_for_hour(self, hour: int) -> float:
        """Return UAH/kWh rate for the given hour (0–23)."""
        from datetime import time
        t = time(hour, 0, 0)
        zones = self.get_active()
        for zone in zones:
            s, e = zone.start_time, zone.end_time
            if s < e:
                if s <= t < e:
                    return zone.rate_uah_kwh
            else:
                if t >= s or t < e:
                    return zone.rate_uah_kwh
        return 6.9

class SolarRepository(BaseRepository[SolarGeneration]):
    def __init__(self, db: Session):
        super().__init__(SolarGeneration, db)

    def get_range(self, start: datetime, end: datetime) -> List[SolarGeneration]:
        stmt = (
            select(SolarGeneration)
            .where(and_(SolarGeneration.timestamp >= start, SolarGeneration.timestamp < end))
            .order_by(SolarGeneration.timestamp)
        )
        return list(self.db.scalars(stmt))

class BatteryRepository(BaseRepository[BatteryState]):
    def __init__(self, db: Session):
        super().__init__(BatteryState, db)

    def latest(self) -> Optional[BatteryState]:
        stmt = select(BatteryState).order_by(BatteryState.timestamp.desc()).limit(1)
        return self.db.scalars(stmt).first()

    def get_range(self, start: datetime, end: datetime) -> List[BatteryState]:
        stmt = (
            select(BatteryState)
            .where(and_(BatteryState.timestamp >= start, BatteryState.timestamp < end))
            .order_by(BatteryState.timestamp)
        )
        return list(self.db.scalars(stmt))

class BaselineRepository(BaseRepository[BaselineConsumption]):
    def __init__(self, db: Session):
        super().__init__(BaselineConsumption, db)

    def get_profile(
        self, object_id: int, month: int, day_type: str
    ) -> List[BaselineConsumption]:
        stmt = (
            select(BaselineConsumption)
            .where(
                and_(
                    BaselineConsumption.object_id == object_id,
                    BaselineConsumption.month == month,
                    BaselineConsumption.day_type == day_type,
                )
            )
            .order_by(BaselineConsumption.hour_of_day)
        )
        return list(self.db.scalars(stmt))

class MetricsRepository(BaseRepository[EnergyEfficiencyMetric]):
    def __init__(self, db: Session):
        super().__init__(EnergyEfficiencyMetric, db)

    def get_range(
        self, object_id: int, start: datetime, end: datetime
    ) -> List[EnergyEfficiencyMetric]:
        stmt = (
            select(EnergyEfficiencyMetric)
            .where(
                and_(
                    EnergyEfficiencyMetric.object_id == object_id,
                    EnergyEfficiencyMetric.date >= start,
                    EnergyEfficiencyMetric.date < end,
                )
            )
            .order_by(EnergyEfficiencyMetric.date)
        )
        return list(self.db.scalars(stmt))
