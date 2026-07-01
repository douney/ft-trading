from queue import Queue
from typing import Optional

from modules.base_type.broker import Broker
from modules.base_type.broker_config import BrokerConfig
from modules.base_type.instrument import Instrument
from modules.base_type.position import Position, PositionDirection
from modules.base_type.queue_data import QueueData
from modules.base_type.time_frame import TimeFrame
from modules.broker.ig.ig_service import IGService
from modules.broker.ig.listener import PositionListener, TickListener
from modules.broker.ig.subscription import PositionSubscription, TickSubscription

import logging

from modules.broker.ig.utils.types_convertor import TypesConvertor
logger = logging.getLogger(__name__)

class IGBroker(Broker):
    def __init__(self, config: BrokerConfig):
        super().__init__(config)
        self.config = config
        self.ig_service: Optional[IGService] = None
        

    def connect(self, passphrase: Optional[str] = None):
        self.config.validate()
        self.config.decrypt_password(passphrase)

        self.ig_service = IGService(self.config.username, self.config.api_key, 
                                    self.config.acc_type, acc_number=self.config.acc_number)
        
        self.ig_service.connect(self.config.password)
        self.ig_service.stream.connect()
        self.config.clear_password()

        logger.info("Connected to IG API")

    def disconnect(self):
        if self.ig_service is None:
            return

        self.ig_service.stream.disconnect()
        self.ig_service.ig_session.session.close()
        self.ig_service = None
        logger.info("Disconnected from IG API")

    def subscribe_price(self, instrument: Instrument, timeframe: TimeFrame, id: int, queue: Queue[QueueData]):
        if not self.ig_service:
            raise Exception("IGService is not initialized. Call connect() first.")

        sub = TickSubscription(instrument.symbol)
        sub.addListener(TickListener(queue, id)) # type: ignore
        self.ig_service.stream.subscribe(sub)

    def subscribe_positions(self, queue: Queue[QueueData]):
        if not self.ig_service:
            raise Exception("IGService is not initialized. Call connect() first.")

        sub = PositionSubscription(self.config.acc_number)
        sub.addListener(PositionListener(queue, 0)) # type: ignore
        self.ig_service.stream.subscribe(sub)

    def create_position(self, position: Position, validity_level: Optional[float] = None):
        if not self.ig_service:
            raise Exception("IGService is not initialized. Call connect() first.")
        
        self.ig_service.deal.create_open_position(
            TypesConvertor.from_currency(position.currency),
            TypesConvertor.from_position_direction(position.direction),
            position.instrument.symbol,
            position.get_stop_distance(),
            position.size,
            position.get_limit_distance(),
            validity_level,
        )
    
    def close_position(self, position: Position, validity_level: Optional[float] = None, size: Optional[float] = None):
        if not self.ig_service:
            raise Exception("IGService is not initialized. Call connect() first.")

        if size is None:
            size = position.size

        direction = PositionDirection.SELL if position.direction == PositionDirection.BUY else PositionDirection.BUY

        self.ig_service.deal.close_open_position(
            position.id,
            TypesConvertor.from_position_direction(direction),
            "-",
            validity_level,
            size
        )
    
    def update_position(self, position: Position):
        if not self.ig_service:
            raise Exception("IGService is not initialized. Call connect() first.")

        print(f"Updating position {position.id} with limit: {position.limit_level}, stop: {position.stop_level}")

        self.ig_service.deal.update_open_position(
            position.id,
            position.limit_level,
            position.stop_level,
        )
