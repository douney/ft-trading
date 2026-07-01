import logging
import threading
from typing import Callable, Optional

from modules.base_type.broker import Broker
from modules.base_type.broker_config import BrokerConfig, DemoConfig, LiveConfig
from modules.base_type.instrument import Instrument
from modules.base_type.time_frame import TimeFrame
from modules.broker.ig.port.ig_instruments import IG_INSTRUMENTS
from modules.manager.money_manager import MoneyManager, MoneyManagerConfig
from modules.manager.position_manager import PositionManager
from modules.manager.price_manager import PriceManager

logger = logging.getLogger(__name__)

BrokerFactory = Callable[[BrokerConfig], Broker]


def create_ig_broker(config: BrokerConfig) -> Broker:
    from modules.broker.ig.port.ig_broker import IGBroker

    return IGBroker(config)


TRADING_INSTRUMENTS = [
    IG_INSTRUMENTS.CAC40_1E,
    IG_INSTRUMENTS.SP500_1E,
]

RECORDING_INSTRUMENTS = [
    IG_INSTRUMENTS.DAX_1E,
    IG_INSTRUMENTS.CAC40_1E,
    IG_INSTRUMENTS.SP500_1E,
    IG_INSTRUMENTS.US_TECH_1E,
    IG_INSTRUMENTS.DOWJONES_1E,
]


class MarketDataRuntime:
    def __init__(
        self,
        name: str,
        instruments: list[Instrument],
        broker_factory: BrokerFactory = create_ig_broker,
    ):
        self.name = name
        self.instruments = instruments
        self.broker_factory = broker_factory
        self.lock = threading.RLock()
        self.broker: Optional[Broker] = None
        self.broker_mode: Optional[str] = None
        self.price_manager: Optional[PriceManager] = None

    def start(self, mode: str, passphrase: Optional[str] = None) -> dict:
        mode, broker = self._connect_broker(mode, passphrase)
        price_manager = PriceManager(broker)

        try:
            price_manager.start()
            self._subscribe_prices(price_manager)
        except Exception:
            self._stop_runtime(broker, price_manager)
            raise

        with self.lock:
            previous_broker = self.broker
            previous_price_manager = self.price_manager

            self.broker = broker
            self.broker_mode = mode
            self.price_manager = price_manager

        self._stop_runtime(previous_broker, previous_price_manager)
        logger.info(f"Started {self.name} runtime in {mode} mode")
        return self.get_status()

    def stop(self) -> None:
        with self.lock:
            broker = self.broker
            price_manager = self.price_manager
            self.broker = None
            self.broker_mode = None
            self.price_manager = None

        self._stop_runtime(broker, price_manager)
        logger.info(f"Stopped {self.name} runtime")

    def get_status(self) -> dict:
        with self.lock:
            price_manager = self.price_manager
            broker_mode = self.broker_mode

        return {
            "name": self.name,
            "connected": broker_mode is not None,
            "mode": broker_mode,
            "instruments": [instrument.symbol for instrument in self.instruments],
            "instrument_labels": self._get_instrument_labels(),
            "subscriptions": self._get_subscriptions(price_manager),
        }

    def get_prices(self) -> list[dict]:
        with self.lock:
            price_manager = self.price_manager

        if price_manager is None:
            return []

        return [
            {
                "runtime": self.name,
                "instrument": symbol,
                "instrument_label": self._get_instrument_label(symbol),
                "bid": tick.bid,
                "ask": tick.ask,
                "spread": tick.ask - tick.bid,
                "mid": tick.get_price(),
                "timestamp_ms": tick.timestamp_ms,
            }
            for symbol, tick in price_manager.last_ticks.items()
        ]

    def _connect_broker(self, mode: str, passphrase: Optional[str]) -> tuple[str, Broker]:
        mode = mode.lower()
        if mode not in ("demo", "live"):
            raise ValueError(f"Unknown IG mode: {mode}")

        config = DemoConfig() if mode == "demo" else LiveConfig()
        if mode == "live" and config.encrypted_password and not config.password and not passphrase:
            raise ValueError("Live mode requires the broker password passphrase")

        broker = self.broker_factory(config)
        broker.connect(passphrase)
        return mode, broker

    def _subscribe_prices(self, price_manager: PriceManager) -> None:
        for instrument in self.instruments:
            price_manager.subscribe(instrument, TimeFrame.TICK)

    def _stop_runtime(
        self,
        broker: Optional[Broker],
        price_manager: Optional[PriceManager],
    ) -> None:
        if price_manager is not None:
            price_manager.stop()

        if price_manager is not None and price_manager.is_alive():
            price_manager.join(timeout=2)

        if broker is not None:
            broker.disconnect()

    def _get_subscriptions(self, price_manager: Optional[PriceManager]) -> list[dict]:
        if price_manager is None:
            return []

        return [
            {
                "instrument": sub.instrument.symbol,
                "instrument_label": sub.instrument.display_label(),
                "timeframe": str(sub.timeframe),
            }
            for sub in price_manager.subscriptions
        ]

    def _get_instrument_labels(self) -> dict[str, str]:
        return {
            instrument.symbol: instrument.display_label()
            for instrument in self.instruments
        }

    def _get_instrument_label(self, symbol: str) -> str:
        return self._get_instrument_labels().get(symbol, symbol)


class RecordingRuntime(MarketDataRuntime):
    def __init__(self, broker_factory: BrokerFactory = create_ig_broker):
        super().__init__("recording", RECORDING_INSTRUMENTS, broker_factory)


