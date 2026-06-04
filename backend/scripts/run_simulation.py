from __future__ import annotations

import argparse
import logging
import sys

from backend.app.database import check_connection, session_scope
from backend.config.config import get_settings

from backend.app.simulation.simulation_service import SimulationService

logging.basicConfig(level=logging.INFO, format="%(levelname)s – %(message)s")
logger = logging.getLogger("run_simulation")


def _print_summary(result) -> None:
    e  = result.energy
    ec = result.economics

    print(f"EMS SIMULATION RESULTS  run_id={result.run_id}")
    print(f"Тривалість: {e.period_days} діб")
    print(f"ЕНЕРГЕТИЧНИЙ БАЛАНС")
    print(f"Загальне споживання: {e.total_load_kwh:,.1f} кВт·год")
    print(f"Генерація СЕС: {e.total_solar_kwh:,.1f} кВт·год")
    print(f"Імпорт з мережі: {e.total_import_kwh:,.1f} кВт·год")
    print(f"Експорт у мережу: {e.total_export_kwh:,.1f} кВт·год")
    print(f"Заряд BESS: {e.total_charge_kwh:,.1f} кВт·год")
    print(f"Розряд BESS: {e.total_discharge_kwh:,.1f} кВт·год")
    print(f"Покриття навант. СЕС: {e.solar_coverage_pct:.1f}%")
    print(f"Самоспоживання СЕС: {e.self_consumption_pct:.1f}%")
    print(f"Самодостатність: {e.self_sufficiency_pct:.1f}%")
    print(f"Цикли батареї: {e.battery_cycles:.2f}")
    print(f"\nЕКОНОМІЧНИЙ АНАЛІЗ")
    print(f"Вартість з EMS: {ec.ems_cost_uah:,.0f} грн")
    print(f"Вартість без EMS: {ec.baseline_cost_uah:,.0f} грн")
    print(f"Економія (період): {ec.savings_uah:,.0f} грн ({ec.savings_pct:.1f}%)")
    print(f"Річна економія: {ec.annual_savings_uah:,.0f} грн/рік")
    print(f"\nІНВЕСТИЦІЙНИЙ АНАЛІЗ")
    print(f"CAPEX (СЕС+BESS): {ec.capex_total_uah:,.0f} грн")
    print(f"Simple Payback: {ec.simple_payback_years:.1f} років")
    print(f"NPV (20 р, r=12%): {ec.npv_uah:,.0f} грн")
    print(f"IRR: {ec.irr_pct:.1f}%")
    print(f"LCOE: {ec.lcoe_uah_kwh:.2f} грн/кВт·год")


def main() -> None:
    parser = argparse.ArgumentParser(description="EMS ЛР3 — Run Simulation")
    parser.add_argument("--start", default=None,
                        help="Дата початку YYYY-MM-DD (default: липень)")
    parser.add_argument("--days", type=int, default=7,
                        help="Кількість діб (default: 7)")
    parser.add_argument("--strategy", default="tariff_optimized",
                        choices=["tariff_optimized", "rule_based"])
    parser.add_argument("--no-save",  action="store_true",
                        help="Не зберігати в БД")
    args = parser.parse_args()

    cfg = get_settings()
    logger.info("EMS ЛР3: Simulation")
    logger.info("Database: %s", cfg.database.url.split("@")[-1])

    if not check_connection():
        logger.error("Немає з'єднання з БД. Запустіть: docker-compose up -d")
        sys.exit(1)

    with session_scope() as db:
        svc = SimulationService(db)
        result = svc.run(
            start_date = args.start,
            days = args.days,
            strategy = args.strategy,
            save_to_db = not args.no_save,
        )

    _print_summary(result)
    logger.info("Done")


if __name__ == "__main__":
    main()
