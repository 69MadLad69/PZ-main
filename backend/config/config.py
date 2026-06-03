from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

CONFIG_DIR = Path(__file__).parent
SETTINGS_FILE = CONFIG_DIR / "settings.yaml"

def _resolve_env_vars(value: Any) -> Any:
    if isinstance(value, str):
        pattern = re.compile(r"\$\{(\w+)(?::([^}]*))?\}")
        def replacer(m: re.Match) -> str:
            var_name, default = m.group(1), m.group(2) or ""
            return os.environ.get(var_name, default)
        return pattern.sub(replacer, value)
    if isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env_vars(i) for i in value]
    return value


def _load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return _resolve_env_vars(raw)


class DatabaseConfig(BaseModel):
    host: str = "localhost"
    port: int = 5432
    name: str = "ems_db"
    user: str = "ems_user"
    password: str = "ems_password"
    pool_size: int = 10
    max_overflow: int = 20
    echo: bool = False

    @property
    def url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )

    @property
    def async_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )


class ObjectConfig(BaseModel):
    name: str
    type: str
    location: str
    area_m2: float
    max_power_kw: float
    meter_count: int
    operation_mode: str
    avg_load_kw: float
    min_load_kw: float
    max_load_kw: float


class SolarConfig(BaseModel):
    name: str
    capacity_kw: float
    panel_efficiency: float
    inverter_efficiency: float
    degradation_rate: float
    tilt_angle_deg: float
    azimuth_deg: float


class BatteryConfig(BaseModel):
    name: str
    capacity_kwh: float
    max_charge_kw: float
    max_discharge_kw: float
    charge_efficiency: float
    discharge_efficiency: float
    min_soc_pct: float
    max_soc_pct: float
    initial_soc_pct: float


from datetime import time as Time

class TariffZoneConfig(BaseModel):
    name: str
    zone_type: str
    start_time: Time
    end_time: Time
    rate_uah_kwh: float


class TariffConfig(BaseModel):
    name: str
    type: str
    currency: str
    zones: list[TariffZoneConfig]


class WeatherConfig(BaseModel):
    location: str
    latitude: float
    longitude: float
    timezone: str
    hdd_base_temp_c: float
    cdd_base_temp_c: float
    year: int
    monthly_avg_temp_c: list[float]
    monthly_avg_irradiance_wm2: list[float]


class MeterConfig(BaseModel):
    id: int
    name: str
    type: str
    level: int
    description: str
    location: str


class DayTypeFactors(BaseModel):
    weekday: float
    weekend: float
    holiday: float


class TemperatureConfig(BaseModel):
    heating_threshold_c: float
    cooling_threshold_c: float
    heating_coeff_kw_per_c: float
    cooling_coeff_kw_per_c: float


class GenerationConfig(BaseModel):
    year: int
    hours: int
    random_seed: int
    fluctuation_min_pct: float
    fluctuation_max_pct: float
    day_type_factors: DayTypeFactors
    hourly_load_profile: list[float]
    seasonal_factors: dict[str, float]
    temperature: TemperatureConfig
    meter_shares: dict[str, float]


class AnalyticsConfig(BaseModel):
    anomaly_threshold_pct: float
    baseline_window_days: int
    efficiency_target_kwh_m2_year: float
    report_timezone: str


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: str = "logs/ems.log"

class Settings(BaseModel):
    database: DatabaseConfig
    object: ObjectConfig
    solar: SolarConfig
    battery: BatteryConfig
    tariff: TariffConfig
    weather: WeatherConfig
    meters: list[MeterConfig]
    generation: GenerationConfig
    analytics: AnalyticsConfig
    logging: LoggingConfig


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    data = _load_yaml(SETTINGS_FILE)
    return Settings(**data)


settings = get_settings()
