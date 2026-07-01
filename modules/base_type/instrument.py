
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Optional
from modules.base_type.currency import Currency

@dataclass
class Instrument:
    symbol: str
    currency: Currency
    point_value: float
    min_size: float
    open_hour: float
    close_hour: float
    label: str = ""

    def display_label(self) -> str:
        return self.label or self.symbol


def get_instrument_by_symbol(ns: SimpleNamespace, symbol: str) -> Optional[Instrument]:
    for name in vars(ns):
        inst = getattr(ns, name)
        if getattr(inst, "symbol", None) == symbol:
            return inst
    return None
