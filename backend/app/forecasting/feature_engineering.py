from __future__ import annotations

import logging
from functools import lru_cache
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.config.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s – %(message)s")
logger = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def _cfg():
    return get_settings()

def _hdd_base() -> float: return _cfg().weather.hdd_base_temp_c
def _cdd_base() -> float: return _cfg().weather.cdd_base_temp_c
def _day_rate() -> float:
    for z in _cfg().tariff.zones:
        if z.zone_type == "day":
            return z.rate_uah_kwh
    return 6.9
def _night_rate()  -> float:
    for z in _cfg().tariff.zones:
        if z.zone_type == "night":
            return z.rate_uah_kwh
    return 5.6
def _area_m2() -> float: return _cfg().object.area_m2
def _meter_id() -> int:   return _cfg().forecasting.main_meter_id
def _year() -> int:   return _cfg().generation.year
def _lags() -> List[int]: return list(_cfg().forecasting.feature_lags)
def _windows() -> List[int]: return list(_cfg().forecasting.rolling_windows)
def _tz() -> str:   return _cfg().weather.timezone

_UA_HOLIDAYS: frozenset[tuple] = frozenset({
    (1, 1), (1, 7), (3, 8), (5, 1), (6, 8), (6, 28),
    (8, 24), (10, 14), (12, 25),
})

TARGET = "energy_kwh"

def load_raw_data(
    db: Session,
    year: Optional[int] = None,
    meter_id: Optional[int] = None,
) -> pd.DataFrame:
    year = year or _year()
    meter_id = meter_id or _meter_id()
    tz = _tz()

    sql = text(f"""
        SELECT
            m.timestamp AS ts,
            m.active_power_kw,
            m.energy_kwh,
            m.power_factor,
            w.temperature_c,
            w.solar_irradiance_wm2,
            w.humidity_pct,
            w.wind_speed_ms,
            w.hdd,
            w.cdd,
            w.cloud_cover_pct
        FROM measurements m
        LEFT JOIN weather_data w ON w.timestamp = m.timestamp
        WHERE m.meter_id = :mid
          AND EXTRACT(YEAR FROM m.timestamp AT TIME ZONE :tz) = :yr
        ORDER BY m.timestamp
    """)
    result = db.execute(sql, {"mid": meter_id, "yr": year, "tz": tz})
    df = pd.DataFrame(result.fetchall(), columns=result.keys())

    if df.empty:
        logger.warning("No data found for meter_id=%d, year=%d", meter_id, year)
        return df

    df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.tz_convert(tz)
    df = df.set_index("ts").sort_index()
    logger.info("Loaded %d rows  meter=%d  year=%d  tz=%s",
                len(df), meter_id, year, tz)
    return df


def load_baseline(db: Session) -> pd.DataFrame:
    sql = text("""
        SELECT month, hour_of_day, day_type,
               expected_kwh, std_dev_kwh, temperature_coeff
        FROM baseline_consumption
        WHERE object_id = 1
        ORDER BY month, hour_of_day, day_type
    """)
    result = db.execute(sql)
    return pd.DataFrame(result.fetchall(), columns=result.keys())

