from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

import pandas as pd
from backend.app.api.deps import get_db
from backend.app.api.schemas import ForecastSummary
from backend.config.config import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)


def _svc(db: Session):
    try:
        from backend.app.forecasting.forecast_service import ForecastService
        return ForecastService.from_saved(db)
    except Exception as exc:
        logger.warning("ForecastService unavailable: %s", exc)
        return None

def _load_forecast_service(db: Session):
    try:
        from backend.app.forecasting.forecast_service import ForecastService
        return ForecastService.from_saved(db)
    except Exception as exc:
        logger.warning("ForecastService unavailable: %s", exc)
        return None


@router.get("/forecast/summary",
            summary="Прогноз наступного місяця (ЛР2 best model)")
async def forecast_summary(db: Session = Depends(get_db)):
    svc = _svc(db)
    if svc is None:
        raise HTTPException(503, "Модель не завантажена. Запустіть train_models.")
    try:
        s = svc.forecast_summary()
        metrics_dict = None
        if not svc.metrics.empty:
            b = svc.metrics.iloc[0]
            metrics_dict = {
                "R2": float(b.get("R2", b.get("R²", 0))),
                "RMSE": float(b.get("RMSE", 0)),
                "MAE": float(b.get("MAE", 0)),
                "MAPE": float(b.get("MAPE", b.get("MAPE%", 0))),
                "model_name": str(b.get("model", b.get("Модель", "GB"))),
            }
        return {
            "monthly_kwh":      s["monthly_kwh"],
            "monthly_cost_uah": s["monthly_cost_uah"],
            "solar_saving_uah": s["solar_saving_uah"],
            "specific_kwh_m2":  s["specific_kwh_m2"],
            "metrics":          metrics_dict,
        }
    except Exception as exc:
        logger.error("Forecast summary error: %s", exc, exc_info=True)
        raise HTTPException(500, str(exc))


@router.get("/forecast/hourly", summary="Погодинний прогноз (ЛР2)")
async def forecast_hourly(
    hours: int = Query(default=168, ge=1, le=744),
    db: Session = Depends(get_db),
):
    svc = _svc(db)
    if svc is None:
        raise HTTPException(503, "Модель не завантажена")
    cfg = get_settings()
    start_ts = svc._train_df.index.max() + pd.Timedelta(hours=1)
    try:
        fc = svc.forecast_period(start_ts, hours)
        fc.index = fc.index.astype(str)
        records = fc.reset_index().rename(columns={"index": "timestamp"}).to_dict(orient="records")
        return {"hours": hours, "data": records}
    except Exception as exc:
        raise HTTPException(500, str(exc))


@router.get("/forecast/test-predictions")
async def forecast_test_predictions(
    n: int = Query(default=168, ge=1, le=1440),
    db: Session = Depends(get_db),
):
    svc = _svc(db)
    if svc is None:
        raise HTTPException(503, "Модель не завантажена")
    try:
        result = svc.predict_test_set()
        if result.empty:
            return {"data": []}
        result.index = result.index.astype(str)
        rows = result.iloc[:n].reset_index().rename(columns={"index": "timestamp"})
        return {"data": rows.to_dict(orient="records")}
    except Exception as exc:
        raise HTTPException(500, str(exc))

@router.get("/forecast/metrics", summary="Метрики моделі прогнозування (ЛР2)")
async def forecast_metrics(db: Session = Depends(get_db)):
    svc = _svc(db)
    if svc is None:
        raise HTTPException(503, "Модель не завантажена")
    try:
        import numpy as np
        result = svc.predict_test_set()
        if not result.empty:
            actual = result["actual_kwh"].values
            pred = result["predicted_kwh"].values
            r2 = 1 - np.sum((actual-pred)**2) / np.sum((actual-actual.mean())**2)
            rmse = float(np.sqrt(np.mean((actual-pred)**2)))
            mae = float(np.mean(np.abs(actual-pred)))
            mape = float(np.mean(np.abs((actual-pred)/np.maximum(actual, 0.1))*100))
            computed = [{
                "model": svc._best_name, "R2": round(r2,4), "RMSE": round(rmse,4),
                "MAE": round(mae,4), "MAPE": round(mape,2),
            }]
            return {"metrics": computed}
    except Exception:
        pass
    if svc.metrics.empty:
        return {"metrics": []}
    return {"metrics": svc.metrics.to_dict(orient="records")}