class TradingRuntime(MarketDataRuntime):
    def __init__(
        self,
        money_manager_config: MoneyManagerConfig,
        broker_factory: BrokerFactory = create_ig_broker,
    ):
        super().__init__("trading", TRADING_INSTRUMENTS, broker_factory)
        self.money_manager_config = money_manager_config
        self.position_manager: Optional[PositionManager] = None
        self.money_manager: Optional[MoneyManager] = None

    def start(self, mode: str, passphrase: Optional[str] = None) -> dict:
        mode, broker = self._connect_broker(mode, passphrase)
        price_manager = PriceManager(broker)
        position_manager = PositionManager(broker)
        money_manager = MoneyManager(self.money_manager_config, position_manager, price_manager)

        try:
            price_manager.start()
            self._subscribe_prices(price_manager)
            position_manager.start()
        except Exception:
            self._stop_trading_runtime(broker, price_manager, position_manager)
            raise

        with self.lock:
            previous_broker = self.broker
            previous_price_manager = self.price_manager
            previous_position_manager = self.position_manager

            self.broker = broker
            self.broker_mode = mode
            self.price_manager = price_manager
            self.position_manager = position_manager
            self.money_manager = money_manager

        self._stop_trading_runtime(previous_broker, previous_price_manager, previous_position_manager)
        logger.info(f"Started trading runtime in {mode} mode")
        return self.get_status()

    def stop(self) -> None:
        with self.lock:
            broker = self.broker
            price_manager = self.price_manager
            position_manager = self.position_manager
            self.broker = None
            self.broker_mode = None
            self.price_manager = None
            self.position_manager = None
            self.money_manager = None

        self._stop_trading_runtime(broker, price_manager, position_manager)
        logger.info("Stopped trading runtime")

    def get_health(self) -> dict:
        with self.lock:
            position_manager = self.position_manager
            money_manager = self.money_manager

        return {
            **self.get_status(),
            "open_positions": 0 if position_manager is None else len(position_manager.trading_positions),
            "day_balance": 0 if money_manager is None else money_manager.day_balance,
            "last_trade_balance": 0 if money_manager is None else money_manager.last_trade_balance,
        }

    def get_positions(self) -> list:
        with self.lock:
            position_manager = self.position_manager
            price_manager = self.price_manager

        if position_manager is None or price_manager is None:
            return []

        return [
            self.serialize_position(position, price_manager.get_last_tick(position.position.instrument))
            for position in position_manager.trading_positions
        ]

    def close_position(self, position_id: str) -> None:
        position_manager, position = self._find_position(position_id)
        logger.info(f"UI requested close for position {position_id}")
        position_manager.close_position(position)

    def update_limit(self, position_id: str, distance: Optional[float]) -> dict:
        position_manager, position = self._find_position(position_id)

        if position.position.get_limit_distance() != distance:
            logger.info(f"UI requested limit update for position {position_id}: {distance}")
            position.position.set_limit_distance(distance)
            position_manager.update_position(position)

        return self._serialize_current_position(position)

    def update_stop_profit(self, position_id: str, distance: Optional[float]) -> dict:
        _, position = self._find_position(position_id)

        if distance is None or position.get_stop_profit_distance() != distance:
            logger.info(f"UI requested stop profit update for position {position_id}: {distance}")
            position.set_stop_profit_distance(distance)

        return self._serialize_current_position(position)

    def serialize_position(self, position, last_tick):
        raw = position.position
        pnl = None
        if last_tick is not None:
            pnl = raw.get_distance(last_tick) * raw.size

        return {
            "id": raw.id,
            "instrument": raw.instrument.symbol,
            "instrument_label": raw.instrument.display_label(),
            "status": str(raw.status),
            "direction": str(raw.direction),
            "level": raw.level,
            "size": raw.size,
            "currency": str(raw.currency),
            "stop_level": raw.stop_level,
            "limit_level": raw.limit_level,
            "entry_level": raw.entry_level,
            "timestamp_ms": raw.timestamp,
            "pnl": pnl,
            "max_gain": position.max_gain * raw.size,
            "max_loss": position.max_loss * raw.size,
            "stop_out": position.stop_out,
            "stop_profit": position.stop_profit,
            "last_tick": None if last_tick is None else {
                "bid": last_tick.bid,
                "ask": last_tick.ask,
                "mid": last_tick.get_price(),
                "timestamp_ms": last_tick.timestamp_ms,
            },
        }

    def _find_position(self, position_id: str):
        with self.lock:
            position_manager = self.position_manager

        if position_manager is None:
            raise ValueError("Trading runtime is not connected")

        position = next(
            (
                trading_position
                for trading_position in position_manager.trading_positions
                if trading_position.position.id == position_id
            ),
            None,
        )
        if position is None:
            raise KeyError("Position not found")

        return position_manager, position

    def _serialize_current_position(self, position) -> dict:
        with self.lock:
            price_manager = self.price_manager

        last_tick = None
        if price_manager is not None:
            last_tick = price_manager.get_last_tick(position.position.instrument)

        return self.serialize_position(position, last_tick)

    def _stop_trading_runtime(
        self,
        broker: Optional[Broker],
        price_manager: Optional[PriceManager],
        position_manager: Optional[PositionManager],
    ) -> None:
        if position_manager is not None:
            position_manager.stop()

        if position_manager is not None and position_manager.is_alive():
            position_manager.join(timeout=2)

        self._stop_runtime(broker, price_manager)


class BacktestRuntime:
    def __init__(self):
        self.running = False

    def get_status(self) -> dict:
        return {
            "name": "backtest",
            "running": self.running,
            "available": False,
        }
