from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime

import pandas as pd

from backend.app.analytics.queries import AnalyticsQueries
from backend.app.analytics.charts import save_all as save_charts
from backend.app.database import session_scope
from backend.config.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s – %(message)s")
logger = logging.getLogger("analytics")
settings = get_settings()

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)


def _save(df: pd.DataFrame, name: str, fmt: str = "csv"):
    path = os.path.join(REPORTS_DIR, f"{name}.{fmt}")
    if fmt == "csv":
        df.to_csv(path, index=False, encoding="utf-8-sig")
    elif fmt == "excel":
        df.to_excel(path, index=False)
    logger.info("Saved → %s", path)
    return path


def run_all_analytics(year: int = 2025, fmt: str = "csv", charts: bool = True):
    start = f"{year}-01-01"
    end = f"{year}-12-31"
    object_id = 1
    area_m2 = settings.object.area_m2
    obj_name = settings.object.name

    dfs: dict = {}

    with session_scope() as db:
        q = AnalyticsQueries(db)

        logger.info("1. Daily consumption")
        dfs["daily"] = q.daily_consumption(start, end)
        _save(dfs["daily"], "01_daily_consumption", fmt)
        if not dfs["daily"].empty:
            print("\nDaily Consumption (first 10 rows)")
            print(dfs["daily"].head(10).to_string(index=False))

        logger.info("2. Monthly consumption")
        dfs["monthly"] = q.monthly_consumption(year)
        _save(dfs["monthly"], "02_monthly_consumption", fmt)
        if not dfs["monthly"].empty:
            print("\nMonthly Consumption")
            print(dfs["monthly"].to_string(index=False))

        logger.info("3. Tariff zone analysis")
        dfs["tariff"] = q.tariff_zone_analysis(start, end)
        _save(dfs["tariff"], "03_tariff_zone_analysis", fmt)
        if not dfs["tariff"].empty:
            print("\nTariff Zone Analysis")
            print(dfs["tariff"].to_string(index=False))

        logger.info("4. Specific consumption (kWh/m²)")
        dfs["specific"] = q.specific_consumption(start, end, area_m2=settings.object.area_m2)
        _save(dfs["specific"], "04_specific_consumption", fmt)
        if not dfs["specific"].empty:
            print("\nSpecific Consumption kWh/m²")
            print(dfs["specific"].to_string(index=False))

        logger.info("5. Baseline comparison")
        df_base = q.baseline_comparison(object_id, start, end)
        _save(df_base, "05_baseline_comparison", fmt)

        logger.info("6. Anomaly detection (>20%%)")
        dfs["anomalies"] = q.anomaly_detection(object_id, start, end, threshold_pct=20.0)
        _save(dfs["anomalies"], "06_anomalies", fmt)
        logger.info("Found %d anomalous hours", len(dfs["anomalies"]))

        logger.info("7. Load factor analysis")
        dfs["load_factor"] = q.load_factor_analysis(start, end)
        _save(dfs["load_factor"], "07_load_factor", fmt)

        logger.info("8. Hourly load profile")
        dfs["hourly"] = q.hourly_profile(start, end)
        _save(dfs["hourly"], "08_hourly_profile", fmt)
        if not dfs["hourly"].empty:
            print("\nAverage Hourly Profile")
            print(dfs["hourly"].to_string(index=False))

        logger.info("9. Solar & battery balance")
        dfs["solar"] = q.solar_battery_balance(start, end)
        _save(dfs["solar"], "09_solar_battery_balance", fmt)

    if not dfs["monthly"].empty and "total_kwh" in dfs["monthly"].columns:
        annual_kwh = dfs["monthly"]["total_kwh"].sum()
        annual_cost = dfs["monthly"]["total_cost_uah"].sum() if "total_cost_uah" in dfs["monthly"].columns else 0
        print(f"ANNUAL SUMMARY {year}")
        print(f"Total consumption: {annual_kwh:,.0f} kWh")
        print(f"Specific: {annual_kwh/settings.object.area_m2:.1f} kWh/m²")
        print(f"Annual cost: {annual_cost:,.0f} UAH")
        print(f"Anomalies found: {len(dfs["anomalies"])}")    

    logger.info("All reports saved to %s/", os.path.abspath(REPORTS_DIR))

    if charts:
        logger.info("Generating charts")
        save_charts(
            reports_dir=REPORTS_DIR,
            dfs=dfs,
            area_m2=area_m2,
            object_name=obj_name,
        )
        chart_files = [f for f in os.listdir(REPORTS_DIR) if f.startswith("fig_")]
        logger.info("Charts saved: %s", ", ".join(sorted(chart_files)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--format", choices=["csv", "excel"], default="csv")
    parser.add_argument("--no-charts", action="store_true",
                        help="Skip PNG chart generation")    
    args = parser.parse_args()
    run_all_analytics(args.year, args.format)