def clean_data(df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    max_kw = _cfg().object.max_power_kw
    report: dict = {}
    tz = _tz()

    full_idx = pd.date_range(df.index.min(), df.index.max(),
                             freq="h", tz=tz)
    report["missing_timestamps"] = len(full_idx.difference(df.index))
    df = df.reindex(full_idx)

    dupes = df.index.duplicated().sum()
    report["duplicates"] = int(dupes)
    df = df[~df.index.duplicated(keep="first")]

    report["outliers_energy"] = int((df["energy_kwh"] > max_kw).sum())
    df["energy_kwh"] = df["energy_kwh"].clip(0, max_kw)
    df["active_power_kw"] = df["active_power_kw"].clip(0, max_kw)

    df["energy_kwh"] = df["energy_kwh"].interpolate(method="time", limit=3)

    weather_cols = ["temperature_c", "solar_irradiance_wm2", "humidity_pct",
                    "wind_speed_ms", "hdd", "cdd", "cloud_cover_pct"]
    for col in weather_cols:
        if col in df.columns:
            hourly_mean = df.groupby(df.index.hour)[col].transform("mean")
            df[col] = df[col].fillna(hourly_mean)

    before = len(df)
    df = df.dropna(subset=[TARGET])
    report["remaining_nans"] = int(df[["energy_kwh", "temperature_c"]].isna().sum().sum())
    report["final_rows"] = len(df)
    logger.info("Clean: %s", report)
    return df, report

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    idx = df.index
    hdd_b = _hdd_base()
    cdd_b = _cdd_base()
    day_r = _day_rate()
    ngt_r = _night_rate()

    df["hour"] = idx.hour
    df["day_of_week"] = idx.dayofweek
    df["day_of_month"] = idx.day
    df["month"] = idx.month
    df["quarter"] = idx.quarter
    df["week_of_year"] = idx.isocalendar().week.astype(int)
    df["day_of_year"] = idx.dayofyear

    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    df["dow_sin"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
    df["dow_cos"] = np.cos(2 * np.pi * df["day_of_week"] / 7)
    df["doy_sin"] = np.sin(2 * np.pi * df["day_of_year"] / 365)
    df["doy_cos"] = np.cos(2 * np.pi * df["day_of_year"] / 365)

    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["is_holiday"] = df.apply(
        lambda r: int((r["month"], r["day_of_month"]) in _UA_HOLIDAYS), axis=1
    )
    mode = _cfg().object.operation_mode
    try:
        w_start, w_end = (int(x) for x in mode.split("-"))
    except ValueError:
        w_start, w_end = 8, 20

    df["is_working_hour"] = df["hour"].between(w_start, w_end - 1).astype(int)
    df["is_working_time"] = (
        (df["is_working_hour"] == 1) &
        (df["is_weekend"] == 0) &
        (df["is_holiday"] == 0)
    ).astype(int)
    df["is_open"] = df["is_working_time"]

    _season = {12: 1, 1: 1, 2: 1, 3: 2, 4: 2, 5: 2,
               6: 3, 7: 3, 8: 3, 9: 4, 10: 4, 11: 4}
    df["season"] = df["month"].map(_season)

    df["hdd"] = np.maximum(0, hdd_b - df["temperature_c"]) / 24
    df["cdd"] = np.maximum(0, df["temperature_c"] - cdd_b) / 24
    df["temp_dev"] = df["temperature_c"] - df["temperature_c"].mean()
    df["solar_irradiance_wm2"] = df["solar_irradiance_wm2"].clip(0)

    day_zones  = [z for z in _cfg().tariff.zones if z.zone_type == "day"]
    if day_zones:
        dz = day_zones[0]
        df["is_day_tariff"] = df["hour"].between(dz.start_time.hour,
                                                  dz.end_time.hour - 1).astype(int)
    else:
        df["is_day_tariff"] = df["hour"].between(7, 22).astype(int)
    df["tariff_price"] = np.where(df["is_day_tariff"], day_r, ngt_r)

    for lag in _lags():
        df[f"lag_{lag}"] = df[TARGET].shift(lag)

    for w in _windows():
        df[f"rolling_mean_{w}"] = (
            df[TARGET].shift(1).rolling(w, min_periods=w // 2).mean()
        )
        df[f"rolling_std_{w}"] = (
            df[TARGET].shift(1).rolling(w, min_periods=w // 2).std()
        )
    df["rolling_max_24"] = df[TARGET].shift(1).rolling(24, min_periods=12).max()
    df["rolling_min_24"] = df[TARGET].shift(1).rolling(24, min_periods=12).min()
    df["lag_168_delta"]  = df[TARGET].shift(1) - df[TARGET].shift(169)

    return df


def get_feature_columns() -> List[str]:
    temporal = ["hour", "day_of_week", "day_of_month", "month", "quarter",
                "week_of_year", "day_of_year"]
    cyclic = ["hour_sin", "hour_cos", "month_sin", "month_cos",
                "dow_sin",  "dow_cos",  "doy_sin",   "doy_cos"]
    binary = ["is_weekend", "is_holiday", "is_working_hour",
                "is_working_time", "season"]
    weather = ["temperature_c", "hdd", "cdd", "temp_dev",
                "solar_irradiance_wm2", "humidity_pct"]
    tariff = ["is_day_tariff", "tariff_price"]
    lags = [f"lag_{lag}" for lag in _lags()]
    rolling  = ([f"rolling_mean_{w}" for w in _windows()] +
                [f"rolling_std_{w}"  for w in _windows()] +
                ["rolling_max_24", "rolling_min_24", "lag_168_delta"])
    return temporal + cyclic + binary + weather + tariff + lags + rolling


def prepare_ml_dataset(
    df: pd.DataFrame,
    drop_na: bool = True,
) -> Tuple[pd.DataFrame, pd.Series]:
    features = [c for c in get_feature_columns() if c in df.columns]
    dataset = df[features + [TARGET]].copy()
    if drop_na:
        before = len(dataset)
        dataset = dataset.dropna()
        logger.info("Dropped %d NaN rows (%d remaining)",
                    before - len(dataset), len(dataset))
    return dataset[features], dataset[TARGET]


def train_test_split_temporal(
    df: pd.DataFrame,
    train_months: Optional[int] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    n_months = train_months or _cfg().forecasting.train_months
    cutoff = df.index.min() + pd.DateOffset(months=n_months)
    train = df[df.index < cutoff]
    test = df[df.index >= cutoff]
    logger.info(
        "Split -> train: %d rows (%s – %s)  test: %d rows (%s – %s)",
        len(train), train.index.min().date(), train.index.max().date(),
        len(test),  test.index.min().date(),  test.index.max().date(),
    )
    return train, test
