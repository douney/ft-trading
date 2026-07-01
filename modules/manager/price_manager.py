from queue import Empty, Queue
from typing import Optional
import threading

from modules.base_type.broker import Broker
from modules.base_type.instrument import Instrument
from modules.base_type.price_subscription import PriceSubscription
from modules.base_type.queue_data import QueueData
from modules.base_type.signal import Signal
from modules.base_type.tick import Tick
from modules.base_type.time_frame import TimeFrame

import logging

from modules.database.database import Database
logger = logging.getLogger(__name__)

class PriceManager(threading.Thread):
    def __init__(self, broker: Broker):
        super().__init__()

        self.broker = broker
        self.subscriptions: list[PriceSubscription] = []
        self.last_ticks: dict[str, Tick] = {}
        self.queue: Queue[QueueData] = Queue()
        self.current_id = 0
        self._stop_event = threading.Event()

    def subscribe(self, instrument: Instrument, timeframe: TimeFrame):
        for sub in self.subscriptions:
            if sub.instrument.symbol == instrument.symbol and sub.timeframe == timeframe:
                return sub.signal
            
        self.current_id += 1
        new_subscription = PriceSubscription(self.current_id, instrument, timeframe, Signal())

        self.subscriptions.append(new_subscription)
        self._subscribe_broker(new_subscription)
        return new_subscription.signal

    def get_signal(self, instrument: Instrument, timeframe: TimeFrame) -> Optional[Signal]:
        for sub in self.subscriptions:
            if sub.instrument.symbol == instrument.symbol and sub.timeframe == timeframe:
                return sub.signal
            
        return None

    def unsubscribe(self, instrument: Instrument, timeframe: TimeFrame):
        for sub in self.subscriptions:
            if sub.instrument.symbol == instrument.symbol and sub.timeframe == timeframe:
                self.subscriptions.remove(sub)
                break

    def get_last_tick(self, instrument: Instrument) -> Optional[Tick]:
        return self.last_ticks.get(instrument.symbol)

    def _subscribe_broker(self, sub: PriceSubscription):
        self.broker.subscribe_price(
            sub.instrument,
            sub.timeframe,
            sub.id,
            self.queue
        )

    def _unsubscribe_broker(self):
        pass

    def stop(self) -> None:
        self._stop_event.set()
        Database().flush_all_ticks()

    def run(self):
        while not self._stop_event.is_set():
            try:
                data: QueueData = self.queue.get(timeout=0.2)
            except Empty:
                continue

            for sub in self.subscriptions:
                if sub.id == data.id and isinstance(data.data, Tick):
                    tick: Tick = data.data
                    Database().add_tick(sub.instrument, tick)
                    self.last_ticks[sub.instrument.symbol] = tick
                    sub.signal.send(data.data, instrument = sub.instrument)
                    break

        Database().flush_all_ticks()
