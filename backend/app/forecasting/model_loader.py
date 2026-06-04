from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

import joblib
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s – %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "models_saved"
)

def _slugify(name: str) -> str:
    return name.lower().replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_")

def save_model(model: Any, name: str, models_dir: str = DEFAULT_DIR) -> str:
    os.makedirs(models_dir, exist_ok=True)
    path = os.path.join(models_dir, f"{_slugify(name)}.joblib")
    joblib.dump(model, path)
    logger.info("Saved %-35s → %s", name, path)
    return path

def load_model(name: str, models_dir: str = DEFAULT_DIR) -> Any:
    path = os.path.join(models_dir, f"{_slugify(name)}.joblib")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Model file not found: {path}")
    model = joblib.load(path)
    logger.info("Loaded %s from %s", name, path)
    return model

def save_all_models(fitted: Dict[str, Any], models_dir: str = DEFAULT_DIR) -> Dict[str, str]:
    return {name: save_model(model, name, models_dir) for name, model in fitted.items()}

def list_saved_models(models_dir: str = DEFAULT_DIR) -> List[str]:
    if not os.path.exists(models_dir):
        return []
    return [f for f in os.listdir(models_dir) if f.endswith(".joblib")]

def save_metadata(metrics_df: pd.DataFrame, feature_names: list,
                  best_name: str, models_dir: str = DEFAULT_DIR) -> None:
    import json, datetime
    meta = {
        "trained_at": datetime.datetime.now().isoformat(),
        "best_model": best_name,
        "feature_count": len(feature_names),
        "feature_names": feature_names,
        "metrics": metrics_df.to_dict(orient="records"),
    }
    path = os.path.join(models_dir, "metadata.json")
    os.makedirs(models_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    logger.info("Metadata saved → %s", path)
