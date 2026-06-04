from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from backend.config.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class BatteryLogEntry:
    timestamp: object
    action: str        # 'charge', 'discharge', 'idle', 'self_discharge'
    power_kw: float
    energy_kwh: float      # фактично заряджено/розряджено
    soc_before: float      # SOC до операції, %
    soc_after: float      # SOC після операції, %
    energy_in: float      # до батареї (брутто)
    energy_out: float      # від батареї (брутто)
    loss_kwh: float      # втрати на ефективність
    cycle_delta: float      # приріст до лічильника циклів
    limited_by: str        # '' / 'soc_max' / 'soc_min' / 'power'


class BatteryStorage:
    SELF_DISCHARGE_RATE: float = 0.001   # частка SOC на годину

    def __init__(self):
        cfg_bat = get_settings().battery
        cfg_sim = get_settings().simulation

        self.capacity_kwh = cfg_bat.capacity_kwh
        self.max_charge_kw = cfg_bat.max_charge_kw
        self.max_discharge_kw = cfg_bat.max_discharge_kw
        self.charge_eff = cfg_bat.charge_efficiency
        self.discharge_eff = cfg_bat.discharge_efficiency
        self.abs_soc_min = cfg_bat.min_soc_pct / 100.0
        self.abs_soc_max = cfg_bat.max_soc_pct / 100.0
        self.op_soc_min = cfg_sim.soc_min_pct / 100.0
        self.op_soc_max = cfg_sim.soc_max_pct / 100.0

        initial_soc = cfg_bat.initial_soc_pct / 100.0
        self._soc: float = max(self.abs_soc_min, min(self.abs_soc_max, initial_soc))
        self._soc_kwh: float = self._soc * self.capacity_kwh
        self.cycle_count: float = 0.0
        self.total_charged: float = 0.0
        self.total_discharged: float = 0.0
        self.log: List[BatteryLogEntry] = []

        logger.info(
            "BatteryStorage init: cap=%.1f kWh  SOC=%.0f%%  "
            "op_range=[%.0f%%..%.0f%%]  max_ch/dch=%.1f/%.1f kW",
            self.capacity_kwh, self._soc * 100,
            self.op_soc_min * 100, self.op_soc_max * 100,
            self.max_charge_kw, self.max_discharge_kw,
        )

    @property
    def soc_pct(self) -> float:
        return round(self._soc * 100.0, 2)

    @property
    def soc_kwh(self) -> float:
        return round(self._soc_kwh, 3)

    @property
    def available_capacity_kwh(self) -> float:
        return max(0.0, self.op_soc_max * self.capacity_kwh - self._soc_kwh)

    @property
    def available_energy_kwh(self) -> float:
        return max(0.0, self._soc_kwh - self.op_soc_min * self.capacity_kwh)

    def get_soc(self) -> float:
        return round(self._soc, 4)

    def charge(self, requested_kwh: float, timestamp=None) -> Tuple[float, BatteryLogEntry]:
        soc_before = self._soc
        limited_by = ""

        energy_in = min(requested_kwh, self.max_charge_kw)
        if energy_in < requested_kwh:
            limited_by = "power"

        max_storable = self.available_capacity_kwh / self.charge_eff
        if energy_in > max_storable:
            energy_in = max_storable
            limited_by = "soc_max"

        abs_max_storable = (self.abs_soc_max * self.capacity_kwh - self._soc_kwh) / self.charge_eff
        energy_in = min(energy_in, max(0.0, abs_max_storable))

        energy_in = max(0.0, round(energy_in, 4))

        energy_stored = energy_in * self.charge_eff
        loss = energy_in - energy_stored

        self._soc_kwh = min(self._soc_kwh + energy_stored,
                            self.abs_soc_max * self.capacity_kwh)
        self._soc = self._soc_kwh / self.capacity_kwh
        self.total_charged += energy_in
        self.cycle_count += energy_in / self.capacity_kwh * 0.5

        entry = BatteryLogEntry(
            timestamp = timestamp,
            action = "charge" if energy_in > 0 else "idle",
            power_kw = energy_in,
            energy_kwh = energy_stored,
            soc_before = soc_before * 100,
            soc_after = self._soc * 100,
            energy_in = energy_in,
            energy_out = 0.0,
            loss_kwh = round(loss, 4),
            cycle_delta = round(energy_in / self.capacity_kwh * 0.5, 4),
            limited_by = limited_by,
        )
        self.log.append(entry)
        return round(energy_in, 4), entry

    def discharge(self, requested_kwh: float, timestamp=None) -> Tuple[float, BatteryLogEntry]:
        soc_before = self._soc
        limited_by = ""

        energy_out = min(requested_kwh, self.max_discharge_kw)
        if energy_out < requested_kwh:
            limited_by = "power"

        max_extractable = self.available_energy_kwh * self.discharge_eff
        if energy_out > max_extractable:
            energy_out = max_extractable
            limited_by = "soc_min"

        abs_min_extractable = (self._soc_kwh - self.abs_soc_min * self.capacity_kwh) * self.discharge_eff
        energy_out = min(energy_out, max(0.0, abs_min_extractable))

        energy_out = max(0.0, round(energy_out, 4))

        energy_extracted = energy_out / self.discharge_eff if self.discharge_eff > 0 else energy_out
        loss = energy_extracted - energy_out

        self._soc_kwh = max(self._soc_kwh - energy_extracted,
                            self.abs_soc_min * self.capacity_kwh)
        self._soc = self._soc_kwh / self.capacity_kwh
        self.total_discharged += energy_out
        self.cycle_count += energy_extracted / self.capacity_kwh * 0.5

        entry = BatteryLogEntry(
            timestamp = timestamp,
            action = "discharge" if energy_out > 0 else "idle",
            power_kw = energy_out,
            energy_kwh = energy_out,
            soc_before = soc_before * 100,
            soc_after = self._soc * 100,
            energy_in = 0.0,
            energy_out = energy_extracted,
            loss_kwh = round(loss, 4),
            cycle_delta = round(energy_extracted / self.capacity_kwh * 0.5, 4),
            limited_by = limited_by,
        )
        self.log.append(entry)
        return round(energy_out, 4), entry

    def apply_self_discharge(self, timestamp=None) -> BatteryLogEntry:
        loss = self._soc_kwh * self.SELF_DISCHARGE_RATE
        soc_before = self._soc
        self._soc_kwh = max(self._soc_kwh - loss,
                            self.abs_soc_min * self.capacity_kwh)
        self._soc = self._soc_kwh / self.capacity_kwh
        entry = BatteryLogEntry(
            timestamp=timestamp, action="self_discharge",
            power_kw=0.0, energy_kwh=0.0,
            soc_before=soc_before*100, soc_after=self._soc*100,
            energy_in=0.0, energy_out=round(loss,4),
            loss_kwh=round(loss,4), cycle_delta=0.0, limited_by="",
        )
        self.log.append(entry)
        return entry

    def update_state(self, timestamp=None) -> None:
        self.apply_self_discharge(timestamp)

    def reset(self, initial_soc_pct: Optional[float] = None) -> None:
        if initial_soc_pct is None:
            initial_soc_pct = get_settings().battery.initial_soc_pct
        self._soc = initial_soc_pct / 100.0
        self._soc_kwh = self._soc * self.capacity_kwh
        self.cycle_count = 0.0
        self.total_charged = 0.0
        self.total_discharged = 0.0
        self.log.clear()
