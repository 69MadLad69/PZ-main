"""
Analytical SQL views and query builders for EMS.
Views implement 3-level consumption hierarchy per the assignment spec.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

VIEWS_DDL = """
CREATE OR REPLACE VIEW level_1_consumption AS
SELECT
    m.timestamp                                       AS ts,
    DATE(m.timestamp AT TIME ZONE 'Europe/Kyiv')      AS day,
    EXTRACT(MONTH FROM m.timestamp AT TIME ZONE 'Europe/Kyiv')::INT AS month,
    EXTRACT(YEAR  FROM m.timestamp AT TIME ZONE 'Europe/Kyiv')::INT AS year,
    EXTRACT(HOUR  FROM m.timestamp AT TIME ZONE 'Europe/Kyiv')::INT AS hour,
    CASE
        WHEN EXTRACT(DOW FROM m.timestamp AT TIME ZONE 'Europe/Kyiv') IN (0,6)
        THEN 'weekend' ELSE 'weekday'
    END                                                AS day_type,
    m.active_power_kw,
    m.energy_kwh,
    m.power_factor,
    -- Tariff zone classification (2-zone: 07–23 day, 23–07 night)
    CASE
        WHEN (m.timestamp AT TIME ZONE 'Europe/Kyiv')::time
             BETWEEN '07:00:00' AND '22:59:59'
        THEN 'day' ELSE 'night'
    END                                                AS tariff_zone,
    CASE
        WHEN (m.timestamp AT TIME ZONE 'Europe/Kyiv')::time
             BETWEEN '07:00:00' AND '22:59:59'
        THEN m.energy_kwh * 6.9
        ELSE m.energy_kwh * 5.6
    END                                                AS cost_uah
FROM measurements m
JOIN meters mt ON mt.id = m.meter_id
WHERE mt.type = 'main'
  AND mt.level = 1;

CREATE OR REPLACE VIEW level_2_consumption AS
SELECT
    m.timestamp                                       AS ts,
    DATE(m.timestamp AT TIME ZONE 'Europe/Kyiv')      AS day,
    mt.name                                           AS meter_name,
    mt.type                                           AS meter_type,
    mt.location,
    m.active_power_kw,
    m.energy_kwh,
    -- Share of total: join level_1 for the same timestamp
    m.energy_kwh / NULLIF(l1.energy_kwh, 0) * 100.0  AS share_pct
FROM measurements m
JOIN meters mt ON mt.id = m.meter_id
LEFT JOIN (
    SELECT m2.timestamp, m2.energy_kwh
    FROM measurements m2
    JOIN meters mt2 ON mt2.id = m2.meter_id
    WHERE mt2.type = 'main'
) l1 ON l1.timestamp = m.timestamp
WHERE mt.level = 2;

CREATE OR REPLACE VIEW level_3_consumption AS
SELECT
    m.timestamp                                       AS ts,
    DATE(m.timestamp AT TIME ZONE 'Europe/Kyiv')      AS day,
    mt.name                                           AS meter_name,
    mt.type                                           AS meter_type,
    m.active_power_kw,
    m.energy_kwh,
    -- Solar & battery enrichment
    sg.power_kw                                       AS solar_power_kw,
    sg.energy_kwh                                     AS solar_energy_kwh,
    bs.soc_pct                                        AS battery_soc_pct,
    bs.mode                                           AS battery_mode
FROM measurements m
JOIN meters mt ON mt.id = m.meter_id
LEFT JOIN solar_generation sg ON sg.timestamp = m.timestamp AND mt.type = 'solar'
LEFT JOIN battery_state    bs ON bs.timestamp = m.timestamp AND mt.type = 'battery'
WHERE mt.level = 3;

CREATE OR REPLACE VIEW daily_meter_summary AS
SELECT
    DATE(m.timestamp AT TIME ZONE 'Europe/Kyiv') AS day,
    mt.id                                        AS meter_id,
    mt.name                                      AS meter_name,
    mt.type                                      AS meter_type,
    mt.level,
    SUM(m.energy_kwh)                            AS total_kwh,
    MAX(m.active_power_kw)                       AS peak_kw,
    AVG(m.active_power_kw)                       AS avg_kw,
    MIN(m.active_power_kw)                       AS min_kw,
    COUNT(*)                                     AS readings_count
FROM measurements m
JOIN meters mt ON mt.id = m.meter_id
GROUP BY day, mt.id, mt.name, mt.type, mt.level;

CREATE OR REPLACE VIEW monthly_energy_cost AS
SELECT
    year,
    month,
    SUM(energy_kwh)                              AS total_kwh,
    SUM(CASE WHEN tariff_zone = 'day'   THEN energy_kwh ELSE 0 END) AS day_kwh,
    SUM(CASE WHEN tariff_zone = 'night' THEN energy_kwh ELSE 0 END) AS night_kwh,
    SUM(cost_uah)                                AS total_cost_uah,
    MAX(active_power_kw)                         AS peak_kw,
    AVG(active_power_kw)                         AS avg_kw
