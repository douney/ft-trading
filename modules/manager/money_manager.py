
from dataclasses import dataclass

from modules.base_type.instrument import Instrument
from modules.base_type.position import PositionDirection, PositionStatus, TradingPosition
from modules.base_type.signal import Signal
from modules.base_type.tick import Tick
from modules.base_type.time_frame import TimeFrame
from modules.manager.position_manager import PositionManager
from modules.manager.price_manager import PriceManager

import logging
logger = logging.getLogger(__name__)

@dataclass
class MoneyManagerConfig():
    position_stop_distance: float

class MoneyManager:
    def __init__(self, config: MoneyManagerConfig, position_manager: PositionManager, price_manager: PriceManager):
        self.position_manager = position_manager
        self.price_manager = price_manager
        self.config = config
        self.ticks_signal: dict[str, Signal] = {}
        self.day_balance = 0
        self.last_trade_balance = 0

        self.position_manager.signal.connect(self.on_position_update)
           
    def on_price_update(self, tick: Tick, instrument: Instrument) -> None:
        for position in self.position_manager.trading_positions:
            if position.position.instrument == instrument and position.position.status != PositionStatus.DELETED:
                self._check_position(position, tick)


    def on_position_update(self, position: TradingPosition):
        if (position.position.status == PositionStatus.OPEN or position.position.status == PositionStatus.UPDATED):
            if (position.position.instrument.symbol not in self.ticks_signal):
                signal: Signal | None = self.price_manager.get_signal(position.position.instrument, TimeFrame.TICK)

                if signal is None:
                    logger.warning(f"Price signal for {position.position.instrument} not found")
                    return
                
                signal.connect(self.on_price_update)
                self.ticks_signal[position.position.instrument.symbol] = signal

        elif (position.position.status == PositionStatus.DELETED):
            self.day_balance += (position.position.get_balance() * position.position.size)
            self.last_trade_balance = (position.position.get_balance() * position.position.size)


    def _check_position(self, position: TradingPosition, tick: Tick):
        pl = position.position.get_distance(tick)
        position.last_tick = tick

        if pl < 0:
            position.max_loss = min(position.max_loss, pl)
        else:
            position.max_gain = max(position.max_gain, pl)

        position.test_data = ""

        if position.stop_out is None:
            position.set_stop_out_distance(-self.config.position_stop_distance)

        if position.trailing_stop and position.stop_out is not None:
            if position.position.direction == PositionDirection.BUY:
                position.stop_out = max(position.stop_out, tick.bid - self.config.position_stop_distance)
            else:
                position.stop_out = min(position.stop_out, tick.ask + self.config.position_stop_distance)

        if not position.lock.locked():
            if position.is_stop_out():
                position.test_data += "Stop triggered"
                logger.info(f"Stop triggered for position {position.position.instrument} tick: {tick}")
                self.position_manager.close_position(position)
                
            if position.stop_profit is not None:
                if position.is_stop_profit():
                    position.test_data += "Take profit triggered"
                    logger.info(f"Take profit triggered for position {position.position.instrument}")
                    self.position_manager.close_position(position)
