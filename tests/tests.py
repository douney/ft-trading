import os
import tempfile
import time
import unittest
from queue import Queue
from typing import Optional

from modules.base_type.broker import Broker
from modules.base_type.broker_config import BrokerConfig
from modules.base_type.currency import Currency
from modules.base_type.instrument import Instrument
from modules.base_type.position import Position, PositionDirection, PositionStatus, TradingPosition
from modules.base_type.queue_data import QueueData
from modules.base_type.tick import Tick
from modules.base_type.time_frame import TimeFrame
from modules.database.database import Database
from modules.manager.position_manager import PositionManager
from modules.manager.price_manager import PriceManager
from modules.manager.runtimes import RECORDING_INSTRUMENTS, RecordingRuntime
from modules.manager.trading_manager import TradingManager


TEST_INSTRUMENT = Instrument(
    symbol="TEST.MARKET",
    currency=Currency.EUR,
    point_value=1,
    min_size=1,
    open_hour=0,
    close_hour=24,
)


class FakeConfig(BrokerConfig):
    def __init__(self):
        self.env_prefix = "TEST"
        self.username = "test"
        self.password = "test"
        self.api_key = "test"
        self.acc_type = "demo"
        self.acc_number = "test"
        self.password_file = ""


class FakeBroker(Broker):
    def __init__(self):
        super().__init__(FakeConfig())
        self.connected = False
        self.price_queue: Optional[Queue[QueueData]] = None
        self.position_queue: Optional[Queue[QueueData]] = None
        self.price_subscription_id: Optional[int] = None
        self.price_subscriptions: list[tuple[Instrument, TimeFrame, int]] = []
        self.orders: list[tuple[str, Position]] = []
        self.disconnected = False

    def connect(self, passphrase: Optional[str] = None) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.disconnected = True

    def subscribe_price(self, instrument: Instrument, timeframe: TimeFrame, id: int, queue: Queue[QueueData]) -> None:
        self.price_subscription_id = id
        self.price_queue = queue
        self.price_subscriptions.append((instrument, timeframe, id))

    def unsubscribe_price(self, instrument: Instrument, timeframe: TimeFrame) -> None:
        pass

    def subscribe_positions(self, queue: Queue[QueueData]) -> None:
        self.position_queue = queue

    def unsubscribe_positions(self) -> None:
        pass

    def create_position(self, position: Position, validity_level: Optional[float] = None) -> None:
        self.orders.append(("open", position))

    def close_position(self, position: Position, validity_level: Optional[float] = None, size: Optional[float] = None) -> None:
        self.orders.append(("close", position))

    def update_position(self, position: Position) -> None:
        self.orders.append(("update", position))

    def get_positions(self) -> list[Position]:
        return []

    def emit_tick(self, tick: Tick) -> None:
        if self.price_queue is None or self.price_subscription_id is None:
            raise AssertionError("price queue is not subscribed")
        self.price_queue.put(QueueData(self.price_subscription_id, tick))


class FakeRuntime:
    def __init__(self, name: str):
        self.name = name
        self.connected = False
        self.mode: Optional[str] = None

    def start(self, mode: str, passphrase: Optional[str] = None) -> dict:
        self.connected = True
        self.mode = mode
        return self.get_status()

    def stop(self) -> None:
        self.connected = False
        self.mode = None

    def get_status(self) -> dict:
        return {
            "name": self.name,
            "connected": self.connected,
            "mode": self.mode,
            "instruments": [],
            "subscriptions": [],
        }

    def get_health(self) -> dict:
        return {
            **self.get_status(),
            "open_positions": 0,
            "day_balance": 0,
            "last_trade_balance": 0,
        }


def reset_database_singleton() -> None:
    instance = Database.__class__._instances.pop(Database, None)
    if instance is not None:
        instance.close()


def make_position(status: PositionStatus = PositionStatus.OPEN) -> Position:
    return Position(
        id="deal-1",
        instrument=TEST_INSTRUMENT,
        level=100.0,
        currency=Currency.EUR,
        stop_level=95.0,
        limit_level=110.0,
        status=status,
        direction=PositionDirection.BUY,
        size=1.0,
        timestamp=1_735_689_600_000,
    )


def make_tick() -> Tick:
    return Tick(bid=101.0, ask=102.0, timestamp_ms=int(time.time() * 1000))


