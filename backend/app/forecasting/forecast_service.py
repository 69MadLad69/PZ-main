from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path
from typing import Dict, List, Optional
import json

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from backend.app.forecasting.feature_engineering import (
    TARGET, _UA_HOLIDAYS, build_features, clean_data, get_feature_columns,
    load_raw_data, prepare_ml_dataset, train_test_split_temporal,
)
from backend.app.forecasting.model_loader import (
    load_model,
    save_all_models,
    save_metadata,
)
from backend.app.forecasting.models import (
    best_model_name,
    get_feature_subset,
    train_all_models,
)
from backend.config.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s – %(message)s")
logger = logging.getLogger(__name__)

class ForecastService:
    def __init__(
        self,
        fitted_models: dict,
        best_name: str,
        metrics_df: pd.DataFrame,
        train_df: pd.DataFrame,
        test_df: pd.DataFrame,
        full_df=None
    ):
        self._models = fitted_models
        self._best_name = best_name
        self.metrics = metrics_df
        self._train_df = train_df
        self._test_df = test_df
        self._full_df   = full_df if full_df is not None else train_df  # для clim
        self._settings = get_settings()
        self._saved_feature_cols: Optional[List[str]] = None

    @property
    def _solar_kw(self) -> float:
        return self._settings.solar.capacity_kw

    @property
    def _day_rate(self) -> float:
        for z in self._settings.tariff.zones:
            if z.zone_type == "day":
                return z.rate_uah_kwh
        return 6.9

    @property
    def _night_rate(self) -> float:
        for z in self._settings.tariff.zones:
            if z.zone_type == "night":
                return z.rate_uah_kwh
        return 5.6

    @property
    def _models_dir(self) -> str:
        return self._settings.forecasting.models_dir

    @classmethod
    def train(
        cls,
        db: Session,
        year: None,
        save: bool = True,
    ) -> "ForecastService":
        cfg = get_settings()
        logger.info("ForecastService.train() year=%s",
                    year or cfg.generation.year)

        raw = load_raw_data(db, year=year)
        clean, report = clean_data(raw)
        logger.info("Quality report: %s", report)

        featured = build_features(clean)
        train_df, test_df = train_test_split_temporal(featured)

        X_train, y_train = prepare_ml_dataset(train_df)
        X_test, y_test  = prepare_ml_dataset(test_df)

        fitted, metrics_df, _ = train_all_models(
            X_train, y_train, X_test, y_test
        )
        best = best_model_name(metrics_df)
        logger.info("Best model: %s  R²=%.4f", best, metrics_df.iloc[0]["R2"])

        if save:
            models_dir = cfg.forecasting.models_dir
            save_all_models(fitted, models_dir)
            save_metadata(metrics_df, get_feature_columns(), best, models_dir)

        return cls(fitted, best, metrics_df, train_df, test_df, full_df=featured)

    @classmethod
    def from_saved(
        cls,
        db: Session,
        best_name: Optional[str] = None,
        year: Optional[int] = None,
    ) -> "ForecastService":
        cfg = get_settings()
        models_dir = cfg.forecasting.models_dir
        saved_features = None

        meta_path = Path(models_dir) / "metadata.json"
        if meta_path.exists():
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
                if best_name is None:
                    best_name = meta.get("best_model", "Gradient Boosting")
                saved_features = meta.get("feature_columns")
                logger.info("Loaded metadata: model=%s, features=%d",
                            best_name, len(saved_features or []))
        if best_name is None:
            best_name = "Gradient Boosting"
        model = load_model(best_name, cfg.forecasting.models_dir)
        raw = load_raw_data(db, year=year)
        clean, _ = clean_data(raw)
        featured = build_features(clean)
        train_df, test_df = train_test_split_temporal(featured)
        svc = cls({best_name: model}, best_name, pd.DataFrame(),
                  train_df, test_df, full_df=featured)
        svc._saved_feature_cols = saved_features
        logger.info("Loaded %s | train_end=%s | features=%d",
                    best_name, train_df.index.max().date(), len(saved_features or []))
        return svc

    def _feature_row(
        self,
        ts: pd.Timestamp,
        buf: List[float],
        clim: pd.DataFrame,
    ) -> dict:
        h = ts.hour
        dow = ts.dayofweek
        m = ts.month
        d = ts.day
        doy = ts.dayofyear

        key = (m, h)
        in_clim = key in clim.index
        t_c = float(clim.loc[key, "temperature_c"]) if in_clim else 10.0
        irr = float(clim.loc[key, "solar_irradiance_wm2"]) if in_clim else 0.0
        hum = float(clim.loc[key, "humidity_pct"]) if in_clim else 75.0

        is_we = int(dow >= 5)
        is_hol = int((m, d) in _UA_HOLIDAYS)
        is_wh = int(8 <= h <= 19)
        is_wt = int(is_wh and not is_we and not is_hol)
        season = (m - 1) // 3 + 1

        hdd = max(0.0, 18.0 - t_c) / 24.0
        cdd = max(0.0, t_c - 22.0) / 24.0
        t_mean = float(self._full_df["temperature_c"].mean()) if "temperature_c" in self._full_df.columns else 10.0
        t_dev = t_c - t_mean

        def lag(n: int) -> float:
            return float(buf[-n]) if len(buf) >= n else 5.0

        w24 = buf[-24:] if len(buf) >= 12 else [5.0]
        w168 = buf[-168:] if len(buf) >= 84 else [5.0]

        return {
            "hour": h,
            "day_of_week": dow,
            "day_of_month": d,
            "month": m,
            "quarter": (m - 1) // 3 + 1,
            "week_of_year": int(ts.isocalendar().week),
            "day_of_year": doy,
            "hour_sin": np.sin(2 * np.pi * h / 24),
            "hour_cos": np.cos(2 * np.pi * h / 24),
            "month_sin": np.sin(2 * np.pi * m / 12),
            "month_cos": np.cos(2 * np.pi * m / 12),
            "dow_sin": np.sin(2 * np.pi * dow / 7),
            "dow_cos": np.cos(2 * np.pi * dow / 7),
            "doy_sin": np.sin(2 * np.pi * doy / 365),
            "doy_cos": np.cos(2 * np.pi * doy / 365),
            "is_weekend": is_we,
            "is_holiday": is_hol,
            "is_working_hour": is_wh,
            "is_working_time": is_wt,
            "season": season,
            "temperature_c": t_c,
            "hdd": hdd,
            "cdd": cdd,
            "temp_dev": t_dev,
            "solar_irradiance_wm2": irr,
            "humidity_pct": hum,
            "is_day_tariff": int(7 <= h <= 22),
            "tariff_price": self._day_rate if 7 <= h <= 22 else self._night_rate,
            "lag_1": lag(1),
            "lag_2": lag(2),
            "lag_24": lag(24),
            "lag_48": lag(48),
            "lag_168": lag(168),
            "rolling_mean_24": float(np.mean(w24)),
            "rolling_std_24": float(np.std(w24))  if len(w24) > 1 else 1.0,
            "rolling_mean_168": float(np.mean(w168)),
            "rolling_std_168": float(np.std(w168)) if len(w168) > 1 else 1.0,
            "rolling_max_24": float(max(w24)),
            "rolling_min_24": float(min(w24)),
            "lag_168_delta": (buf[-1] - buf[-169]) if len(buf) >= 169 else 0.0,
        }

    def predict(
        self,
        X: pd.DataFrame,
        model_name: Optional[str] = None,
    ) -> np.ndarray:
        name = model_name or self._best_name
        model = self._models[name]
        cols = self._saved_feature_cols
        X_sub = X.reindex(columns=cols, fill_value=0.0) if cols else get_feature_subset(name, X)
        return np.clip(model.predict(X_sub), 0, None)

    def forecast_next_month(self) -> pd.DataFrame:
        last_ts = self._train_df.index.max()
        start_ts = last_ts + pd.Timedelta(hours=1)
        end_ts = start_ts + pd.DateOffset(months=1) - timedelta(hours=1)
        hours = int((end_ts - start_ts).total_seconds() // 3600) + 1
        return self.forecast_period(start_ts, hours)

    def predict_test_set(self):
        X_test, y_test = prepare_ml_dataset(self._test_df)
        if X_test.empty:
            return pd.DataFrame()
        y_pred = self.predict(X_test)
        result = pd.DataFrame(index=X_test.index)
        result["actual_kwh"] = y_test.values
        result["predicted_kwh"] = y_pred
        result["error_kwh"] = np.abs(y_test.values - y_pred)
        return result

    def forecast_period(
        self,
        start_ts: pd.Timestamp,
        hours: int,
    ) -> pd.DataFrame:
        tz = self._settings.weather.timezone
        clim_src = self._full_df
        clim = (
            clim_src
            .groupby([clim_src.index.month, clim_src.index.hour])
            [["temperature_c", "solar_irradiance_wm2", "humidity_pct"]]
            .mean()
        )

        buf: List[float] = list(self._train_df[TARGET].iloc[-200:].values.astype(float))

        if getattr(start_ts, "tzinfo", None) is not None:
            future_idx = pd.date_range(start_ts, periods=hours, freq="h")
        else:
            future_idx = pd.date_range(start_ts, periods=hours, freq="h", tz=tz)

        feature_cols = self._saved_feature_cols or get_feature_columns()
        
        predictions: List[float] = []

        for ts in future_idx:
            row = self._feature_row(ts, buf, clim)
            X = pd.DataFrame([{c: row.get(c, 0.0) for c in feature_cols}])
            pred = float(self.predict(X)[0])
            pred = max(0.0, pred)
            predictions.append(pred)
            buf.append(pred)
        
        result = pd.DataFrame(index=future_idx)
        result["predicted_kwh"] = predictions
        result["tariff_zone"] = ["day" if 7 <= ts.hour < 23 else "night"
                                       for ts in future_idx]
        result["tariff_price"] = [
            self._day_rate if z == "day" else self._night_rate
            for z in result["tariff_zone"]
        ]
        result["cost_uah"] = result["predicted_kwh"] * result["tariff_price"]

        inv_eff = self._settings.solar.inverter_efficiency
        result["solar_kwh"] = np.array([
            min(
                float(clim.loc[(ts.month, ts.hour), "solar_irradiance_wm2"])
                / 1000.0 * self._settings.solar.capacity_kw * inv_eff,
                pred,
            )
            if (ts.month, ts.hour) in clim.index else 0.0
            for ts, pred in zip(future_idx, predictions)
        ])
        result["solar_saving_uah"]  = result["solar_kwh"] * result["tariff_price"]
        result["net_grid_kwh"] = result["predicted_kwh"] - result["solar_kwh"]

        try:
            ts_p  = self.predict_test_set()
            sigma = float(np.sqrt(np.mean((ts_p["actual_kwh"].values - ts_p["predicted_kwh"].values)**2)))
        except Exception:
            sigma = 1.5
        sigma = max(sigma, 0.5)
        result["lower_bound"] = (result["predicted_kwh"] - 1.5 * sigma).clip(lower=0)
        result["upper_bound"] = result["predicted_kwh"] + 1.5 * sigma

        return result

    def forecast_summary(self) -> dict:
        area = self._settings.object.area_m2
        fc = self.forecast_next_month()
        return {
            "hourly": fc,
            "monthly_kwh": round(float(fc["predicted_kwh"].sum()), 1),
            "monthly_cost_uah": round(float(fc["cost_uah"].sum()), 1),
            "solar_saving_uah": round(float(fc["solar_saving_uah"].sum()), 1),
            "specific_kwh_m2": round(float(fc["predicted_kwh"].sum()) / area, 2),
        }
