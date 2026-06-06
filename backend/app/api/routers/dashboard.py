from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.api.schemas import DashboardSummary, KPIValue
from backend.app.analytics.queries import AnalyticsQueries
from backend.config.config import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)
CO2_KG_PER_KWH = 0.302


def _kpi(value: float, unit: str, prev: Optional[float] = None) -> KPIValue:
    change = None; trend = None
    if prev and prev != 0:
        change = round((value - prev) / abs(prev) * 100, 1)
        trend = "up" if change > 0 else ("down" if change < 0 else "flat")
    return KPIValue(value=round(value, 2), unit=unit, change_pct=change, trend=trend)


@router.get("/dashboard/summary", response_model=DashboardSummary,
            summary="Головна панель: KPI поточного стану")
async def dashboard_summary(
    year: int = Query(default=2025),
    db: Session = Depends(get_db),
):
    cfg = get_settings()
    q   = AnalyticsQueries(db)

    monthly = q.monthly_consumption(year)
    last_month = monthly.iloc[-1] if not monthly.empty else None

    solar_sql = text("""
        SELECT COALESCE(SUM(energy_kwh), 0) AS total
        FROM solar_generation
        WHERE EXTRACT(YEAR  FROM timestamp AT TIME ZONE :tz) = :yr
          AND EXTRACT(MONTH FROM timestamp AT TIME ZONE :tz) = :mo
    """)
    now = datetime.now(timezone.utc)
    solar_row = db.execute(solar_sql, {"tz": cfg.weather.timezone,
                                       "yr": year, "mo": now.month}).fetchone()
    solar_kwh = float(solar_row.total) if solar_row else 0.0

    sim_sql = text("""
        SELECT solar_kwh, load_kwh, soc_pct, import_kwh
        FROM simulation_results
        ORDER BY timestamp DESC LIMIT 1
    """)
    try:
        sim_row = db.execute(sim_sql).fetchone()
    except Exception:
        sim_row = None

    savings_sql = text("""
        SELECT COALESCE(SUM(savings_uah), 0)
        FROM simulation_runs WHERE status = 'completed'
    """)
    try:
        sav = db.execute(savings_sql).scalar() or 0.0
    except Exception:
        sav = 0.0

    current_kw  = float(sim_row.load_kwh) if sim_row else cfg.object.avg_load_kw
    soc_pct = float(sim_row.soc_pct)  if sim_row else 50.0
    today_kwh = float(last_month.avg_kw * 24) if last_month is not None else 0.0
    month_kwh = float(last_month.total_kwh)   if last_month is not None else 0.0
    solar_cov = (solar_kwh / month_kwh * 100) if month_kwh > 0 else 0.0
    co2_saved = solar_kwh * CO2_KG_PER_KWH

    return DashboardSummary(
        current_consumption_kw = _kpi(current_kw,  "кВт"),
        today_consumption_kwh = _kpi(today_kwh,   "кВт·год"),
        solar_generation_kwh = _kpi(solar_kwh,   "кВт·год"),
        battery_soc_pct = _kpi(soc_pct,     "%"),
        cost_savings_uah = _kpi(float(sav),  "грн"),
        co2_reduction_kg = _kpi(co2_saved,   "кг"),
        solar_coverage_pct = _kpi(solar_cov,   "%"),
        month_consumption_kwh  = _kpi(month_kwh,   "кВт·год"),
        last_updated = now,
    )


@router.get("/dashboard/kpi", summary="KPI за обраний рік")
async def dashboard_kpi(
    year: int = Query(default=2025),
    db: Session = Depends(get_db),
):
    q = AnalyticsQueries(db)
    monthly = q.monthly_consumption(year)
    if monthly.empty:
        return {"year": year, "months": []}
    return {
        "year": year,
        "total_kwh": round(float(monthly["total_kwh"].sum()), 1),
        "total_cost_uah": round(float(monthly["total_cost_uah"].sum()), 0),
        "months": monthly.to_dict(orient="records"),
    }
