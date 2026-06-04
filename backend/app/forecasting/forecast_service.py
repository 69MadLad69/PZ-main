from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from backend.app.forecasting.feature_engineering import (
    TARGET,
    build_features,
    clean_data,
    get_feature_columns,
    load_raw_data,
    prepare_ml_dataset,
    train_test_split_temporal,
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
    ):
        self._models = fitted_models
        self._best_name = best_name
        self.metrics = metrics_df
        self._train_df = train_df
        self._test_df = test_df
        self._settings = get_settings()

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
        year: Optional[int] = None,
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

        return cls(fitted, best, metrics_df, train_df, test_df)

    @classmethod
    def from_saved(
        cls,
        db: Session,
        best_name: Optional[str] = None,
        year: Optional[int] = None,
    ) -> "ForecastService":
        cfg = get_settings()
        models_dir = cfg.forecasting.models_dir

        if best_name is None:
            import json
            meta_path = Path(models_dir) / "metadata.json"
            if meta_path.exists():
                with open(meta_path, encoding="utf-8") as f:
                    best_name = json.load(f).get("best_model", "Gradient Boosting")
            else:
                best_name = "Gradient Boosting"

        model = load_model(best_name, models_dir)

        raw = load_raw_data(db, year=year)
        clean, _ = clean_data(raw)
        featured = build_features(clean)
        _, test_df = train_test_split_temporal(featured)

        return cls({best_name: model}, best_name,
                   pd.DataFrame(), featured, test_df)

    def predict(
        self,
        X: pd.DataFrame,
        model_name: Optional[str] = None,
    ) -> np.ndarray:
        name = model_name or self._best_name
        model = self._models[name]
        Xs = get_feature_subset(name, X)
        return np.clip(model.predict(Xs), 0, None)

    def forecast_next_month(self) -> pd.DataFrame:
        last_ts = self._train_df.index.max()
        start_ts = (last_ts + timedelta(hours=1)).replace(minute=0, second=0)
        end_ts = start_ts + pd.DateOffset(months=1) - timedelta(hours=1)
        return self.forecast_period(start_ts, int((end_ts - start_ts).total_seconds() // 3600) + 1)

    def forecast_period(
        self,
        start_ts: pd.Timestamp,
        hours: int,
    ) -> pd.DataFrame:
        tz = self._settings.weather.timezone
        features = get_feature_columns()

        future_idx = pd.date_range(start_ts,
                                   periods=hours,
                                   freq="h",
                                   tz=tz)

        seed = self._train_df[[TARGET, "temperature_c", "solar_irradiance_wm2",
                                "humidity_pct"]].iloc[-168:].copy()

        clim = (
            self._train_df
            .groupby([self._train_df.index.month, self._train_df.index.hour])
            [["temperature_c", "solar_irradiance_wm2", "humidity_pct"]]
            .mean()
        )

        all_data = pd.concat([
            seed,
            pd.DataFrame(index=future_idx, columns=seed.columns, dtype=float),
        ])
        predicted = np.zeros(len(future_idx))

        for i, ts in enumerate(future_idx):
            key = (ts.month, ts.hour)
            for col in ["temperature_c", "solar_irradiance_wm2", "humidity_pct"]:
                all_data.loc[ts, col] = (clim.loc[key, col]
                                         if key in clim.index else 0.0)

            row_featured = build_features(all_data)
            row_feat, _ = prepare_ml_dataset(row_featured.iloc[[-1]], drop_na=False)
            row_feat = row_feat.fillna(0)

            pred = float(self.predict(row_feat)[0])
            predicted[i] = pred
            all_data.loc[ts, TARGET] = pred

        result = pd.DataFrame(index=future_idx)
        result["predicted_kwh"] = predicted
        result["tariff_zone"] = np.where(
            pd.DatetimeIndex(future_idx).hour.isin(range(7, 23)), "day", "night"
        )
        result["tariff_price"]  = np.where(
            result["tariff_zone"] == "day", self._day_rate, self._night_rate
        )
        result["cost_uah"] = result["predicted_kwh"] * result["tariff_price"]

        clim_irr = np.array([
            clim.loc[(ts.month, ts.hour), "solar_irradiance_wm2"]
            if (ts.month, ts.hour) in clim.index else 0.0
            for ts in future_idx
        ])
        inv_eff = self._settings.solar.inverter_efficiency
        solar_kwh = np.clip(
            clim_irr / 1000 * self._solar_kw * inv_eff, 0, predicted
        )
        result["solar_kwh"] = solar_kwh
        result["solar_saving_uah"] = solar_kwh * result["tariff_price"]
        result["net_grid_kwh"] = result["predicted_kwh"] - solar_kwh
        return result

    def forecast_summary(self) -> dict:
        area = self._settings.object.area_m2
        fc = self.forecast_next_month()
        daily = fc.groupby(fc.index.date).agg(
            total_kwh =("predicted_kwh", "sum"),
            cost_uah =("cost_uah", "sum"),
            solar_kwh =("solar_kwh", "sum"),
            peak_kw =("predicted_kwh", "max"),
        ).reset_index().rename(columns={"index": "date"})

        return {
            "hourly": fc,
            "daily": daily,
            "monthly_kwh": round(fc["predicted_kwh"].sum(), 1),
            "monthly_cost_uah": round(fc["cost_uah"].sum(), 1),
            "solar_saving_uah": round(fc["solar_saving_uah"].sum(), 1),
            "specific_kwh_m2": round(fc["predicted_kwh"].sum() / area, 2),
        }
