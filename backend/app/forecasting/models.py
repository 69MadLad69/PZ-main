from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

logging.basicConfig(level=logging.INFO, format="%(levelname)s – %(message)s")
logger = logging.getLogger(__name__)

def mape(y_true: np.ndarray, y_pred: np.ndarray, eps: float = 1e-6) -> float:
    mask = np.abs(y_true) > eps
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


def evaluate(y_true: np.ndarray, y_pred: np.ndarray, name: str = "") -> dict:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    metrics = {
        "model": name,
        "R2": round(r2_score(y_true, y_pred), 4),
        "RMSE": round(np.sqrt(mean_squared_error(y_true, y_pred)), 4),
        "MAE": round(mean_absolute_error(y_true, y_pred), 4),
        "MAPE": round(mape(y_true, y_pred), 2),
    }
    logger.info("%-35s  R²=%.4f  RMSE=%.4f  MAE=%.4f  MAPE=%.2f%%",
                name, metrics["R2"], metrics["RMSE"], metrics["MAE"], metrics["MAPE"])
    return metrics

class HourlyMeanBaseline:

    def __init__(self):
        self._profile: Optional[pd.Series] = None

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "HourlyMeanBaseline":
        df = X.copy()
        df["_y"] = y.values
        self._profile = (
            df.groupby(["hour", "is_weekend"])["_y"].mean()
        )
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        def _lookup(row):
            key = (row["hour"], row["is_weekend"])
            return self._profile.get(key, self._profile.mean())
        return np.array([_lookup(r) for _, r in X.iterrows()])

LINEAR_FEATURES = [
    "hour_sin", "hour_cos", "month_sin", "month_cos",
    "dow_sin",  "dow_cos",
    "is_weekend", "is_working_time", "is_holiday",
    "temperature_c", "hdd", "cdd",
    "is_day_tariff",
]

POLY_FEATURES = [
    "hour_sin", "hour_cos", "month_sin", "month_cos",
    "is_working_time", "temperature_c", "hdd", "cdd",
]

def build_models() -> Dict[str, Any]:
    return {
        "Baseline (Hourly Mean)": HourlyMeanBaseline(),

        "Linear Regression": Pipeline([
            ("scaler", StandardScaler()),
            ("model", LinearRegression()),
        ]),

        "Ridge Regression": Pipeline([
            ("scaler", StandardScaler()),
            ("model", Ridge(alpha=1.0)),
        ]),

        "Polynomial Regression (deg-2)": Pipeline([
            ("scaler", StandardScaler()),
            ("poly", PolynomialFeatures(degree=2, include_bias=False,
                                          interaction_only=False)),
            ("model", Ridge(alpha=10.0)),
        ]),

        "Random Forest": RandomForestRegressor(
            n_estimators=200,
            max_depth=15,
            min_samples_leaf=3,
            n_jobs=-1,
            random_state=42,
        ),

        "Gradient Boosting": GradientBoostingRegressor(
            n_estimators=300,
            learning_rate=0.05,
            max_depth=4,
            max_features=0.6,
            subsample=0.8,
            min_samples_leaf=8,
            random_state=42,
        ),
    }

def get_feature_subset(model_name: str, X: pd.DataFrame) -> pd.DataFrame:
    avail = lambda cols: [c for c in cols if c in X.columns]
    if "Linear" in model_name or "Ridge" in model_name:
        return X[avail(LINEAR_FEATURES)]
    if "Polynomial" in model_name:
        return X[avail(POLY_FEATURES)]
    if "Baseline" in model_name:
        return X[avail(["hour", "is_weekend"])]
    return X


def train_all_models(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> Tuple[Dict[str, Any], pd.DataFrame, Dict[str, np.ndarray]]:
    models = build_models()
    metrics: List[dict] = []
    fitted: Dict[str, Any] = {}
    preds: Dict[str, np.ndarray] = {}

    for name, model in models.items():
        logger.info("Training: %s", name)
        Xt = get_feature_subset(name, X_train)
        Xv = get_feature_subset(name, X_test)

        model.fit(Xt, y_train)
        y_pred = model.predict(Xv)
        y_pred = np.clip(y_pred, 0, None)

        metrics.append(evaluate(y_test.values, y_pred, name))
        fitted[name] = model
        preds[name] = y_pred

    metrics_df = (
        pd.DataFrame(metrics)
        .sort_values("R2", ascending=False)
        .reset_index(drop=True)
    )
    return fitted, metrics_df, preds


def best_model_name(metrics_df: pd.DataFrame) -> str:
    return metrics_df.iloc[0]["model"]

def compute_residuals(y_true: np.ndarray, y_pred: np.ndarray) -> pd.Series:
    return pd.Series(y_true - y_pred, name="residuals")

def residual_stats(residuals: pd.Series) -> dict:
    return {
        "mean": round(residuals.mean(), 4),
        "std": round(residuals.std(), 4),
        "skewness": round(float(residuals.skew()), 4),
        "kurtosis": round(float(residuals.kurtosis()), 4),
        "max_abs": round(residuals.abs().max(), 4),
    }

def get_feature_importance(
    model: Any, feature_names: List[str]
) -> pd.DataFrame:
    if hasattr(model, "feature_importances_"):
        imp = model.feature_importances_
    elif hasattr(model, "named_steps"):
        inner = model.named_steps.get("model", None)
        if inner and hasattr(inner, "feature_importances_"):
            imp = inner.feature_importances_
        elif inner and hasattr(inner, "coef_"):
            imp = np.abs(inner.coef_)
        else:
            return pd.DataFrame()
    elif hasattr(model, "coef_"):
        imp = np.abs(model.coef_)
    else:
        return pd.DataFrame()

    df = pd.DataFrame({"feature": feature_names[:len(imp)], "importance": imp})
    return df.sort_values("importance", ascending=False).reset_index(drop=True)
