from datetime import datetime
import json
from queue import Queue
from typing import Optional

from lightstreamer.client import SubscriptionListener, ItemUpdate # type: ignore
import pytz

from modules.base_type.instrument import get_instrument_by_symbol
from modules.broker.ig.port.ig_instruments import IG_INSTRUMENTS
from modules.broker.ig.utils.types_convertor import TypesConvertor
from modules.base_type.position import Position
from modules.base_type.queue_data import QueueData
from modules.base_type.tick import Tick

import logging
logger = logging.getLogger(__name__)

class BaseListener(SubscriptionListener):
    _name = "Base listener"

    def __init__(self, queue: Queue[QueueData], id: int) -> None:
        self._queue = queue
        self._id = id

    def onItemUpdate(self, update: ItemUpdate):
        data: Optional[Tick | Position] = self.process_data(update)

        if data is None:
            return
        
        self._queue.put(QueueData(self._id, data))

    def onSubscription(self):
        logger.info(f"'{self._name}' onSubscription()")

    def onSubscriptionError(self, code: str, message: str):
        logger.info(
            f"'{self._name}' onSubscriptionError(): '{code}' {message}")

    def onUnsubscription(self):
        logger.info(f"'{self._name}' onUnsubscription()")

    def process_data(self, update: ItemUpdate) -> Optional[Tick | Position]:
        raise NotImplementedError("process_data() must be implemented")


class TickListener(BaseListener):
    _name = "Tick listener"

    def __init__(self, queue: Queue[QueueData], id: int) -> None:
        super().__init__(queue, id)

    def process_data(self, update: ItemUpdate) -> Optional[Tick]:
        bid = update.getValue("BID") # type: ignore
        ask = update.getValue("OFR") # type: ignore
        timestamp_ms = update.getValue("UTM") # type: ignore
    
        if (bid is None) or (ask is None) or (timestamp_ms is None):
            return None
        
        return Tick(float(bid), float(ask), int(timestamp_ms))

class PositionListener(BaseListener):
    _name = "Position listener"

    def __init__(self, queue: Queue[QueueData], id: int) -> None:
        super().__init__(queue, id)

    def process_data(self, update: ItemUpdate):
        confirms = update.getValue("CONFIRMS") # type: ignore
        opu = update.getValue("OPU") # type: ignore
        wou = update.getValue("WOU") # type: ignore

        if (confirms is not None):
            pass

        if (opu is not None):
            opu = json.loads(opu)
            
            currency = TypesConvertor.to_currency(opu.get("currency"))
            status = TypesConvertor.to_position_status(opu.get("status"))
            direction = TypesConvertor.to_position_direction(opu.get("direction"))

            utc_dt = datetime.strptime(opu.get("timestamp"), '%Y-%m-%dT%H:%M:%S.%f')
            utc_dt = pytz.utc.localize(utc_dt)
            local_time = utc_dt.astimezone(pytz.timezone('Europe/Paris'))
            timestamp_ms = int(local_time.timestamp() * 1000)

            instrument = get_instrument_by_symbol(IG_INSTRUMENTS, opu.get("epic"))
            if instrument is None:
                logger.error(f"Instrument not found for epic: {opu.get('epic')}")
                return None

            position = Position(
                id=opu.get("dealId"),
                instrument=instrument,
                level=opu.get("level"),
                currency=currency,
                stop_level=opu.get("stopLevel"),
                limit_level=opu.get("limitLevel"),
                status=status,
                direction=direction,
                size=opu.get("size"),
                timestamp=timestamp_ms
            )

            return position

        if (wou is not None):
            pass

        return None