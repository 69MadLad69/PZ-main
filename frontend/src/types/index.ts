// frontend/src/types/index.ts
export interface KPIValue {
  value: number;
  unit: string;
  change_pct?: number;
  trend?: 'up' | 'down' | 'flat';
}

export interface DashboardSummary {
  current_consumption_kw: KPIValue;
  today_consumption_kwh: KPIValue;
  solar_generation_kwh: KPIValue;
  battery_soc_pct: KPIValue;
  cost_savings_uah: KPIValue;
  co2_reduction_kg: KPIValue;
  solar_coverage_pct: KPIValue;
  month_consumption_kwh: KPIValue;
  last_updated: string;
}

export interface MonthlyConsumption {
  year: number; month: number;
  total_kwh: number; day_kwh: number; night_kwh: number;
  total_cost_uah: number; peak_kw: number; avg_kw: number;
}

export interface DailyConsumption {
  day: string; total_kwh: number; peak_kw: number;
  avg_kw: number; cost_uah: number; day_type: string;
}

export interface EMSStep {
  timestamp: string;
  solar_kwh: number; load_kwh: number; soc_pct: number;
  charge_kwh: number; discharge_kwh: number;
  import_kwh: number; export_kwh: number;
  tariff_zone: string; cost_uah: number;
}

export interface EnergyMetrics {
  period_days: number;
  total_load_kwh: number; total_solar_kwh: number;
  total_import_kwh: number; total_export_kwh: number;
  solar_coverage_pct: number; self_consumption_pct: number;
  self_sufficiency_pct: number; battery_cycles: number;
}

export interface EconomicMetrics {
  ems_cost_uah: number; baseline_cost_uah: number;
  savings_uah: number; savings_pct: number; annual_savings_uah: number;
  capex_total_uah: number; simple_payback_years: number;
  npv_uah: number; irr_pct: number; lcoe_uah_kwh: number;
}

export interface EnergyFlow {
  solar_to_load: number; solar_to_battery: number; solar_to_grid: number;
  battery_to_load: number; grid_to_load: number; grid_to_battery: number;
}

export interface ForecastSummary {
  monthly_kwh: number; monthly_cost_uah: number;
  solar_saving_uah: number; specific_kwh_m2: number;
  metrics?: { R2: number; RMSE: number; MAE: number; MAPE: number; model_name: string; };
}
