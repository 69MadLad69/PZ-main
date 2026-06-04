from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import List, Optional

from backend.config.config import get_settings

logger = logging.getLogger(__name__)

G_REF = 1000.0
T_REF = 25.0
GAMMA = -0.004 
NOCT_C = 0.030


@dataclass
class SolarState:
    timestamp: object
    irradiance_wm2: float = 0.0
    temperature_c: float = 25.0
    cell_temp_c: float = 25.0
    dc_power_kw: float = 0.0
    ac_power_kw: float = 0.0
    energy_kwh: float = 0.0
    efficiency_pct: float = 0.0
    curtailed_kwh: float = 0.0


class SolarPlant:
    def __init__(self, year_of_operation: int = 1):
        cfg = get_settings().solar
        self.capacity_kw = cfg.capacity_kw
        self.panel_efficiency = cfg.panel_efficiency
        self.inverter_efficiency = cfg.inverter_efficiency
        self.degradation_rate = cfg.degradation_rate
        self.age_factor = (1 - self.degradation_rate) ** max(0, year_of_operation - 1)
        self.history: List[SolarState] = []
        logger.info("SolarPlant init: cap=%.1f kW  inv_eff=%.2f  age=%.3f",
                    self.capacity_kw, self.inverter_efficiency, self.age_factor)

    def compute(
        self,
        timestamp,
        irradiance_wm2: float,
        temperature_c: float,
        max_output_kw: Optional[float] = None,
    ) -> SolarState:
        g = max(0.0, irradiance_wm2)
        t_amb = temperature_c

        t_cell = t_amb + g * NOCT_C

        eta_temp = 1.0 + GAMMA * (t_cell - T_REF)
        eta_temp = max(0.5, eta_temp)

        p_dc = (g / G_REF) * self.capacity_kw * eta_temp * self.age_factor
        p_dc = max(0.0, min(p_dc, self.capacity_kw))

        p_ac = p_dc * self.inverter_efficiency
        p_ac = max(0.0, p_ac)

        curtailed = 0.0
        if max_output_kw is not None and p_ac > max_output_kw:
            curtailed = p_ac - max_output_kw
            p_ac = max_output_kw

        eff = (p_ac / self.capacity_kw * 100.0) if self.capacity_kw > 0 else 0.0

        state = SolarState(
            timestamp = timestamp,
            irradiance_wm2 = round(g, 2),
            temperature_c = round(t_amb, 2),
            cell_temp_c = round(t_cell, 2),
            dc_power_kw = round(p_dc, 3),
            ac_power_kw = round(p_ac, 3),
            energy_kwh = round(p_ac, 3),   # 1-годинний крок → кВт = кВт·год
            efficiency_pct  = round(eff, 2),
            curtailed_kwh = round(curtailed, 3),
        )
        self.history.append(state)
        return state

    def daily_energy_kwh(self) -> float:
        return round(sum(s.energy_kwh for s in self.history), 3)

    def reset(self) -> None:
        self.history.clear()