class PositionTests(unittest.TestCase):
    def test_buy_position_distance_and_balance(self):
        position = make_position()

        self.assertEqual(position.get_distance(Tick(bid=103.0, ask=104.0, timestamp_ms=1)), 3.0)

        position.status = PositionStatus.DELETED
        position.entry_level = 100.0
        position.level = 106.0
        self.assertEqual(position.get_balance(), 6.0)


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        reset_database_singleton()
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["FT_DB_PATH"] = os.path.join(self.tmpdir.name, "test.sqlite3")

    def tearDown(self):
        reset_database_singleton()
        self.tmpdir.cleanup()
        os.environ.pop("FT_DB_PATH", None)

    def test_tick_round_trip_and_order_event_count(self):
        db = Database()
        tick = make_tick()

        db.add_tick(TEST_INSTRUMENT, tick)
        db.flush_all_ticks()
        db.add_order_event("close", make_position())

        self.assertEqual(db.load_ticks(TEST_INSTRUMENT)[0], tick)
        self.assertEqual(db.count_order_events(), 1)


class ManagerTests(unittest.TestCase):
    def setUp(self):
        reset_database_singleton()
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["FT_DB_PATH"] = os.path.join(self.tmpdir.name, "test.sqlite3")

    def tearDown(self):
        reset_database_singleton()
        self.tmpdir.cleanup()
        os.environ.pop("FT_DB_PATH", None)

    def test_price_manager_stores_last_tick(self):
        broker = FakeBroker()
        manager = PriceManager(broker)
        manager.start()
        manager.subscribe(TEST_INSTRUMENT, TimeFrame.TICK)

        tick = make_tick()
        broker.emit_tick(tick)

        for _ in range(20):
            if manager.get_last_tick(TEST_INSTRUMENT) == tick:
                break
            time.sleep(0.01)

        manager.stop()
        manager.join()

        self.assertEqual(manager.get_last_tick(TEST_INSTRUMENT), tick)
        self.assertEqual(Database().load_ticks(TEST_INSTRUMENT)[0], tick)

    def test_position_manager_logs_order_events(self):
        broker = FakeBroker()
        manager = PositionManager(broker)
        position = TradingPosition(make_position())

        manager.close_position(position)

        for _ in range(20):
            if broker.orders:
                break
            time.sleep(0.01)

        manager.stop()

        self.assertEqual(broker.orders[0][0], "close")
        self.assertEqual(Database().count_order_events(), 1)

    def test_recording_runtime_only_subscribes_prices(self):
        broker = FakeBroker()
        runtime = RecordingRuntime(lambda config: broker)

        runtime.start("demo")
        tick = make_tick()
        broker.emit_tick(tick)

        prices = []
        for _ in range(20):
            prices = runtime.get_prices()
            if prices:
                break
            time.sleep(0.01)

        status = runtime.get_status()
        runtime.stop()

        self.assertEqual(len(broker.price_subscriptions), len(RECORDING_INSTRUMENTS))
        self.assertEqual([sub[0] for sub in broker.price_subscriptions], RECORDING_INSTRUMENTS)
        self.assertEqual(
            status["instrument_labels"][RECORDING_INSTRUMENTS[0].symbol],
            RECORDING_INSTRUMENTS[0].label,
        )
        self.assertEqual(
            status["subscriptions"][0]["instrument_label"],
            RECORDING_INSTRUMENTS[0].label,
        )
        self.assertEqual(prices[0]["instrument_label"], RECORDING_INSTRUMENTS[-1].label)
        self.assertEqual(prices[0]["spread"], tick.ask - tick.bid)
        self.assertFalse(hasattr(runtime, "close_position"))
        self.assertFalse(hasattr(runtime, "update_position"))
        self.assertEqual(broker.orders, [])
        self.assertTrue(broker.disconnected)

    def test_trading_and_recording_are_mutually_exclusive(self):
        manager = TradingManager()
        manager.trading_runtime = FakeRuntime("trading")
        manager.recording_runtime = FakeRuntime("recording")

        manager.start_recording("demo")
        with self.assertRaisesRegex(ValueError, "Disconnect recorder"):
            manager.start_trading("demo")

        manager.stop_recording()
        manager.start_trading("demo")
        with self.assertRaisesRegex(ValueError, "Disconnect trading"):
            manager.start_recording("demo")

    def test_trading_auto_connect_is_disabled_by_default(self):
        previous = os.environ.pop("FT_IG_AUTO_CONNECT", None)
        try:
            manager = TradingManager()
            self.assertFalse(manager._env_enabled("FT_IG_AUTO_CONNECT", default=False))
        finally:
            if previous is not None:
                os.environ["FT_IG_AUTO_CONNECT"] = previous


if __name__ == "__main__":
    unittest.main()
