from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.app.database import Base

class ObjectType(str, enum.Enum):
    medical_center = "medical_center"
    polyclinic = "polyclinic"
    office = "office"
    industrial = "industrial"
    residential = "residential"
    retail = "retail"


class MeterType(str, enum.Enum):
    main = "main"
    zone = "zone"
    solar = "solar"
    battery = "battery"
    emergency = "emergency"


class DayType(str, enum.Enum):
    weekday = "weekday"
    weekend = "weekend"
    holiday = "holiday"


class TariffZoneType(str, enum.Enum):
    day = "day"
    night = "night"
    peak = "peak"
    off_peak = "off_peak"


class BatteryMode(str, enum.Enum):
    charging = "charging"
    discharging = "discharging"
    idle = "idle"

class EnergyObject(Base):
    __tablename__ = "objects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    type = Column(Enum(ObjectType), nullable=False)
    location = Column(String(300), nullable=False)
    area_m2 = Column(Float, nullable=False)
    max_power_kw = Column(Float, nullable=False)
    meter_count = Column(SmallInteger, nullable=False)
    operation_mode = Column(String(50), nullable=False, default="24/7")
    avg_load_kw = Column(Float, nullable=False)
    min_load_kw = Column(Float, nullable=False)
    max_load_kw = Column(Float, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    meters = relationship("Meter", back_populates="object", cascade="all, delete-orphan")
    baseline = relationship("BaselineConsumption", back_populates="object", cascade="all, delete-orphan")
    efficiency_metrics = relationship("EnergyEfficiencyMetric", back_populates="object", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("min_load_kw <= avg_load_kw", name="ck_min_le_avg"),
        CheckConstraint("avg_load_kw <= max_load_kw", name="ck_avg_le_max"),
        CheckConstraint("area_m2 > 0", name="ck_area_positive"),
    )

    def __repr__(self) -> str:
        return f"<EnergyObject id={self.id} name={self.name!r}>"

class Meter(Base):
    __tablename__ = "meters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    object_id = Column(Integer, ForeignKey("objects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    type = Column(Enum(MeterType), nullable=False)
    level = Column(SmallInteger, nullable=False, comment="1=building, 2=zone, 3=equipment")
    location = Column(String(300))
    description = Column(Text)
    serial_number = Column(String(100))
    is_active = Column(Boolean, default=True, nullable=False)
    installed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    object = relationship("EnergyObject", back_populates="meters")
    measurements = relationship("Measurement", back_populates="meter", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("level IN (1, 2, 3)", name="ck_meter_level"),
        Index("ix_meters_object_id", "object_id"),
        Index("ix_meters_type", "type"),
    )

    def __repr__(self) -> str:
        return f"<Meter id={self.id} name={self.name!r} level={self.level}>"

class Measurement(Base):
    __tablename__ = "measurements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    meter_id = Column(Integer, ForeignKey("meters.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    active_power_kw = Column(Float, nullable=False)
    reactive_power_kvar = Column(Float, default=0.0)
    voltage_v = Column(Float, default=220.0)
    current_a = Column(Float)
    power_factor = Column(Float, default=0.92)
    energy_kwh = Column(Float, nullable=False, comment="Incremental kWh this hour")
    cumulative_kwh = Column(Float, comment="Meter totalizer reading")
    quality_flag = Column(SmallInteger, default=1, comment="1=good, 0=estimated, -1=bad")

    meter = relationship("Meter", back_populates="measurements")

    __table_args__ = (
        UniqueConstraint("meter_id", "timestamp", name="uq_measurement_meter_ts"),
        Index("ix_measurements_meter_ts", "meter_id", "timestamp"),
        Index("ix_measurements_timestamp", "timestamp"),
        CheckConstraint("active_power_kw >= 0", name="ck_power_non_negative"),
        CheckConstraint("power_factor BETWEEN 0 AND 1", name="ck_pf_range"),
        CheckConstraint("quality_flag IN (-1, 0, 1)", name="ck_quality_flag"),
    )

    def __repr__(self) -> str:
        return f"<Measurement meter={self.meter_id} ts={self.timestamp} kw={self.active_power_kw}>"

class WeatherData(Base):
    __tablename__ = "weather_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, unique=True)
    temperature_c = Column(Float, nullable=False)
    humidity_pct = Column(Float)
    wind_speed_ms = Column(Float)
    solar_irradiance_wm2 = Column(Float, nullable=False, default=0.0)
    cloud_cover_pct = Column(Float, default=0.0)
    precipitation_mm = Column(Float, default=0.0)
    hdd = Column(Float, nullable=False, comment="Heating Degree Day (base 18°C)")
    cdd = Column(Float, nullable=False, comment="Cooling Degree Day (base 22°C)")
    data_source = Column(String(100), default="synthetic")

    __table_args__ = (
        Index("ix_weather_timestamp", "timestamp"),
        CheckConstraint("humidity_pct BETWEEN 0 AND 100", name="ck_humidity"),
        CheckConstraint("cloud_cover_pct BETWEEN 0 AND 100", name="ck_cloud_cover"),
        CheckConstraint("solar_irradiance_wm2 >= 0", name="ck_irradiance"),
    )

    def __repr__(self) -> str:
        return f"<WeatherData ts={self.timestamp} t={self.temperature_c}°C>"

class TariffZone(Base):
    __tablename__ = "tariff_zones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    tariff_name = Column(String(200), nullable=False)
    zone_type = Column(Enum(TariffZoneType), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    rate_uah_kwh = Column(Float, nullable=False)
    valid_from = Column(DateTime(timezone=True))
    valid_to = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("rate_uah_kwh > 0", name="ck_rate_positive"),
    )

    def __repr__(self) -> str:
        return f"<TariffZone {self.zone_type} {self.start_hour}–{self.end_hour}h @ {self.rate_uah_kwh} UAH>"

class BaselineConsumption(Base):
    __tablename__ = "baseline_consumption"

    id = Column(Integer, primary_key=True, autoincrement=True)
    object_id = Column(Integer, ForeignKey("objects.id", ondelete="CASCADE"), nullable=False)
    month = Column(SmallInteger, nullable=False)
    hour_of_day = Column(SmallInteger, nullable=False)
    day_type = Column(Enum(DayType), nullable=False)
    expected_kwh = Column(Float, nullable=False)
    std_dev_kwh = Column(Float, default=0.0)
    temperature_coeff = Column(Float, default=0.0, comment="kWh per degree C deviation")
    sample_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    object = relationship("EnergyObject", back_populates="baseline")

    __table_args__ = (
        UniqueConstraint("object_id", "month", "hour_of_day", "day_type", name="uq_baseline"),
        Index("ix_baseline_object_month", "object_id", "month"),
        CheckConstraint("month BETWEEN 1 AND 12", name="ck_month"),
        CheckConstraint("hour_of_day BETWEEN 0 AND 23", name="ck_hour"),
        CheckConstraint("expected_kwh >= 0", name="ck_expected_positive"),
    )

    def __repr__(self) -> str:
        return f"<Baseline obj={self.object_id} m={self.month} h={self.hour_of_day} {self.day_type}>"

class EnergyEfficiencyMetric(Base):
    __tablename__ = "energy_efficiency_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    object_id = Column(Integer, ForeignKey("objects.id", ondelete="CASCADE"), nullable=False)
    date = Column(DateTime(timezone=True), nullable=False, comment="Date (midnight)")
    total_consumption_kwh = Column(Float, nullable=False)
    solar_generation_kwh = Column(Float, default=0.0)
    battery_charge_kwh = Column(Float, default=0.0)
    battery_discharge_kwh = Column(Float, default=0.0)
    grid_import_kwh = Column(Float, default=0.0)
    grid_export_kwh = Column(Float, default=0.0)
    specific_consumption_kwh_m2 = Column(Float, nullable=False)
    peak_demand_kw = Column(Float)
    avg_demand_kw = Column(Float)
    load_factor = Column(Float, comment="avg/peak demand ratio")
    peak_to_avg_ratio = Column(Float)
    self_consumption_ratio = Column(Float, comment="Solar used on-site / total generation")
    cost_uah = Column(Float)
    cost_day_uah = Column(Float)
    cost_night_uah = Column(Float)
    co2_kg = Column(Float, comment="Estimated CO₂ (0.302 kg/kWh grid factor)")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    object = relationship("EnergyObject", back_populates="efficiency_metrics")

    __table_args__ = (
        UniqueConstraint("object_id", "date", name="uq_metrics_object_date"),
        Index("ix_metrics_object_date", "object_id", "date"),
    )

    def __repr__(self) -> str:
        return f"<EnergyMetric obj={self.object_id} date={self.date} kwh={self.total_consumption_kwh}>"

class SolarGeneration(Base):
    __tablename__ = "solar_generation"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, unique=True)
    power_kw = Column(Float, nullable=False, default=0.0)
    energy_kwh = Column(Float, nullable=False, default=0.0)
    irradiance_wm2 = Column(Float, nullable=False, default=0.0)
    temperature_c = Column(Float)
    efficiency_pct = Column(Float)
    curtailed_kwh = Column(Float, default=0.0)
    dc_power_kw = Column(Float)

    __table_args__ = (
        Index("ix_solar_timestamp", "timestamp"),
        CheckConstraint("power_kw >= 0", name="ck_solar_power"),
        CheckConstraint("energy_kwh >= 0", name="ck_solar_energy"),
        CheckConstraint("irradiance_wm2 >= 0", name="ck_irradiance2"),
    )

    def __repr__(self) -> str:
        return f"<SolarGeneration ts={self.timestamp} kw={self.power_kw}>"

