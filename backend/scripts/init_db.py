from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone

from backend.app.models.models import (
    Base,
    BatteryMode,
    BatteryState,
    BaselineConsumption,
    EnergyEfficiencyMetric,
    EnergyObject,
    Measurement,
    Meter,
    MeterType,
    ObjectType,
    SolarGeneration,
    TariffZone,
    TariffZoneType,
    WeatherData,
)
from backend.app.database import engine, session_scope, check_connection
from backend.app.analytics.queries import VIEWS_DDL
from backend.config.config import get_settings
from backend.scripts.generate_data import generate_all

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s – %(message)s",
)
logger = logging.getLogger("init_db")
settings = get_settings()

def create_tables(reset: bool = False):
    if reset:
        logger.warning("DROP ALL TABLES requested!")
        _drop_views()
        Base.metadata.drop_all(bind=engine)
    logger.info("Creating tables")
    Base.metadata.create_all(bind=engine)
    logger.info("Tables created: %s", list(Base.metadata.tables.keys()))


def _drop_views():
    from sqlalchemy import text
    views = [
        "monthly_energy_cost",
        "level_1_consumption",
        "level_2_consumption",
        "level_3_consumption",
        "daily_meter_summary",
    ]
    with engine.connect() as conn:
        for view in views:
            conn.execute(text(f"DROP VIEW IF EXISTS {view} CASCADE"))
            logger.info("Dropped view: %s", view)
        conn.commit()
    logger.info("All views dropped.")

def seed_reference_data():
    with session_scope() as db:
        if db.query(EnergyObject).count() > 0:
            logger.info("Reference data already seeded – skipping.")
            return

        logger.info("Seeding reference data")
        s = settings

        obj = EnergyObject(
            name=s.object.name,
            type=ObjectType(s.object.type),
            location=s.object.location,
            area_m2=s.object.area_m2,
            max_power_kw=s.object.max_power_kw,
            meter_count=s.object.meter_count,
            operation_mode=s.object.operation_mode,
            avg_load_kw=s.object.avg_load_kw,
            min_load_kw=s.object.min_load_kw,
            max_load_kw=s.object.max_load_kw,
            description="Медичний центр, Київ. Комплексна система енергоменеджменту.",
        )
        db.add(obj)
        db.flush()

        type_map = {
            "main": MeterType.main,
            "zone": MeterType.zone,
            "solar": MeterType.solar,
            "battery": MeterType.battery,
            "emergency": MeterType.emergency,
        }
        for m_cfg in s.meters:
            meter = Meter(
                id=m_cfg.id,
                object_id=obj.id,
                name=m_cfg.name,
                type=type_map[m_cfg.type],
                level=m_cfg.level,
                location=m_cfg.location,
                description=m_cfg.description,
                serial_number=f"SN-{m_cfg.id:04d}-2025",
                is_active=True,
                installed_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            )
            db.add(meter)

        zone_type_map = {
            "day": TariffZoneType.day,
            "night": TariffZoneType.night,
        }
        for z_cfg in s.tariff.zones:
            zone = TariffZone(
                name=z_cfg.name,
                tariff_name=s.tariff.name,
                zone_type=zone_type_map[z_cfg.zone_type],
                start_time=z_cfg.start_time,
                end_time=z_cfg.end_time,
                rate_uah_kwh=z_cfg.rate_uah_kwh,
                valid_from=datetime(2025, 1, 1, tzinfo=timezone.utc),
                is_active=True,
            )
            db.add(zone)

        logger.info("Reference data seeded: 1 object, %d meters, %d tariff zones",
                    len(s.meters), len(s.tariff.zones))

def create_views():
    from sqlalchemy import text
    logger.info("Creating SQL views")
    with engine.connect() as conn:
        for stmt in VIEWS_DDL.split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
        conn.commit()
    logger.info("SQL views created.")

CHUNK = 2000

def _bulk_insert(db, model, records, label: str):
    total = len(records)
    logger.info("  Inserting %d %s rows", total, label)
    for i in range(0, total, CHUNK):
        chunk = records[i : i + CHUNK]
        db.bulk_insert_mappings(model, chunk)
        db.flush()
        if (i // CHUNK) % 10 == 0:
            logger.info("%d / %d", min(i + CHUNK, total), total)

def insert_synthetic_data():
    with session_scope() as db:
        if db.query(Measurement).count() > 0:
            logger.info("Measurements already exist – skipping generation.")
            return

    logger.info("Generating 8760h of synthetic data")
    t0 = time.time()
    data = generate_all(settings.generation.year)
    logger.info("Generation complete in %.1fs", time.time() - t0)

    with session_scope() as db:
        solar_fixed = []
        for r in data["solar"]:
            row = dict(r)
            ts = row["timestamp"]
            if hasattr(ts, "tzinfo") and ts.tzinfo is not None:
                ts = ts.astimezone(timezone.utc)
            row["timestamp"] = ts
            solar_fixed.append(row)

        weather_fixed = []
        for r in data["weather"]:
            row = dict(r)
            ts = row["timestamp"]
            if hasattr(ts, "tzinfo") and ts.tzinfo is not None:
                ts = ts.astimezone(timezone.utc)
            row["timestamp"] = ts
            weather_fixed.append(row)

        _bulk_insert(db, WeatherData, weather_fixed, "weather")
        _bulk_insert(db, Measurement, data["measurements"], "measurements")
        _bulk_insert(db, SolarGeneration, solar_fixed, "solar")
        _bulk_insert(db, BatteryState, data["battery"], "battery")
        _bulk_insert(db, BaselineConsumption, data["baseline"], "baseline")
        _bulk_insert(db, EnergyEfficiencyMetric, data["metrics"], "metrics")

    logger.info("All synthetic data inserted (%.1fs total).", time.time() - t0)

def main():
    parser = argparse.ArgumentParser(description="Initialize EMS database")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate tables")
    parser.add_argument("--skip-data", action="store_true", help="Skip data generation")
    args = parser.parse_args()

    logger.info("EMS Database Initialization")
    logger.info("Database: %s", settings.database.url.split("@")[-1])

    if not check_connection():
        logger.error("Cannot connect to database. Check Docker/PostgreSQL is running.")
        sys.exit(1)

    create_tables(reset=args.reset)
    seed_reference_data()
    create_views()

    if not args.skip_data:
        insert_synthetic_data()

    logger.info("Initialization complete!")


if __name__ == "__main__":
    main()
