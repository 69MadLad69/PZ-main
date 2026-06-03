from __future__ import annotations

import logging
import math
import random
from datetime import datetime, timezone
from typing import Dict, List, Tuple

import numpy as np
import pytz

from backend.config.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s – %(message)s")
logger = logging.getLogger(__name__)
settings = get_settings()
cfg_gen = settings.generation
cfg_w = settings.weather
cfg_bat = settings.battery
cfg_sol = settings.solar
cfg_obj = settings.object

KYIV_TZ = pytz.timezone(cfg_w.timezone)
RNG = np.random.default_rng(cfg_gen.random_seed)

UA_HOLIDAYS_2025: set[Tuple[int, int]] = {
    (1, 1),
    (1, 7),
    (3, 8),
    (5, 1),
    (6, 8),
    (6, 28),
    (8, 24),
    (10, 14),
    (12, 25),
}

def _hourly_temp(base_temp_c: float, hour: int) -> float:
    amplitude = 4.0  # ±4°C diurnal swing
    phase = (hour - 14) * math.pi / 12
    return base_temp_c + amplitude * math.cos(phase)


def _solar_irradiance(month: int, hour: int, cloud_cover: float) -> float:
    monthly_peak = cfg_w.monthly_avg_irradiance_wm2[month - 1]
    daylight_center = 12.5
    daylight_half = 5.5 + 1.5 * math.sin((month - 6) * math.pi / 6)
    if abs(hour - daylight_center) >= daylight_half:
        return 0.0
    cosine = math.cos((hour - daylight_center) * math.pi / (2 * daylight_half))
    clear_sky = monthly_peak * max(0.0, cosine)
    cloud_factor = 1.0 - 0.75 * (cloud_cover / 100.0)
    noise = float(RNG.uniform(0.93, 1.07))
    return max(0.0, clear_sky * cloud_factor * noise)


def _cloud_cover(month: int) -> float:
    base = 57.5 - 17.5 * math.cos((month - 7) * math.pi / 6)
    return float(np.clip(base + RNG.normal(0, 8), 0, 100))


def generate_weather(timestamps: List[datetime]) -> List[dict]:
    logger.info("Generating weather data for %d timestamps", len(timestamps))
    records = []
    hdd_base = cfg_w.hdd_base_temp_c
    cdd_base = cfg_w.cdd_base_temp_c

    for ts in timestamps:
        month = ts.month
        base_temp = cfg_w.monthly_avg_temp_c[month - 1]
        doy = ts.timetuple().tm_yday
        temp_trend = 1.5 * math.sin((doy - 15) * 2 * math.pi / 365)
        hourly_temp = _hourly_temp(base_temp + temp_trend, ts.hour)
        hourly_temp += float(RNG.normal(0, 0.8))

        cloud = _cloud_cover(month)
        irradiance = _solar_irradiance(month, ts.hour, cloud)
        humidity = float(np.clip(RNG.normal(65, 15), 20, 100))
        wind = max(0.0, float(RNG.normal(3.5, 2.0)))
        precip = max(0.0, float(RNG.exponential(0.3)) if RNG.random() < 0.25 else 0.0)

        hdd = max(0.0, hdd_base - hourly_temp) / 24.0
        cdd = max(0.0, hourly_temp - cdd_base) / 24.0

        records.append(
            {
                "timestamp": ts,
                "temperature_c": round(hourly_temp, 2),
                "humidity_pct": round(humidity, 1),
                "wind_speed_ms": round(wind, 2),
                "solar_irradiance_wm2": round(irradiance, 2),
                "cloud_cover_pct": round(cloud, 1),
                "precipitation_mm": round(precip, 2),
                "hdd": round(hdd, 4),
                "cdd": round(cdd, 4),
                "data_source": "synthetic",
            }
        )
    return records

def _get_season(month: int) -> str:
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "autumn"


def _temperature_adjustment(temp_c: float) -> float:
    heat_thresh = cfg_gen.temperature.heating_threshold_c
    cool_thresh = cfg_gen.temperature.cooling_threshold_c
    heat_coeff = cfg_gen.temperature.heating_coeff_kw_per_c
    cool_coeff = cfg_gen.temperature.cooling_coeff_kw_per_c

    if temp_c < heat_thresh:
        return (heat_thresh - temp_c) * heat_coeff
    if temp_c > cool_thresh:
        return (temp_c - cool_thresh) * cool_coeff
    return 0.0