class BatteryState(Base):
    __tablename__ = "battery_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, unique=True)
    soc_pct = Column(Float, nullable=False, comment="State of charge 0–100%")
    soc_kwh = Column(Float, nullable=False)
    power_kw = Column(Float, nullable=False, comment="+charge / -discharge")
    energy_kwh = Column(Float, nullable=False, comment="Absolute energy this hour")
    mode = Column(Enum(BatteryMode), nullable=False)
    temperature_c = Column(Float)
    cycle_count = Column(Float, default=0.0, comment="Cumulative full cycles")
    voltage_v = Column(Float)
    health_pct = Column(Float, default=100.0, comment="State of health")

    __table_args__ = (
        Index("ix_battery_timestamp", "timestamp"),
        CheckConstraint("soc_pct BETWEEN 0 AND 100", name="ck_soc_range"),
        CheckConstraint("health_pct BETWEEN 0 AND 100", name="ck_health_range"),
    )

    def __repr__(self) -> str:
        return f"<BatteryState ts={self.timestamp} soc={self.soc_pct}% mode={self.mode}>"

__all__ = [
    "Base",
    "EnergyObject",
    "Meter",
    "Measurement",
    "WeatherData",
    "TariffZone",
    "BaselineConsumption",
    "EnergyEfficiencyMetric",
    "SolarGeneration",
    "BatteryState",
    # enums
    "ObjectType",
    "MeterType",
    "DayType",
    "TariffZoneType",
    "BatteryMode",
]
