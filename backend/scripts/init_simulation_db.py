import logging
import sys

from backend.app.database  import check_connection, engine
from backend.app.models.simulation_models import Base as SimBase, SimulationRun, SimulationResult
from backend.config.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s – %(message)s")
logger = logging.getLogger("init_sim_db")


def main():
    cfg = get_settings()
    logger.info("EMS ЛР3: Init Simulation DB")
    logger.info("Database: %s", cfg.database.url.split("@")[-1])

    if not check_connection():
        logger.error("Немає з'єднання з БД. docker-compose up -d")
        sys.exit(1)

    SimBase.metadata.create_all(bind=engine, tables=[
        SimulationRun.__table__,
        SimulationResult.__table__,
    ])
    logger.info("Simulation tables created: simulation_runs, simulation_results")
    logger.info("Done")


if __name__ == "__main__":
    main()