def generate_load_kw(
    ts: datetime,
    temp_c: float,
) -> float:
    hour = ts.hour
    month = ts.month
    weekday = ts.weekday()
    is_holiday = (month, ts.day) in UA_HOLIDAYS_2025

    profile = cfg_gen.hourly_load_profile
    base_factor = profile[hour]

    if is_holiday:
        day_factor = cfg_gen.day_type_factors.holiday
    elif weekday >= 5:
        day_factor = cfg_gen.day_type_factors.weekend
    else:
        day_factor = cfg_gen.day_type_factors.weekday

    season = _get_season(month)
    season_factor = cfg_gen.seasonal_factors[season]

    temp_adj_kw = _temperature_adjustment(temp_c)

    avg_kw = cfg_obj.avg_load_kw
    load_kw = avg_kw * base_factor * day_factor * season_factor + temp_adj_kw

    noise_lo = cfg_gen.fluctuation_min_pct
    noise_hi = cfg_gen.fluctuation_max_pct
    noise = float(RNG.uniform(1 - noise_hi, 1 + noise_hi))

    load_kw *= noise

    load_kw = np.clip(load_kw, cfg_obj.min_load_kw, cfg_obj.max_load_kw)
    return round(float(load_kw), 3)

def generate_solar(ts: datetime, irradiance_wm2: float, temp_c: float) -> dict:
    capacity_kw = cfg_sol.capacity_kw
    panel_eff = cfg_sol.panel_efficiency
    inv_eff = cfg_sol.inverter_efficiency

    temp_coeff = 1.0 - max(0.0, (temp_c - 25.0) * 0.004)

    dc_kw = (irradiance_wm2 / 1000.0) * capacity_kw * temp_coeff
    ac_kw = dc_kw * inv_eff
    ac_kw = float(np.clip(ac_kw, 0.0, capacity_kw))

    efficiency = (ac_kw / capacity_kw * 100.0) if capacity_kw > 0 else 0.0

    return {
        "timestamp": ts,
        "power_kw": round(ac_kw, 3),
        "energy_kwh": round(ac_kw, 3),  # 1-hour interval
        "irradiance_wm2": round(irradiance_wm2, 2),
        "temperature_c": round(temp_c, 2),
        "efficiency_pct": round(efficiency, 2),
        "dc_power_kw": round(dc_kw, 3),
        "curtailed_kwh": 0.0,
    }

def dispatch_battery(
    load_kw: float,
    solar_kw: float,
    soc_kwh: float,
    hour: int,
) -> Tuple[float, float, str]:
    cap = cfg_bat.capacity_kwh
    max_ch = cfg_bat.max_charge_kw
    max_dis = cfg_bat.max_discharge_kw
    ch_eff = cfg_bat.charge_efficiency
    dis_eff = cfg_bat.discharge_efficiency
    soc_min = cfg_bat.min_soc_pct / 100.0 * cap
    soc_max = cfg_bat.max_soc_pct / 100.0 * cap
    avg_load = cfg_obj.avg_load_kw

    net_load = load_kw - solar_kw
    if net_load < 0 and soc_kwh < soc_max:
        charge_kw = min(abs(net_load), max_ch, (soc_max - soc_kwh) / ch_eff)
        new_soc = soc_kwh + charge_kw * ch_eff
        return round(charge_kw, 3), round(new_soc, 3), "charging"

    is_night = hour >= 23 or hour < 7
    if is_night and soc_kwh < soc_max * 0.80:
        charge_kw = min(max_ch, (soc_max - soc_kwh) / ch_eff)
        new_soc = soc_kwh + charge_kw * ch_eff
        return round(charge_kw, 3), round(new_soc, 3), "charging"

    is_peak = 10 <= hour <= 17
    if is_peak and load_kw > avg_load and soc_kwh > soc_min:
        discharge_kw = min(max_dis, load_kw - avg_load, (soc_kwh - soc_min) * dis_eff)
        new_soc = soc_kwh - discharge_kw / dis_eff
        return round(-discharge_kw, 3), round(new_soc, 3), "discharging"

    return 0.0, round(soc_kwh, 3), "idle"


def split_load_to_meters(
    total_kw: float,
    meter_shares: Dict[int, float],
) -> Dict[int, float]:
    result = {1: total_kw}
    remainder = total_kw
    for meter_id, share in meter_shares.items():
        load = total_kw * share
        noise = float(RNG.uniform(0.95, 1.05))
        result[meter_id] = round(load * noise, 3)
        remainder -= load
    return result

