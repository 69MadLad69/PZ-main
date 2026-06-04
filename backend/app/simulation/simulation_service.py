from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from backend.app.simulation.economics        import EconomicAnalyzer, EconomicMetrics, EnergyMetrics
from backend.app.simulation.simulation_engine import SimulationEngine
from backend.config.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s – %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class SimulationResult:
    run_id: str
    df: pd.DataFrame
    energy: EnergyMetrics
    economics: EconomicMetrics


class SimulationService:

    def __init__(self, db: Session):
        self.db = db

    def run(
        self,
        start_date: Optional[str] = None,
        days: int = 7,
        strategy: str = "tariff_optimized",
        save_to_db: bool = True,
    ) -> SimulationResult:
        engine = SimulationEngine(self.db, strategy=strategy)
        df = engine.run(start_date=start_date, days=days, save_to_db=save_to_db)

        analyzer = EconomicAnalyzer()
        energy = analyzer.compute_energy_metrics(df)
        economics = analyzer.compute_economic_metrics(df)

        logger.info(
            "SimulationService done: savings=%.0f UAH  payback=%.1f yr  NPV=%.0f UAH",
            economics.annual_savings_uah,
            economics.simple_payback_years,
            economics.npv_uah,
        )
        return SimulationResult(
            run_id = engine.run_id,
            df = df,
            energy = energy,
            economics = economics,
        )

    def get_latest_result(self) -> Optional[pd.DataFrame]:
        from sqlalchemy import text
        sql = text("""
            SELECT r.run_id, r.started_at, r.total_cost_uah, r.savings_uah,
                   r.total_consumption_kwh, r.total_generation_kwh
            FROM simulation_runs r
            WHERE r.status = 'completed'
            ORDER BY r.started_at DESC
            LIMIT 1
        """)
        try:
            result = self.db.execute(sql)
            row = result.fetchone()
            if row:
                return dict(row._mapping)
        except Exception as exc:
            logger.warning("Could not fetch latest run: %s", exc)
        return None
