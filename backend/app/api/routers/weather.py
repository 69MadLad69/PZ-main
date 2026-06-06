"""backend/app/api/routers/weather.py"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session
from datetime import date
from backend.app.api.deps import get_db
from backend.config.config import get_settings

router = APIRouter()

@router.get("/weather", summary="Метеодані (ЛР1)")
async def weather_data(
    start: date = Query(default=date(2025, 7, 1)),
    end:   date = Query(default=date(2025, 7, 7)),
    db: Session = Depends(get_db),
):
    cfg = get_settings()
    sql = text("""
        SELECT timestamp, temperature_c, solar_irradiance_wm2,
               humidity_pct, wind_speed_ms, hdd, cdd
        FROM weather_data
        WHERE timestamp >= :s AND timestamp < :e
        ORDER BY timestamp
        LIMIT 744
    """)
    rows = db.execute(sql, {"s": start, "e": end}).fetchall()
    return {"data": [dict(r._mapping) for r in rows]}
