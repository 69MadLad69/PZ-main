from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd

from backend.app.simulation.components.battery import BatteryStorage
from backend.app.simulation.components.grid    import GridConnection
from backend.app.simulation.components.solar   import SolarPlant
from backend.config.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s – %(message)s")
logger = logging.getLogger(__name__)

@dataclass
class StepResult:
    timestamp: object
    solar_kwh: float = 0.0
    load_kwh: float = 0.0
    forecast_kwh: float = 0.0
    soc_pct: float = 50.0
    soc_kwh: float = 12.5
    charge_kwh: float = 0.0
    discharge_kwh: float = 0.0
    import_kwh: float = 0.0
    export_kwh: float = 0.0
    tariff_zone: str = "day"
    rate_uah_kwh: float = 6.9
    cost_uah: float = 0.0
    direct_solar_kwh: float = 0.0
    grid_covered_pct: float = 100.0
    solar_covered_pct:float = 0.0
    decision: str = ""


class TariffOptimizer:
    def __init__(self, battery: BatteryStorage, grid: GridConnection):
        self.battery = battery
        self.grid = grid
        cfg_sim = get_settings().simulation
        self._op_min = cfg_sim.soc_min_pct / 100.0
        self._op_max = cfg_sim.soc_max_pct / 100.0
        cfg_bat = get_settings().battery
        self._max_ch = cfg_bat.max_charge_kw
        self._max_dch = cfg_bat.max_discharge_kw

    def night_charge_kw(self, hour: int, soc: float) -> float:
        _, rate = self.grid.get_rate(hour)
        if rate > 6.0:
            return 0.0
        if soc >= self._op_max * 0.95:
            return 0.0
        return self._max_ch

    def should_discharge(
        self, hour: int, soc: float, net_deficit_kwh: float,
        forecast_next_6h: Optional[List[float]] = None,
    ) -> bool:
        if soc <= self._op_min:
            return False
        _, rate = self.grid.get_rate(hour)
        if rate < 6.0:
            if soc < self._op_min + 0.05 and net_deficit_kwh > 5:
                return True
            return False

        if net_deficit_kwh <= 0:
            return False

        if forecast_next_6h:
            max_upcoming = max(forecast_next_6h)
            avg_upcoming = sum(forecast_next_6h) / len(forecast_next_6h)
            battery_kwh  = soc * self.battery.capacity_kwh
            if max_upcoming > 20 and battery_kwh < 5:
                return False
        return True


class EMSController:
    def __init__(
        self,
        solar: SolarPlant,
        battery: BatteryStorage,
        grid: GridConnection,
    ):
        self.solar = solar
        self.battery = battery
        self.grid = grid
        self.optimizer = TariffOptimizer(battery, grid)
        self._steps: List[StepResult] = []

    def step(
        self,
        timestamp,
        irradiance_wm2: float,
        temperature_c: float,
        load_kwh: float,
        forecast_kwh: float = 0.0,
        forecast_next_6h: Optional[List[float]] = None,
    ) -> StepResult:
        hour = timestamp.hour if hasattr(timestamp, 'hour') else pd.Timestamp(timestamp).hour
        zone, rate = self.grid.get_rate(hour)

        self.battery.update_state(timestamp)

        solar_state = self.solar.compute(timestamp, irradiance_wm2, temperature_c)
        solar_kwh = solar_state.energy_kwh

        direct_solar = min(solar_kwh, load_kwh)
        balance = solar_kwh - load_kwh

        charge_kwh = 0.0
        discharge_kwh = 0.0
        import_kwh = 0.0
        export_kwh = 0.0
        decision_parts: list[str] = []

        if balance >= 0:
            surplus = balance
            decision_parts.append(f"solar>{load_kwh:.1f}")
            charged, _ = self.battery.charge(surplus, timestamp)
            charge_kwh = charged
            export_kwh = max(0.0, surplus - charged)
            if export_kwh > 0:
                decision_parts.append(f"export={export_kwh:.1f}")
            if charged > 0:
                decision_parts.append(f"chg={charged:.1f}")

        else:
            deficit = abs(balance)
            soc = self.battery.get_soc()

            night_ch_kw = self.optimizer.night_charge_kw(hour, soc)
            if night_ch_kw > 0:
                night_charged, _ = self.battery.charge(night_ch_kw, timestamp)
                charge_kwh += night_charged
                import_kwh += night_charged
                decision_parts.append(f"night_chg={night_charged:.1f}")

            soc_after_charge = self.battery.get_soc()
            if self.optimizer.should_discharge(hour, soc_after_charge, deficit,
                                               forecast_next_6h):
                discharged, _ = self.battery.discharge(deficit, timestamp)
                discharge_kwh = discharged
                remaining_deficit = max(0.0, deficit - discharged)
                import_kwh += remaining_deficit
                decision_parts.append(f"dch={discharged:.1f}")
                if remaining_deficit > 0:
                    decision_parts.append(f"imp={remaining_deficit:.1f}")
            else:
                import_kwh += deficit
                decision_parts.append(f"imp={deficit:.1f}")

        grid_step = self.grid.transact(timestamp, import_kwh, export_kwh, hour)

        grid_covered  = import_kwh / load_kwh * 100 if load_kwh > 0 else 0.0
        solar_covered = direct_solar / load_kwh * 100 if load_kwh > 0 else 0.0

        result = StepResult(
            timestamp = timestamp,
            solar_kwh = round(solar_kwh, 3),
            load_kwh = round(load_kwh, 3),
            forecast_kwh = round(forecast_kwh, 3),
            soc_pct = self.battery.soc_pct,
            soc_kwh = self.battery.soc_kwh,
            charge_kwh = round(charge_kwh, 3),
            discharge_kwh = round(discharge_kwh, 3),
            import_kwh = round(import_kwh, 3),
            export_kwh = round(export_kwh, 3),
            tariff_zone = zone,
            rate_uah_kwh = rate,
            cost_uah = round(grid_step.net_cost, 4),
            direct_solar_kwh = round(direct_solar, 3),
            grid_covered_pct = round(grid_covered, 1),
            solar_covered_pct= round(solar_covered, 1),
            decision = " | ".join(decision_parts),
        )
        self._steps.append(result)
        return result

    @property
    def results(self) -> List[StepResult]:
        return self._steps

    def reset(self) -> None:
        self._steps.clear()
        self.solar.reset()
        self.battery.reset()
        self.grid.reset()
