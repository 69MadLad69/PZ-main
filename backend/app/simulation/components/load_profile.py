from __future__ import annotations

import logging
from typing import Dict, Optional

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.config.config import get_settings

logger = logging.getLogger(__name__)

UA_HOLIDAYS = frozenset({(1,1),(1,7),(3,8),(5,1),(6,8),(6,28),(8,24),(10,14),(12,25)})


class LoadProfile:
    def __init__(self, db: Session):
        self.db   = db
        cfg = get_settings().object
        self.avg = cfg.avg_load_kw
        self.min_ = cfg.min_load_kw
        self.max_ = cfg.max_load_kw
        mode = cfg.operation_mode  # "8-20"
        try:
            self._work_start, self._work_end = (int(x) for x in mode.split("-"))
        except ValueError:
            self._work_start, self._work_end = 8, 20

        self._baseline: Optional[Dict] = None

    def _load_baseline(self) -> None:
        sql = text("""
            SELECT month, hour_of_day, day_type, expected_kwh
            FROM baseline_consumption
            WHERE object_id = 1
        """)
        result = self.db.execute(sql)
        rows = result.fetchall()
        self._baseline = {}
        for r in rows:
            key = (int(r.month), int(r.hour_of_day), r.day_type)
            self._baseline[key] = float(r.expected_kwh)
        logger.info("LoadProfile: loaded %d baseline entries", len(self._baseline))

    def get_baseline(self, ts: pd.Timestamp) -> float:
        if self._baseline is None:
            self._load_baseline()
        m = ts.month
        h = ts.hour
        dt = "weekend" if ts.dayofweek >= 5 else "weekday"
        key = (m, h, dt)
        val = self._baseline.get(key)
        if val is not None:
            return val
        return self._synthetic_load(h, ts.dayofweek)

    def _synthetic_load(self, hour: int, dow: int) -> float:
        is_work = self._work_start <= hour < self._work_end
        is_we = dow >= 5
        if is_work and not is_we:
            factor = 0.90 if 10 <= hour <= 15 else 0.75
        elif is_work:
            factor = 0.65
        else:
            factor = 0.28
        return round(self.avg * factor, 3)

    def get_actual_hourly(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
        sql = text("""
            SELECT m.timestamp, m.energy_kwh
            FROM measurements m
            JOIN meters mt ON mt.id = m.meter_id
            WHERE mt.type = 'main' AND mt.level = 1
              AND m.timestamp >= :start AND m.timestamp < :end
            ORDER BY m.timestamp
        """)
        result = self.db.execute(sql, {"start": start, "end": end})
        rows = result.fetchall()
        if not rows:
            return pd.Series(dtype=float)
        df = pd.DataFrame(rows, columns=["timestamp", "energy_kwh"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        return df.set_index("timestamp")["energy_kwh"]
