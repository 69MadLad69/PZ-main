from __future__ import annotations
from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class PaginationMeta(BaseModel):
    total: int; page: int; page_size: int; pages: int

class PaginatedResponse(BaseModel):
    data: list; meta: PaginationMeta

class HourlyConsumption(BaseModel):
    timestamp: datetime
    energy_kwh: float
    active_power_kw: float
    tariff_zone: Optional[str] = None
    cost_uah: Optional[float] = None

class DailyConsumption(BaseModel):
    day: date
    total_kwh: float
    peak_kw: float
    avg_kw: float
    cost_uah: float
    day_type: str

class MonthlyConsumption(BaseModel):
    year: int; month: int
    total_kwh: float
    day_kwh: float
    night_kwh: float
    total_cost_uah: float
    peak_kw: float
    avg_kw: float

class TariffZoneSummary(BaseModel):
    tariff_zone: str
    total_kwh: float
    total_uah: float
    avg_kw: float
    hours: int

class ForecastPoint(BaseModel):
    timestamp: datetime
    predicted_kwh: float
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None
    tariff_zone: Optional[str] = None
    cost_uah: Optional[float] = None

class ForecastMetrics(BaseModel):
    r2: float = Field(..., alias="R2")
    rmse: float = Field(..., alias="RMSE")
    mae: float = Field(..., alias="MAE")
    mape: float = Field(..., alias="MAPE")
    model_name: str
    class Config: populate_by_name = True

class ForecastSummary(BaseModel):
    monthly_kwh: float
    monthly_cost_uah: float
    solar_saving_uah: float
    specific_kwh_m2: float
    metrics: Optional[ForecastMetrics] = None

class EMSStatus(BaseModel):
    run_id: str
    started_at: Optional[datetime]
    strategy: str
    status: str

class EMSStep(BaseModel):
    timestamp: datetime
    solar_kwh: float
    load_kwh: float
    soc_pct: float
    soc_kwh: float
    charge_kwh: float
    discharge_kwh: float
    import_kwh: float
    export_kwh: float
    tariff_zone: str
    rate_uah_kwh: float
    cost_uah: float

class EnergyMetricsSchema(BaseModel):
    period_days: int
    total_load_kwh: float
    total_solar_kwh: float
    total_import_kwh: float
    total_export_kwh: float
    total_charge_kwh: float
    total_discharge_kwh: float
    solar_coverage_pct: float
    self_consumption_pct: float
    self_sufficiency_pct: float
    battery_cycles: float

class EconomicMetricsSchema(BaseModel):
    ems_cost_uah: float
    baseline_cost_uah: float
    savings_uah: float
    savings_pct: float
    annual_savings_uah: float
    capex_total_uah: float
    simple_payback_years: float
    npv_uah: float
    irr_pct: float
    lcoe_uah_kwh: float

class EnergyFlowSchema(BaseModel):
    solar_to_load: float
    solar_to_battery: float
    solar_to_grid: float
    battery_to_load: float
    grid_to_load: float
    grid_to_battery: float

class KPIValue(BaseModel):
    value: float
    unit: str
    change_pct: Optional[float] = None
    trend: Optional[str] = None

class DashboardSummary(BaseModel):
    current_consumption_kw: KPIValue
    today_consumption_kwh: KPIValue
    solar_generation_kwh: KPIValue
    battery_soc_pct: KPIValue
    cost_savings_uah: KPIValue
    co2_reduction_kg: KPIValue
    solar_coverage_pct: KPIValue
    month_consumption_kwh: KPIValue
    last_updated: datetime

class ReportRequest(BaseModel):
    start_date: date
    end_date: date
    report_type: str = "full"
    format: str = "csv"
    include_charts: bool = True

class ReportResponse(BaseModel):
    report_id: str
    status: str
    download_url: Optional[str] = None
    created_at: datetime
