from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, Index,
    Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.sql import func

from backend.app.database import Base


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(50), nullable=False, unique=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    start_date = Column(DateTime(timezone=True))
    end_date = Column(DateTime(timezone=True))
    strategy = Column(String(50), default="tariff_optimized")
    initial_soc_pct = Column(Float, default=50.0)
    total_consumption_kwh = Column(Float)
    total_generation_kwh  = Column(Float)
    total_import_kwh = Column(Float)
    total_export_kwh = Column(Float)
    total_cost_uah = Column(Float)
    baseline_cost_uah = Column(Float)
    savings_uah = Column(Float)
    self_sufficiency_pct = Column(Float)
    self_consumption_pct = Column(Float)
    battery_cycles = Column(Float)
    npv_uah = Column(Float)
    irr_pct = Column(Float)
    simple_payback_years  = Column(Float)
    status = Column(String(20), default="pending")
    notes = Column(Text)

    __table_args__ = (
        Index("ix_sim_runs_started", "started_at"),
        Index("ix_sim_runs_status",  "status"),
    )

    def __repr__(self) -> str:
        return f"<SimulationRun {self.run_id} {self.status}>"


class SimulationResult(Base):
    __tablename__ = "simulation_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(50), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    solar_kwh = Column(Float, default=0.0)
    load_kwh = Column(Float, nullable=False)
    forecast_kwh    = Column(Float, default=0.0)
    soc_pct = Column(Float, nullable=False)
    soc_kwh = Column(Float, nullable=False)
    charge_kwh = Column(Float, default=0.0)
    discharge_kwh   = Column(Float, default=0.0)
    import_kwh = Column(Float, default=0.0)
    export_kwh = Column(Float, default=0.0)
    tariff_zone = Column(String(10))
    rate_uah_kwh    = Column(Float)
    cost_uah = Column(Float, default=0.0)
    strategy = Column(String(50))
    temperature_c   = Column(Float)
    irradiance_wm2  = Column(Float)

    __table_args__ = (
        UniqueConstraint("run_id", "timestamp", name="uq_simres_run_ts"),
        Index("ix_simres_run_ts",  "run_id", "timestamp"),
        Index("ix_simres_ts",      "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<SimResult {self.run_id} {self.timestamp} soc={self.soc_pct}%>"
