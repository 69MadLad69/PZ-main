from __future__ import annotations

import argparse
import logging
import sys

from backend.app.database import check_connection, session_scope
from backend.config.config import get_settings

from backend.app.forecasting.forecast_service import ForecastService

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s – %(message)s",
)
logger = logging.getLogger("train_models")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="EMS ЛР2 — Train forecasting models"
    )
    parser.add_argument("--year",    type=int, default=None,
                        help="Year to use (default: settings.generation.year)")
    parser.add_argument("--no-save", action="store_true",
                        help="Skip saving models to disk")
    args = parser.parse_args()

    cfg = get_settings()
    logger.info("EMS ЛР2: Model Training")
    logger.info("Database: %s", cfg.database.url.split("@")[-1])
    logger.info("Models dir: %s", cfg.forecasting.models_dir)

    if not check_connection():
        logger.error("Cannot connect to DB. Run: docker-compose up -d")
        sys.exit(1)

    with session_scope() as db:
        svc = ForecastService.train(
            db,
            year=args.year,
            save=not args.no_save,
        )

    logger.info("\nModel Comparison")
    print(svc.metrics.to_string(index=False))

    best = svc.metrics.iloc[0]
    logger.info(
        "\nBest model: %s R²=%.4f RMSE=%.4f MAE=%.4f MAPE=%.2f%%",
        best["model"], best["R2"], best["RMSE"], best["MAE"], best["MAPE"],
    )

    if not args.no_save:
        logger.info("Models saved to: %s/", cfg.forecasting.models_dir)

    logger.info("Done")


if __name__ == "__main__":
    main()