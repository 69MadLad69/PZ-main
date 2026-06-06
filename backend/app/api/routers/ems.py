from __future__ import annotations
import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.api.schemas import (
    EnergyMetricsSchema, EconomicMetricsSchema, EnergyFlowSchema,
)
from backend.config.config import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/ems/status", summary="Статус останнього прогону симуляції (ЛР3)")
async def ems_status(db: Session = Depends(get_db)):
    sql = text("""
        SELECT run_id, started_at, strategy, status,
               total_consumption_kwh, total_generation_kwh,
               total_cost_uah, savings_uah
        FROM simulation_runs
        ORDER BY started_at DESC LIMIT 1
    """)
    try:
        row = db.execute(sql).fetchone()
    except Exception:
        row = None
    if row is None:
        return {"status": "no_runs", "message": "Симуляція ще не запускалась. "
                "Виконайте: python -m backend.scripts.run_simulation"}
    return dict(row._mapping)


@router.get("/ems/simulation", summary="Погодинні результати останньої симуляції (ЛР3)")
async def ems_simulation(
    run_id: Optional[str] = Query(default=None),
    page: int  = Query(default=1, ge=1),
    page_size: int = Query(default=168, ge=1, le=744),
    db: Session = Depends(get_db),
):
    if run_id is None:
        rid_sql = text("SELECT run_id FROM simulation_runs ORDER BY started_at DESC LIMIT 1")
        try:
            row = db.execute(rid_sql).fetchone()
            run_id = row[0] if row else None
        except Exception:
            run_id = None
    if run_id is None:
        raise HTTPException(404, "Результати симуляції не знайдено")

    sql = text("""
        SELECT timestamp, solar_kwh, load_kwh, soc_pct, soc_kwh,
               charge_kwh, discharge_kwh, import_kwh, export_kwh,
               tariff_zone, rate_uah_kwh, cost_uah
        FROM simulation_results
        WHERE run_id = :rid
        ORDER BY timestamp
        LIMIT :lim OFFSET :off
    """)
    rows = db.execute(sql, {"rid": run_id,
                             "lim": page_size,
                             "off": (page-1)*page_size}).fetchall()
    total_sql = text("SELECT COUNT(*) FROM simulation_results WHERE run_id=:rid")
    total = db.execute(total_sql, {"rid": run_id}).scalar() or 0
    return {
        "run_id": run_id,
        "data": [dict(r._mapping) for r in rows],
        "meta": {"total": total, "page": page, "page_size": page_size,
                 "pages": (total + page_size - 1) // page_size},
    }


@router.get("/ems/metrics", summary="Енергетичні KPI симуляції (ЛР3)")
async def ems_metrics(
    run_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    import pandas as pd
    from backend.app.simulation.economics import EconomicAnalyzer

    if run_id is None:
        rid_sql = text("SELECT run_id FROM simulation_runs ORDER BY started_at DESC LIMIT 1")
        try:
            row = db.execute(rid_sql).fetchone(); run_id = row[0] if row else None
        except Exception: run_id = None
    if run_id is None:
        raise HTTPException(404, "Симуляцію не знайдено")

    sql = text("""
        SELECT solar_kwh, load_kwh, import_kwh, export_kwh,
               charge_kwh, discharge_kwh, direct_solar_kwh
        FROM simulation_results WHERE run_id = :rid
    """)
    try:
        rows = db.execute(sql, {"rid": run_id}).fetchall()
    except Exception as exc:
        raise HTTPException(500, str(exc))
    if not rows:
        raise HTTPException(404, f"Дані симуляції {run_id} не знайдено")

    df = pd.DataFrame([dict(r._mapping) for r in rows])
    e  = EconomicAnalyzer.compute_energy_metrics(df)
    return e.__dict__


@router.get("/ems/economics", summary="Економічний аналіз (NPV, IRR, Payback) (ЛР3)")
async def ems_economics(
    run_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    import pandas as pd
    from backend.app.simulation.economics import EconomicAnalyzer

    if run_id is None:
        rid_sql = text("SELECT run_id FROM simulation_runs ORDER BY started_at DESC LIMIT 1")
        try:
            row = db.execute(rid_sql).fetchone(); run_id = row[0] if row else None
        except Exception: run_id = None
    if run_id is None:
        raise HTTPException(404, "Симуляцію не знайдено")

    sql = text("""
        SELECT timestamp, solar_kwh, load_kwh, import_kwh, export_kwh,
            charge_kwh, discharge_kwh, direct_solar_kwh,
            rate_uah_kwh, cost_uah
        FROM simulation_results WHERE run_id = :rid
        ORDER BY timestamp
    """)
    try:
        rows = db.execute(sql, {"rid": run_id}).fetchall()
    except Exception as exc:
        raise HTTPException(500, str(exc))
    df = pd.DataFrame([dict(r._mapping) for r in rows])
    from backend.config.config import get_settings
    cfg = get_settings()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True) \
                        .dt.tz_convert(cfg.weather.timezone)
    df = df.set_index("timestamp")
    analyzer = EconomicAnalyzer()
    eco = analyzer.compute_economic_metrics(df)
    return eco.__dict__


@router.get("/ems/energy-flow", response_model=EnergyFlowSchema,
            summary="Sankey diagram: потоки енергії (ЛР3)")
async def energy_flow(
    run_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    import pandas as pd

    if run_id is None:
        try:
            row = db.execute(text("SELECT run_id FROM simulation_runs ORDER BY started_at DESC LIMIT 1")).fetchone()
            run_id = row[0] if row else None
        except Exception: run_id = None
    if run_id is None:
        raise HTTPException(404, "Симуляцію не знайдено")

    sql = text("""
        SELECT solar_kwh, load_kwh, charge_kwh, discharge_kwh,
               import_kwh, export_kwh
        FROM simulation_results WHERE run_id = :rid
    """)
    rows = db.execute(sql, {"rid": run_id}).fetchall()
    df = pd.DataFrame([dict(r._mapping) for r in rows])

    total_solar = float(df["solar_kwh"].sum())
    direct_solar = float(df.get("direct_solar_kwh", df["solar_kwh"]).sum())
    to_battery = float(df["charge_kwh"].sum())
    to_grid = float(df["export_kwh"].sum())
    bat_to_load = float(df["discharge_kwh"].sum())
    grid_to_load = float(df["import_kwh"].sum())
    grid_to_bat = max(0.0, to_battery - (total_solar - to_grid - direct_solar))

    return EnergyFlowSchema(
        solar_to_load = round(direct_solar, 2),
        solar_to_battery = round(max(0, to_battery - grid_to_bat), 2),
        solar_to_grid = round(to_grid, 2),
        battery_to_load  = round(bat_to_load, 2),
        grid_to_load = round(grid_to_load, 2),
        grid_to_battery  = round(grid_to_bat, 2),
    )


@router.post("/ems/run", summary="Запустити нову симуляцію (ЛР3)")
async def run_simulation(
    start_date: Optional[str] = Query(default=None),
    days: int = Query(default=7, ge=1, le=30),
    strategy: str = Query(default="tariff_optimized"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
):
    from backend.app.simulation.simulation_service import SimulationService

    def _run():
        svc = SimulationService(db)
        svc.run(start_date=start_date, days=days, strategy=strategy)

    background_tasks.add_task(_run)
    return {"message": "Симуляцію запущено у фоновому режимі",
            "days": days, "strategy": strategy}