def generate_all(year: int = 2025):
    from backend.config.config import get_settings
    s = get_settings()

    logger.info("Starting data generation for year %d", year)

    start = datetime(year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    timestamps = [
        start.replace(hour=0) + __import__("datetime").timedelta(hours=h)
        for h in range(s.generation.hours)
    ]
    ts_kyiv = [t.astimezone(KYIV_TZ) for t in timestamps]

    weather_records = generate_weather(ts_kyiv)
    logger.info("Weather: %d rows", len(weather_records))

    raw_shares = s.generation.meter_shares
    meter_shares = {int(k): float(v) for k, v in raw_shares.items()}

    measurement_records: Dict[int, List[dict]] = {i: [] for i in range(1, 7)}
    solar_records: List[dict] = []
    battery_records: List[dict] = []
    cumulative_kwh: Dict[int, float] = {i: 0.0 for i in range(1, 7)}

    soc_kwh = s.battery.initial_soc_pct / 100.0 * s.battery.capacity_kwh
    cycle_count = 0.0
    prev_soc_kwh = soc_kwh

    for i, (ts_utc, ts_local) in enumerate(zip(timestamps, ts_kyiv)):
        w = weather_records[i]
        temp_c = w["temperature_c"]
        irr = w["solar_irradiance_wm2"]

        total_kw = generate_load_kw(ts_local, temp_c)

        sol = generate_solar(ts_local, irr, temp_c)
        solar_records.append(sol)

        bat_power, soc_kwh, bat_mode = dispatch_battery(
            total_kw, sol["power_kw"], soc_kwh, ts_local.hour
        )

        if bat_mode == "discharging":
            cycle_count += abs(bat_power) / s.battery.capacity_kwh
        soc_pct = soc_kwh / s.battery.capacity_kwh * 100.0

        battery_records.append(
            {
                "timestamp": ts_utc,
                "soc_pct": round(soc_pct, 2),
                "soc_kwh": round(soc_kwh, 3),
                "power_kw": bat_power,
                "energy_kwh": round(abs(bat_power), 3),
                "mode": bat_mode,
                "temperature_c": round(temp_c + float(RNG.normal(0, 1.5)), 2),
                "cycle_count": round(cycle_count, 4),
                "voltage_v": round(48.0 + (soc_pct - 50) * 0.1, 2),
                "health_pct": 100.0,
            }
        )

        meter_loads = split_load_to_meters(total_kw, meter_shares)
        pf = float(np.clip(RNG.normal(0.92, 0.02), 0.80, 1.0))

        for meter_id in range(1, 7):
            if meter_id == 5:  # solar
                kw = sol["power_kw"]
            elif meter_id == 6:  # battery
                kw = abs(bat_power)
            else:
                kw = meter_loads.get(meter_id, total_kw)

            voltage = float(np.clip(RNG.normal(220.0, 3.0), 210, 235))
            current_a = (kw * 1000.0) / (voltage * pf * math.sqrt(3)) if kw > 0 else 0.0
            cumulative_kwh[meter_id] += kw
            measurement_records[meter_id].append(
                {
                    "meter_id": meter_id,
                    "timestamp": ts_utc,
                    "active_power_kw": kw,
                    "reactive_power_kvar": round(kw * math.tan(math.acos(pf)), 3),
                    "voltage_v": round(voltage, 1),
                    "current_a": round(current_a, 2),
                    "power_factor": round(pf, 3),
                    "energy_kwh": kw,  # 1h interval → kWh == kW
                    "cumulative_kwh": round(cumulative_kwh[meter_id], 3),
                    "quality_flag": 1,
                }
            )

    all_measurements = []
    for meter_id in range(1, 7):
        all_measurements.extend(measurement_records[meter_id])
    logger.info("Measurements: %d rows", len(all_measurements))

    baseline_records = _build_baseline(weather_records, measurement_records)
    logger.info("Baseline: %d rows", len(baseline_records))

    metrics_records = _build_daily_metrics(
        ts_kyiv, measurement_records, solar_records, battery_records, weather_records
    )
    logger.info("Metrics: %d rows", len(metrics_records))

    return {
        "weather": weather_records,
        "measurements": all_measurements,
        "solar": solar_records,
        "battery": battery_records,
        "baseline": baseline_records,
        "metrics": metrics_records,
    }

def _build_baseline(
    weather_records: List[dict],
    measurement_records: Dict[int, List[dict]],
) -> List[dict]:
    from collections import defaultdict
    import datetime as dt

    accum: Dict[tuple, List[float]] = defaultdict(list)
    temp_accum: Dict[tuple, List[float]] = defaultdict(list)

    for i, rec in enumerate(measurement_records[1]):
        ts = rec["timestamp"]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        local = ts.astimezone(KYIV_TZ)
        month = local.month
        hour = local.hour
        day_type = (
            "weekend" if local.weekday() >= 5 else "weekday"
        )
        key = (month, hour, day_type)
        accum[key].append(rec["energy_kwh"])
        temp_accum[key].append(weather_records[i]["temperature_c"])

    baselines = []
    for (month, hour, day_type), values in accum.items():
        arr = np.array(values)
        temps = np.array(temp_accum[(month, hour, day_type)])
        if len(arr) > 1:
            coeffs = np.polyfit(temps, arr, 1)
            temp_coeff = float(coeffs[0])
        else:
            temp_coeff = 0.0

        baselines.append(
            {
                "object_id": 1,
                "month": month,
                "hour_of_day": hour,
                "day_type": day_type,
                "expected_kwh": round(float(arr.mean()), 4),
                "std_dev_kwh": round(float(arr.std()), 4),
                "temperature_coeff": round(temp_coeff, 6),
                "sample_count": len(values),
            }
        )
    return baselines

def _build_daily_metrics(
    ts_kyiv, measurement_records, solar_records, battery_records, weather_records
) -> List[dict]:
    from collections import defaultdict
    import datetime as dt

    daily: Dict[str, dict] = defaultdict(lambda: {
        "kwh": [], "solar_kwh": [], "bat_ch_kwh": [], "bat_dis_kwh": [],
        "peak_kw": [], "cost_day": 0.0, "cost_night": 0.0,
    })

    for i, rec in enumerate(measurement_records[1]):
        ts = rec["timestamp"]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        local = ts.astimezone(KYIV_TZ)
        day_str = local.date().isoformat()
        d = daily[day_str]
        d["kwh"].append(rec["energy_kwh"])
        d["peak_kw"].append(rec["active_power_kw"])

        sol = solar_records[i]
        d["solar_kwh"].append(sol["energy_kwh"])

        bat = battery_records[i]
        if bat["mode"] == "charging":
            d["bat_ch_kwh"].append(bat["energy_kwh"])
        elif bat["mode"] == "discharging":
            d["bat_dis_kwh"].append(bat["energy_kwh"])

        hour = local.hour
        if 7 <= hour < 23:
            d["cost_day"] += rec["energy_kwh"] * 6.9
        else:
            d["cost_night"] += rec["energy_kwh"] * 5.6

    metrics = []
    for day_str, d in sorted(daily.items()):
        day_dt = datetime.fromisoformat(day_str + "T00:00:00+02:00")
        total_kwh = sum(d["kwh"])
        solar_kwh = sum(d["solar_kwh"])
        bat_ch = sum(d["bat_ch_kwh"])
        bat_dis = sum(d["bat_dis_kwh"])
        peak = max(d["peak_kw"]) if d["peak_kw"] else 0.0
        avg = np.mean(d["peak_kw"]) if d["peak_kw"] else 0.0
        area = cfg_obj.area_m2
        grid_import = max(0.0, total_kwh - solar_kwh - bat_dis)
        cost_total = d["cost_day"] + d["cost_night"]
        co2 = grid_import * 0.302

        metrics.append(
            {
                "object_id": 1,
                "date": day_dt,
                "total_consumption_kwh": round(total_kwh, 3),
                "solar_generation_kwh": round(solar_kwh, 3),
                "battery_charge_kwh": round(bat_ch, 3),
                "battery_discharge_kwh": round(bat_dis, 3),
                "grid_import_kwh": round(grid_import, 3),
                "grid_export_kwh": 0.0,
                "specific_consumption_kwh_m2": round(total_kwh / area, 5),
                "peak_demand_kw": round(peak, 3),
                "avg_demand_kw": round(float(avg), 3),
                "load_factor": round(float(avg) / peak if peak > 0 else 0, 4),
                "peak_to_avg_ratio": round(peak / float(avg) if avg > 0 else 0, 4),
                "self_consumption_ratio": round(
                    min(solar_kwh, total_kwh) / solar_kwh if solar_kwh > 0 else 0, 4
                ),
                "cost_uah": round(cost_total, 2),
                "cost_day_uah": round(d["cost_day"], 2),
                "cost_night_uah": round(d["cost_night"], 2),
                "co2_kg": round(co2, 3),
            }
        )
    return metrics