FROM level_1_consumption
GROUP BY year, month
ORDER BY year, month;
"""

class AnalyticsQueries:

    def __init__(self, db: Session):
        self.db = db

    def _q(self, sql: str, params: dict) -> pd.DataFrame:
        result = self.db.execute(text(sql), params)
        return pd.DataFrame(result.fetchall(), columns=result.keys())

    def daily_consumption(
        self, start_date: str, end_date: str, meter_level: int = 1
    ) -> pd.DataFrame:
        """Daily kWh, peak kW and cost for level-1 (or specified level) meters."""
        return self._q(
            """
            SELECT
                day,
                SUM(energy_kwh)    AS total_kwh,
                MAX(active_power_kw) AS peak_kw,
                AVG(active_power_kw) AS avg_kw,
                SUM(cost_uah)      AS cost_uah,
                day_type
            FROM level_1_consumption
            WHERE day BETWEEN :start AND :end
            GROUP BY day, day_type
            ORDER BY day
            """,
            {"start": start_date, "end": end_date},
        )

    def monthly_consumption(self, year: int) -> pd.DataFrame:
        return self._q(
            """
            SELECT * FROM monthly_energy_cost WHERE year = :year
            """,
            {"year": year},
        )

    def tariff_zone_analysis(
        self, start_date: str, end_date: str
    ) -> pd.DataFrame:
        return self._q(
            """
            SELECT
                tariff_zone,
                SUM(energy_kwh)  AS total_kwh,
                SUM(cost_uah)    AS total_uah,
                AVG(active_power_kw) AS avg_kw,
                COUNT(*)         AS hours
            FROM level_1_consumption
            WHERE day BETWEEN :start AND :end
            GROUP BY tariff_zone
            """,
            {"start": start_date, "end": end_date},
        )

    def specific_consumption(
        self, start_date: str, end_date: str, area_m2: float = 1200.0
    ) -> pd.DataFrame:
        return self._q(
            """
            SELECT
                month,
                year,
                SUM(energy_kwh)               AS total_kwh,
                SUM(energy_kwh) / :area        AS kwh_per_m2
            FROM level_1_consumption
            WHERE day BETWEEN :start AND :end
            GROUP BY year, month
            ORDER BY year, month
            """,
            {"start": start_date, "end": end_date, "area": area_m2},
        )

    def baseline_comparison(
        self,
        object_id: int,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        return self._q(
            """
            SELECT
                l1.day,
                l1.hour,
                l1.day_type,
                SUM(l1.energy_kwh)                          AS actual_kwh,
                AVG(bc.expected_kwh)                        AS baseline_kwh,
                (SUM(l1.energy_kwh) - AVG(bc.expected_kwh))
                    / NULLIF(AVG(bc.expected_kwh), 0) * 100 AS deviation_pct
            FROM level_1_consumption l1
            LEFT JOIN baseline_consumption bc
                   ON bc.object_id   = :oid
                  AND bc.month       = EXTRACT(MONTH FROM l1.day)::INT
                  AND bc.hour_of_day = l1.hour
                  AND bc.day_type::TEXT    = l1.day_type
            WHERE l1.day BETWEEN :start AND :end
            GROUP BY l1.day, l1.hour, l1.day_type
            ORDER BY l1.day, l1.hour
            """,
            {"oid": object_id, "start": start_date, "end": end_date},
        )

    def anomaly_detection(
        self,
        object_id: int,
        start_date: str,
        end_date: str,
        threshold_pct: float = 20.0,
    ) -> pd.DataFrame:
        df = self.baseline_comparison(object_id, start_date, end_date)
        if df.empty:
            return df
        return df[df["deviation_pct"].abs() > threshold_pct].copy()

    def load_factor_analysis(
        self, start_date: str, end_date: str
    ) -> pd.DataFrame:
        return self._q(
            """
            SELECT
                day,
                SUM(energy_kwh)               AS total_kwh,
                MAX(active_power_kw)           AS peak_kw,
                AVG(active_power_kw)           AS avg_kw,
                AVG(active_power_kw)
                    / NULLIF(MAX(active_power_kw), 0) AS load_factor,
                MAX(active_power_kw)
                    / NULLIF(AVG(active_power_kw), 0) AS peak_to_avg
            FROM level_1_consumption
            WHERE day BETWEEN :start AND :end
            GROUP BY day
            ORDER BY day
            """,
            {"start": start_date, "end": end_date},
        )

    def solar_battery_balance(
        self, start_date: str, end_date: str
    ) -> pd.DataFrame:
        return self._q(
            """
            SELECT
                DATE(sg.timestamp AT TIME ZONE 'Europe/Kyiv') AS day,
                SUM(l1_agg.energy_kwh)    AS consumption_kwh,
                SUM(sg.energy_kwh)        AS solar_kwh,
                SUM(bs.energy_kwh)        AS battery_kwh,
                SUM(l1_agg.energy_kwh)
                    - SUM(sg.energy_kwh)  AS grid_import_kwh
            FROM solar_generation sg
            JOIN battery_state bs ON bs.timestamp = sg.timestamp
            JOIN (
                SELECT ts, SUM(energy_kwh) AS energy_kwh
                FROM level_1_consumption
                GROUP BY ts
            ) l1_agg ON l1_agg.ts = sg.timestamp
            WHERE DATE(sg.timestamp AT TIME ZONE 'Europe/Kyiv')
                  BETWEEN :start AND :end
            GROUP BY day
            ORDER BY day
            """,
            {"start": start_date, "end": end_date},
        )

    def hourly_profile(
        self, start_date: str, end_date: str
    ) -> pd.DataFrame:
        return self._q(
            """
            SELECT
                hour,
                day_type,
                AVG(active_power_kw)  AS avg_kw,
                MAX(active_power_kw)  AS max_kw,
                MIN(active_power_kw)  AS min_kw,
                STDDEV(active_power_kw) AS std_kw
            FROM level_1_consumption
            WHERE day BETWEEN :start AND :end
            GROUP BY hour, day_type
            ORDER BY day_type, hour
            """,
            {"start": start_date, "end": end_date},
        )
