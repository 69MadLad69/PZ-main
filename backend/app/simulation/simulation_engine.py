from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.forecasting.forecast_service import ForecastService
from backend.app.simulation.components.battery    import BatteryStorage
from backend.app.simulation.components.grid       import GridConnection
from backend.app.simulation.components.load_profile import LoadProfile
from backend.app.simulation.components.solar      import SolarPlant
from backend.app.simulation.ems_controller        import EMSController, StepResult
from backend.config.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s – %(message)s")
logger = logging.getLogger(__name__)


class SimulationEngine:

    def __init__(self, db: Session, strategy: str = "tariff_optimized"):
        self.db = db
        self.strategy = strategy
        self.run_id = str(uuid.uuid4())[:8]
        cfg = get_settings()
        self._tz = cfg.weather.timezone

        self.solar = SolarPlant()
        self.battery = BatteryStorage()
        self.grid = GridConnection()
        self.ems = EMSController(self.solar, self.battery, self.grid)
        self.load_profile = LoadProfile(db)

        self._forecast_svc: Optional[ForecastService] = None
        self._forecast_cache: Optional[pd.DataFrame]  = None
        self._forecast_start: Optional[pd.Timestamp]  = None

        logger.info("SimulationEngine run_id=%s  strategy=%s", self.run_id, strategy)


    def _get_forecast_service(self) -> Optional[ForecastService]:
        if self._forecast_svc is None:
            try:
                self._forecast_svc = ForecastService.from_saved(self.db)
                logger.info("ForecastService loaded (LR2 best model).")
            except Exception as exc:
                logger.warning("Could not load LR2 ForecastService: %s. Using baseline.", exc)
        return self._forecast_svc

    def _get_forecast_for_window(
        self, start_ts: pd.Timestamp, hours: int = 24
    ) -> pd.DataFrame:
        svc = self._get_forecast_service()
        if svc is None:
            return pd.DataFrame()
        try:
            fc = svc.forecast_period(start_ts, hours)
            return fc
        except Exception as exc:
            logger.warning("Forecast failed: %s", exc)
            return pd.DataFrame()

    def _load_weather(
        self, start: pd.Timestamp, end: pd.Timestamp
    ) -> pd.DataFrame:
        sql = text("""
            SELECT timestamp, temperature_c, solar_irradiance_wm2
            FROM weather_data
            WHERE timestamp >= :s AND timestamp < :e
            ORDER BY timestamp
        """)
        result = self.db.execute(sql, {"s": start, "e": end})
        rows = result.fetchall()
        if not rows:
            logger.warning("No weather data found for %s – %s", start.date(), end.date())
            return pd.DataFrame()
        df = pd.DataFrame(rows, columns=["timestamp", "temperature_c", "solar_irradiance_wm2"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert(self._tz)
        return df.set_index("timestamp")

    def run(
        self,
        start_date:  Optional[str] = None,
        days:        int           = 7,
        save_to_db:  bool          = True,
    ) -> pd.DataFrame:
        cfg = get_settings()
        tz  = self._tz

        if start_date is None:
            start_date = f"{cfg.generation.year}-07-01"
        start_ts = pd.Timestamp(start_date, tz=tz)
        end_ts   = start_ts + pd.Timedelta(hours=days * 24)
        hours_idx = pd.date_range(start_ts, end_ts - pd.Timedelta(hours=1), freq="h")

        logger.info("Simulation: %s → %s  (%d steps)  run_id=%s",
                    start_ts.date(), end_ts.date(), len(hours_idx), self.run_id)

        weather = self._load_weather(start_ts, end_ts)

        actual_load = self.load_profile.get_actual_hourly(start_ts, end_ts)

        self.ems.reset()

        results: List[Dict] = []
        forecast_cache: Optional[pd.DataFrame] = None
        last_fc_update: Optional[pd.Timestamp] = None

        for ts in hours_idx:
            if ts in weather.index:
                irr = float(weather.loc[ts, "solar_irradiance_wm2"])
                temp = float(weather.loc[ts, "temperature_c"])
            else:
                m = ts.month - 1
                irr = cfg.weather.monthly_avg_irradiance_wm2[m] * 0.6
                temp = cfg.weather.monthly_avg_temp_c[m]

            if ts in actual_load.index:
                load = float(actual_load.loc[ts])
            else:
                load = self.load_profile.get_baseline(ts)

            if last_fc_update is None or (ts - last_fc_update).total_seconds() >= 3600 * 24:
                forecast_cache = self._get_forecast_for_window(ts, hours=24)
                last_fc_update = ts

            fc_kwh = 0.0
            fc_next_6h: List[float] = []
            if forecast_cache is not None and not forecast_cache.empty:
                if ts in forecast_cache.index:
                    fc_kwh = float(forecast_cache.loc[ts, "predicted_kwh"])
                future_idx = [ts + pd.Timedelta(hours=h) for h in range(1, 7)]
                fc_next_6h = [
                    float(forecast_cache.loc[fts, "predicted_kwh"])
                    if fts in forecast_cache.index else load
                    for fts in future_idx
                ]

            step = self.ems.step(
                timestamp = ts,
                irradiance_wm2 = irr,
                temperature_c = temp,
                load_kwh = load,
                forecast_kwh = fc_kwh,
                forecast_next_6h = fc_next_6h,
            )

            results.append({
                "run_id": self.run_id,
                "timestamp": ts,
                "solar_kwh": step.solar_kwh,
                "load_kwh": step.load_kwh,
                "forecast_kwh": step.forecast_kwh,
                "soc_pct": step.soc_pct,
                "soc_kwh": step.soc_kwh,
                "charge_kwh": step.charge_kwh,
                "discharge_kwh": step.discharge_kwh,
                "import_kwh": step.import_kwh,
                "export_kwh": step.export_kwh,
                "tariff_zone": step.tariff_zone,
                "rate_uah_kwh": step.rate_uah_kwh,
                "cost_uah": step.cost_uah,
                "direct_solar_kwh": step.direct_solar_kwh,
                "decision": step.decision,
                "temperature_c": temp,
                "irradiance_wm2": irr,
            })

        df = pd.DataFrame(results)
        df = df.set_index("timestamp")

        if save_to_db:
            self._save_results(df, start_ts, end_ts)

        logger.info(
            "Simulation done. Total load=%.1f kWh  solar=%.1f kWh  "
            "import=%.1f kWh  cost=%.0f UAH",
            df["load_kwh"].sum(), df["solar_kwh"].sum(),
            df["import_kwh"].sum(), df["cost_uah"].sum(),
        )
        return df

    def _save_results(
        self,
        df: pd.DataFrame,
        start_ts: pd.Timestamp,
        end_ts:   pd.Timestamp,
    ) -> None:
        try:
            self.db.execute(text("""
                INSERT INTO simulation_runs
                    (run_id, started_at, start_date, end_date, strategy,
                     initial_soc_pct, status)
                VALUES (:rid, :now, :sd, :ed, :strat, :soc, 'running')
                ON CONFLICT (run_id) DO NOTHING
            """), {
                "rid": self.run_id,
                "now": datetime.now(timezone.utc),
                "sd": start_ts,
                "ed": end_ts,
                "strat": self.strategy,
                "soc": get_settings().battery.initial_soc_pct,
            })

            rows = [
                {
                    "run_id": self.run_id,
                    "timestamp": idx,
                    "solar_kwh": row["solar_kwh"],
                    "load_kwh": row["load_kwh"],
                    "forecast_kwh": row["forecast_kwh"],
                    "soc_pct": row["soc_pct"],
                    "soc_kwh": row["soc_kwh"],
                    "charge_kwh": row["charge_kwh"],
                    "discharge_kwh": row["discharge_kwh"],
                    "import_kwh": row["import_kwh"],
                    "export_kwh": row["export_kwh"],
                    "tariff_zone": row["tariff_zone"],
                    "rate_uah_kwh": row["rate_uah_kwh"],
                    "cost_uah": row["cost_uah"],
                    "strategy": self.strategy,
                }
                for idx, row in df.iterrows()
            ]
            self.db.execute(text("""
                INSERT INTO simulation_results
                    (run_id, timestamp, solar_kwh, load_kwh, forecast_kwh,
                     soc_pct, soc_kwh, charge_kwh, discharge_kwh,
                     import_kwh, export_kwh, tariff_zone, rate_uah_kwh,
                     cost_uah, strategy)
                VALUES
                    (:run_id, :timestamp, :solar_kwh, :load_kwh, :forecast_kwh,
                     :soc_pct, :soc_kwh, :charge_kwh, :discharge_kwh,
                     :import_kwh, :export_kwh, :tariff_zone, :rate_uah_kwh,
                     :cost_uah, :strategy)
            """), rows)

            total = df["cost_uah"].sum()
            baseline_cost = (df["load_kwh"].sum() *
                             df["rate_uah_kwh"].mean())
            self.db.execute(text("""
                UPDATE simulation_runs SET
                    total_consumption_kwh = :tc,
                    total_generation_kwh  = :tg,
                    total_import_kwh      = :ti,
                    total_export_kwh      = :te,
                    total_cost_uah        = :tc2,
                    baseline_cost_uah     = :bc,
                    savings_uah           = :sv,
                    status                = 'completed'
                WHERE run_id = :rid
            """), {
                "tc": df["load_kwh"].sum(),
                "tg": df["solar_kwh"].sum(),
                "ti": df["import_kwh"].sum(),
                "te": df["export_kwh"].sum(),
                "tc2": total,
                "bc": baseline_cost,
                "sv": baseline_cost - total,
                "rid": self.run_id,
            })
            self.db.commit()
            logger.info("Results saved to DB  run_id=%s", self.run_id)
        except Exception as exc:
            logger.error("Failed to save to DB: %s", exc)
            self.db.rollback()
