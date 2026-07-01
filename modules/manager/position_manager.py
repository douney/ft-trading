from queue import Empty, Queue
import threading
from concurrent.futures import ThreadPoolExecutor

from modules.base_type.broker import Broker
from modules.base_type.position import Position, PositionStatus, TradingPosition
from modules.base_type.signal import Signal

import logging

from modules.base_type.queue_data import QueueData
from modules.database.database import Database
logger = logging.getLogger(__name__)

class PositionManager(threading.Thread):
    def __init__(self, broker: Broker):
        super().__init__()

        self.broker: Broker = broker
        self.position_queue: Queue[QueueData] = Queue()
        self.trading_positions: list[TradingPosition] = []
        self.signal = Signal()
        self.executor = ThreadPoolExecutor()
        self._stop_event = threading.Event()



    def run(self):
        self.broker.subscribe_positions(self.position_queue)

        while not self._stop_event.is_set():
            try:
                queue_data: QueueData = self.position_queue.get(timeout=0.2)
            except Empty:
                continue

            if not isinstance(queue_data.data, Position):
                logger.warning(f"Received non-position data: {queue_data.data}")
                continue

            position: Position = queue_data.data
            self._process_position(position)

    def open_position(self, position: TradingPosition):
        with position.lock:
            self._submit_order("open", self.broker.create_position, position)

    def close_position(self, position: TradingPosition):
        with position.lock:
            self._submit_order("close", self.broker.close_position, position)

    def update_position(self, position: TradingPosition):
        with position.lock:
            self._submit_order("update", self.broker.update_position, position)

    def stop(self) -> None:
        self._stop_event.set()
        self.executor.shutdown(wait=False, cancel_futures=True)

    def _process_position(self, new_position: Position):
        existing_position = next((trading_position for trading_position in self.trading_positions if trading_position.position.id == new_position.id), None)
        new_trading_position = TradingPosition(new_position)

        if existing_position is None:
            if new_position.status == PositionStatus.DELETED:
                logger.warning(f"Position {new_position.id} is not open, ignoring")
                return
            
            logger.debug(f"Adding new position {new_position.id}")
            new_position.entry_level = new_position.level
            self.trading_positions.append(new_trading_position)
            Database().add_position(new_position)

        else:
            self._update_position(existing_position, new_position)
            
        self.signal.send(new_trading_position)

            
    def _update_position(self, current_position: TradingPosition, new_position: Position):
        if (new_position.status == PositionStatus.DELETED):
            logger.debug(f"Position {current_position.position.id} deleted")
            new_position.entry_level = current_position.position.entry_level
            new_position.size = current_position.position.size
            self.trading_positions.remove(current_position)

        elif (new_position.status == PositionStatus.UPDATED):
            if (current_position.position.stop_level != new_position.stop_level) :
                logger.debug(f"Position {current_position.position.id} stop level updated from {current_position.position.stop_level} to {new_position.stop_level}")
                current_position.position.stop_level = new_position.stop_level

            if (current_position.position.limit_level != new_position.limit_level) :
                logger.debug(f"Position {current_position.position.id} limit level updated from {current_position.position.limit_level} to {new_position.limit_level}")
                current_position.position.limit_level = new_position.limit_level

        else:
            raise ValueError(f"Unknown position status {new_position.status} for position {new_position.id}")

    def _submit_order(self, action: str, broker_method, position: TradingPosition) -> None:
        Database().add_order_event(action, position.position)
        future = self.executor.submit(broker_method, position.position)
        future.add_done_callback(self._log_order_failure)

    def _log_order_failure(self, future) -> None:
        error = future.exception()
        if error is not None:
            logger.error(f"Broker order failed: {error}")


    def __str__(self):
        return f"PositionManager(positions={self.trading_positions})"
