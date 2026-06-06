from __future__ import annotations
import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.analytics.queries import AnalyticsQueries
from backend.config.config import get_settings


router  = APIRouter()
logger  = logging.getLogger(__name__)


@router.get("/consumption/monthly", summary="Місячне споживання (ЛР1)")
async def monthly_consumption(
    year: int = Query(default=2025, ge=2020, le=2030),
    db: Session = Depends(get_db),
):
    q  = AnalyticsQueries(db)
    df = q.monthly_consumption(year)
    return {"year": year, "data": df.to_dict(orient="records")}


@router.get("/consumption/daily", summary="Добове споживання (ЛР1)")
async def daily_consumption(
    start: date = Query(default=date(2025, 7, 1)),
    end: date = Query(default=date(2025, 7, 7)),
    db: Session = Depends(get_db),
):
    if (end - start).days > 366:
        raise HTTPException(400, "Максимальний діапазон — 366 діб")
    q = AnalyticsQueries(db)
    df = q.daily_consumption(str(start), str(end))
    return {"start": str(start), "end": str(end), "data": df.to_dict(orient="records")}


@router.get("/consumption/hourly", summary="Погодинне споживання (ЛР1)")
async def hourly_consumption(
    start: date = Query(default=date(2025, 7, 1)),
    end: date = Query(default=date(2025, 7, 2)),
    meter_id: Optional[int] = Query(default=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    from sqlalchemy import text
    cfg = get_settings()
    sql = text("""
        SELECT timestamp, energy_kwh, active_power_kw,
               CASE WHEN (timestamp AT TIME ZONE :tz)::time BETWEEN '07:00:00' AND '22:59:59'
                    THEN 'day' ELSE 'night' END AS tariff_zone
        FROM measurements
        WHERE meter_id = :mid
          AND timestamp >= :start AND timestamp < :end
        ORDER BY timestamp
        LIMIT :lim OFFSET :off
    """)
    lim = page_size
    off = (page - 1) * page_size
    rows = db.execute(sql, {"tz": cfg.weather.timezone, "mid": meter_id,
                             "start": start, "end": end,
                             "lim": lim, "off": off}).fetchall()
    count_sql = text("SELECT COUNT(*) FROM measurements WHERE meter_id=:mid AND timestamp>=:s AND timestamp<:e")
    total = db.execute(count_sql, {"mid": meter_id, "s": start, "e": end}).scalar() or 0
    return {
        "data": [dict(r._mapping) for r in rows],
        "meta": {"total": total, "page": page, "page_size": page_size,
                 "pages": (total + page_size - 1) // page_size},
    }


@router.get("/consumption/tariff", summary="Споживання по тарифних зонах (ЛР1)")
async def tariff_zone_analysis(
    start: date = Query(default=date(2025, 1, 1)),
    end: date = Query(default=date(2025, 12, 31)),
    db: Session = Depends(get_db),
):
    q  = AnalyticsQueries(db)
    df = q.tariff_zone_analysis(str(start), str(end))
    return {"start": str(start), "end": str(end), "data": df.to_dict(orient="records")}


@router.get("/consumption/specific", summary="Питоме споживання кВт·год/м²")
async def specific_consumption(
    start: date = Query(default=date(2025, 1, 1)),
    end: date = Query(default=date(2025, 12, 31)),
    db: Session = Depends(get_db),
):
    cfg = get_settings()
    q = AnalyticsQueries(db)
    df = q.specific_consumption(str(start), str(end), area_m2=cfg.object.area_m2)
    return {"area_m2": cfg.object.area_m2, "data": df.to_dict(orient="records")}
