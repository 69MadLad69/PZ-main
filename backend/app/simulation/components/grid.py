from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Tuple

from backend.config.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class GridStep:
    timestamp: object
    import_kwh: float
    export_kwh: float
    tariff_zone: str
    rate_uah_kwh: float
    import_cost: float
    export_income: float
    net_cost: float


class GridConnection:
    EXPORT_RATE_FACTOR: float = 0.0

    def __init__(self):
        cfg = get_settings()
        self.max_power_kw = cfg.object.max_power_kw  # 95 кВт
        self._day_rate = 6.9
        self._night_rate = 5.6
        self._day_start = 7
        self._day_end = 23
        for z in cfg.tariff.zones:
            if z.zone_type == "day":
                self._day_rate  = z.rate_uah_kwh
                self._day_start = z.start_time.hour
                self._day_end   = z.end_time.hour
            elif z.zone_type == "night":
                self._night_rate = z.rate_uah_kwh
        self.log: List[GridStep] = []
        logger.info("GridConnection: max=%.0f kW  day=%.2f  night=%.2f UAH/kWh",
                    self.max_power_kw, self._day_rate, self._night_rate)

    def get_rate(self, hour: int) -> Tuple[str, float]:
        s, e = self._day_start, self._day_end
        if s < e:
            is_day = s <= hour < e
        else:
            is_day = hour >= s or hour < e
        if is_day:
            return "day", self._day_rate
        return "night", self._night_rate

    def transact(
        self,
        timestamp,
        import_kwh: float,
        export_kwh: float,
        hour: int,
    ) -> GridStep:
        import_kwh = max(0.0, round(import_kwh, 4))
        export_kwh = max(0.0, round(export_kwh, 4))

        if import_kwh > self.max_power_kw:
            logger.warning("Import %.2f кВт перевищує ліміт %.0f кВт — клівується",
                           import_kwh, self.max_power_kw)
            import_kwh = self.max_power_kw

        zone, rate = self.get_rate(hour)
        import_cost = round(import_kwh * rate, 4)
        export_income = round(export_kwh * rate * self.EXPORT_RATE_FACTOR, 4)
        net_cost = round(import_cost - export_income, 4)

        step = GridStep(
            timestamp=timestamp, import_kwh=import_kwh, export_kwh=export_kwh,
            tariff_zone=zone, rate_uah_kwh=rate,
            import_cost=import_cost, export_income=export_income, net_cost=net_cost,
        )
        self.log.append(step)
        return step

    @property
    def total_import_kwh(self) -> float:
        return round(sum(s.import_kwh for s in self.log), 3)

    @property
    def total_export_kwh(self) -> float:
        return round(sum(s.export_kwh for s in self.log), 3)

    @property
    def total_cost_uah(self) -> float:
        return round(sum(s.net_cost for s in self.log), 2)

    def reset(self) -> None:
        self.log.clear()
