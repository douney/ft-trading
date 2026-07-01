from dataclasses import dataclass
import enum

from modules.base_type.position import Position
from modules.base_type.tick import Tick

class QueueType(enum.Enum):
    TICK = 1
    POSITION = 2
    CANDLE = 3

@dataclass
class QueueData:
    id: int
    data: Tick | Position
    # queue_type: QueueType