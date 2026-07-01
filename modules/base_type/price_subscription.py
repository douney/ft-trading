from modules.base_type.instrument import Instrument
from modules.base_type.signal import Signal
from modules.base_type.time_frame import TimeFrame
from dataclasses import dataclass

@dataclass
class PriceSubscription:
    id: int
    instrument: Instrument
    timeframe: TimeFrame
    signal: Signal
