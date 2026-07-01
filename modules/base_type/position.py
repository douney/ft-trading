from dataclasses import dataclass
import threading
from typing import Optional
from enum import Enum

from modules.base_type.currency import Currency
from modules.base_type.instrument import Instrument
from modules.base_type.tick import Tick

class PositionStatus(Enum):
    OPEN = "OPEN"
    UPDATED = "UPDATED"
    DELETED = "DELETED"

    def __str__(self):
        return self.value
    
class PositionDirection(Enum):
    BUY = "BUY"
    SELL = "SELL"

    def __str__(self):
        return self.value
    
@dataclass
class Position:
    id: str
    instrument: Instrument
    level: float
    currency: Currency
    stop_level: Optional[float]
    limit_level: Optional[float]
    status: PositionStatus
    direction: PositionDirection
    size : float
    timestamp: int
    entry_level: float = 0.0

    def get_stop_distance(self) -> Optional[float]:
        if self.stop_level is None:
            return None
        
        return abs(self.level - self.stop_level)
    
    def set_stop_distance(self, stop_distance: Optional[float]):
        if stop_distance is None:
            self.stop_level = None
            return
        
        if self.direction == PositionDirection.BUY:
            self.stop_level = self.level - stop_distance
        else:
            self.stop_level = self.level + stop_distance
    
    def get_limit_distance(self) -> Optional[float]:
        if self.limit_level is None:
            return None
        
        return abs(self.level - self.limit_level)
       
    def set_limit_distance(self, limit_distance: Optional[float]):
        if limit_distance is None:
            self.limit_level = None
            return

        if self.direction == PositionDirection.BUY:
            self.limit_level = self.level + limit_distance
        else:
            self.limit_level = self.level - limit_distance

    def get_distance(self, tick: Tick) -> float:
        if self.direction == PositionDirection.BUY:
            return tick.bid - self.level
        elif self.direction == PositionDirection.SELL:
            return self.level - tick.ask
        else:
            raise ValueError("Invalid position direction")
                

    def get_balance(self) -> float:
        if (self.status != PositionStatus.DELETED):
            return 0.0
        
        if self.direction == PositionDirection.SELL:
            return self.entry_level - self.level
        else:
            return self.level - self.entry_level

    def __str__(self):
        return (
            "Position("
            f"    id={self.id},\n"
            f"    instrument={self.instrument}\n"
            f"    level={self.level},\n"
            f"    currency={self.currency},\n"
            f"    stop_level={self.stop_level},\n"
            f"    limit_level={self.limit_level},\n"
            f"    status={self.status},\n"
            f"    direction={self.direction},\n"
            f"    size={self.size},\n"
            f"    timestamp={self.timestamp},\n"
            ")"
        )
    
class TradingPosition:
    def __init__(self, position: Position):
        self.position = position
        self.max_loss: float = 0.0
        self.max_gain: float = 0.0
        self.trailing_stop: bool = True
        self.stop_out: Optional[float] = None
        self.stop_profit: Optional[float] = None
        self.last_tick: Optional[Tick] = None
        self.test_data: Optional[str] = None
        self.lock = threading.Lock()

    def get_stop_profit_distance(self) -> Optional[float]:
        if self.stop_profit is None:
            return None
        
        return abs(self.position.level - self.stop_profit)
    
    def set_stop_profit_distance(self, stop_profit_distance: Optional[float]):
        if stop_profit_distance is None:
            self.stop_profit = None
            return
        
        if self.last_tick is None:
            return
        
        pl = self.position.get_distance(self.last_tick)
        if stop_profit_distance < 0:
            if pl > 0:
                stop_profit_distance = pl * abs(stop_profit_distance / 100)
            else:
                return

        if stop_profit_distance >= pl:
            return

        if self.position.direction == PositionDirection.BUY:
            self.stop_profit = self.position.level + stop_profit_distance
        else:
            self.stop_profit = self.position.level - stop_profit_distance

    def is_stop_profit(self) -> bool:
        if self.last_tick is None:
            return False
        
        stop_profit_distance = self.get_stop_profit_distance()

        if stop_profit_distance is None:
            return False
        
        pl = self.position.get_distance(self.last_tick)
        return pl <= stop_profit_distance
    
    def get_stop_out_distance(self) -> Optional[float]:
        if self.stop_out is None:
            return None
        
        if self.position.direction == PositionDirection.BUY:
            return self.stop_out - self.position.level
        else:
            return self.position.level - self.stop_out
    
    def set_stop_out_distance(self, stop_out_distance: Optional[float]):
        if stop_out_distance is None:
            self.stop_out = None
            return
        
        if self.position.direction == PositionDirection.BUY:
            self.stop_out = self.position.level + stop_out_distance
        else:
            self.stop_out = self.position.level - stop_out_distance

    def is_stop_out(self) -> bool:
        if self.last_tick is None:
            return False
        
        stop_out_distance = self.get_stop_out_distance()

        if stop_out_distance is None:
            return False
        
        pl = self.position.get_distance(self.last_tick)
        return pl <= stop_out_distance