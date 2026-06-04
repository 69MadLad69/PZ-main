from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from backend.config.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s – %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class EnergyMetrics:
    period_days: int
    total_load_kwh: float
    total_solar_kwh: float
    total_import_kwh: float
    total_export_kwh: float
    total_charge_kwh: float
    total_discharge_kwh: float
    direct_solar_kwh: float
    solar_coverage_pct: float   # % навантаження, покритого СЕС
    self_consumption_pct: float  # % генерації СЕС, спожитої на об'єкті
    self_sufficiency_pct: float  # % потреби, задоволеної без мережі
    battery_cycles: float


@dataclass
class EconomicMetrics:
    ems_cost_uah: float    # Вартість ЕЕ з EMS
    baseline_cost_uah:  float    # Вартість без EMS
    savings_uah: float    # Економія за симульований період
    savings_pct: float    # % економії
    annual_savings_uah: float    # Екстрапольована річна економія
    capex_total_uah: float
    simple_payback_years: float
    npv_uah: float
    irr_pct: float
    lcoe_uah_kwh: float    # LCOE (вартість кВт·год від СЕС+BESS)


class EconomicAnalyzer:
    def __init__(self):
        cfg = get_settings()
        eco = cfg.economics
        sol = cfg.solar
        bat = cfg.battery

        # Капітальні витрати (UAH)
        self.solar_capex = sol.capacity_kw * eco.solar_capex_uah_per_kw
        self.battery_capex = bat.capacity_kwh * eco.battery_capex_uah_per_kwh
        self.capex_total = self.solar_capex + self.battery_capex
        # Щорічні операційні витрати
        self.annual_opex = self.capex_total * eco.annual_opex_pct
        self.discount_rate = eco.discount_rate
        self.project_life = eco.project_life_years
        self.price_esc = eco.grid_price_escalation
        logger.info(
            "EconomicAnalyzer: CAPEX=%.0f UAH  solar=%.0f  bat=%.0f  r=%.0f%%  N=%d yr",
            self.capex_total, self.solar_capex, self.battery_capex,
            self.discount_rate * 100, self.project_life,
        )

    @staticmethod
    def compute_energy_metrics(df: pd.DataFrame) -> EnergyMetrics:
        days = max(1, len(df) // 24)
        total_load = df["load_kwh"].sum()
        total_solar = df["solar_kwh"].sum()
        total_import = df["import_kwh"].sum()
        total_export = df["export_kwh"].sum()
        total_charge = df["charge_kwh"].sum()
        total_disch = df["discharge_kwh"].sum()
        direct_solar = df["direct_solar_kwh"].sum() if "direct_solar_kwh" in df.columns else 0.0

        solar_used = total_solar - total_export
        non_grid = direct_solar + total_disch

        battery_cycles = (total_charge + total_disch) / (2 * 25.0)

        return EnergyMetrics(
            period_days = days,
            total_load_kwh = round(total_load, 2),
            total_solar_kwh = round(total_solar, 2),
            total_import_kwh = round(total_import, 2),
            total_export_kwh = round(total_export, 2),
            total_charge_kwh = round(total_charge, 2),
            total_discharge_kwh = round(total_disch, 2),
            direct_solar_kwh = round(direct_solar, 2),
            solar_coverage_pct = round(solar_used / total_load * 100 if total_load > 0 else 0, 1),
            self_consumption_pct = round(solar_used / total_solar * 100 if total_solar > 0 else 0, 1),
            self_sufficiency_pct = round(non_grid / total_load * 100 if total_load > 0 else 0, 1),
            battery_cycles = round(battery_cycles, 2),
        )

    @staticmethod
    def baseline_cost(df: pd.DataFrame) -> float:
        cfg = get_settings()
        day_r = next(z.rate_uah_kwh for z in cfg.tariff.zones if z.zone_type=="day")
        night_r = next(z.rate_uah_kwh for z in cfg.tariff.zones if z.zone_type=="night")
        day_h = next(z.start_time.hour for z in cfg.tariff.zones if z.zone_type=="day")
        end_h = next(z.end_time.hour  for z in cfg.tariff.zones if z.zone_type=="day")

        def rate(h):
            return day_r if day_h <= h < end_h else night_r

        total = 0.0
        for ts, row in df.iterrows():
            h = ts.hour if hasattr(ts, 'hour') else pd.Timestamp(ts).hour
            total += row["load_kwh"] * rate(h)
        return round(total, 2)

    def compute_economic_metrics(
        self,
        df: pd.DataFrame,
        annual_solar_kwh: Optional[float] = None,
    ) -> EconomicMetrics:
        days = max(1, len(df) // 24)
        ems_cost = round(df["cost_uah"].sum(), 2)
        no_ems_cost = self.baseline_cost(df)
        savings_period = round(no_ems_cost - ems_cost, 2)
        savings_pct = round(savings_period / no_ems_cost * 100 if no_ems_cost > 0 else 0, 1)
        annual_savings = round(savings_period / days * 365, 2)

        npv = self._npv(annual_savings)
        irr = self._irr(annual_savings)
        payback = round(self.capex_total / annual_savings, 1) if annual_savings > 0 else 999.9
        solar_kwh = annual_solar_kwh or (df["solar_kwh"].sum() / days * 365)
        lcoe = self._lcoe(solar_kwh)

        return EconomicMetrics(
            ems_cost_uah = ems_cost,
            baseline_cost_uah = no_ems_cost,
            savings_uah = savings_period,
            savings_pct = savings_pct,
            annual_savings_uah = annual_savings,
            capex_total_uah = round(self.capex_total, 0),
            simple_payback_years = payback,
            npv_uah = npv,
            irr_pct = irr,
            lcoe_uah_kwh = lcoe,
        )

    def _cash_flows(self, annual_savings: float) -> np.ndarray:
        cf = [-self.capex_total]
        for t in range(1, self.project_life + 1):
            cf_t = annual_savings * (1 + self.price_esc)**(t-1) - self.annual_opex
            cf.append(cf_t)
        return np.array(cf)

    def _npv(self, annual_savings: float) -> float:
        cf = self._cash_flows(annual_savings)
        r  = self.discount_rate
        npv = sum(cf[t] / (1 + r)**t for t in range(len(cf)))
        return round(npv, 0)

    def _irr(self, annual_savings: float) -> float:
        cf = self._cash_flows(annual_savings)
        try:
            roots = np.roots(cf[::-1])
            real_roots = roots[np.isreal(roots)].real
            irr_candidates = real_roots[real_roots > 0] - 1
            irr = float(irr_candidates[irr_candidates > 0].min()) if len(irr_candidates) > 0 else 0.0
            return round(irr * 100, 1)
        except Exception:
            lo, hi = 0.0, 5.0
            for _ in range(50):
                mid = (lo + hi) / 2
                cf_arr = self._cash_flows(annual_savings)
                npv_mid = sum(cf_arr[t]/(1+mid)**t for t in range(len(cf_arr)))
                if npv_mid > 0:
                    lo = mid
                else:
                    hi = mid
            return round((lo + hi) / 2 * 100, 1)

    def _lcoe(self, annual_solar_kwh: float) -> float:
        if annual_solar_kwh <= 0:
            return 0.0
        r = self.discount_rate
        N = self.project_life
        total_pv_cost = self.capex_total + sum(self.annual_opex / (1+r)**t
                                                  for t in range(1, N+1))
        total_pv_energy = sum(annual_solar_kwh / (1+r)**t
                              for t in range(1, N+1))
        return round(total_pv_cost / total_pv_energy, 2) if total_pv_energy > 0 else 0.0
