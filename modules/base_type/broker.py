from queue import Queue
from typing import Optional
from modules.base_type.broker_config import BrokerConfig
from modules.base_type.instrument import Instrument
from modules.base_type.position import Position
from modules.base_type.queue_data import QueueData
from modules.base_type.time_frame import TimeFrame

class Broker():
    def __init__(self, config: BrokerConfig):
        self.config = config

    def connect(self, passphrase: Optional[str] = None) -> None:
        raise NotImplementedError("connect() must be implemented")

    def disconnect(self) -> None:
        pass
    
    def subscribe_price(self, instrument: Instrument, timeframe: TimeFrame, id: int, queue: Queue[QueueData]) -> None:
        raise NotImplementedError("subscribe() must be implemented")
    
    def unsubscribe_price(self, instrument: Instrument, timeframe: TimeFrame) -> None:
        raise NotImplementedError("unsubscribe() must be implemented")
    
    def subscribe_positions(self, queue: Queue[QueueData]) -> None:
        raise NotImplementedError("subscribe_order() must be implemented")
    
    def unsubscribe_positions(self) -> None:
        raise NotImplementedError("unsubscribe_order() must be implemented")
    
    def create_position(self, position: Position, validity_level: Optional[float] = None) -> None:
        raise NotImplementedError("create_position() must be implemented")
    
    def close_position(self, position: Position, validity_level: Optional[float] = None, size: Optional[float] = None) -> None:
        raise NotImplementedError("close_position() must be implemented")
    
    def update_position(self, position: Position) -> None:
        raise NotImplementedError("update_position() must be implemented")
    
    def get_positions(self) -> list[Position]:
        raise NotImplementedError("get_positions() must be implemented")
