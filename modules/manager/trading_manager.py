import logging
import os
import threading
from typing import Optional

from modules.config.env import load_env
from modules.manager.money_manager import MoneyManagerConfig
from modules.manager.runtimes import BacktestRuntime, RecordingRuntime, TradingRuntime
from modules.web_api.index import WebAPI

logger = logging.getLogger(__name__)


class TradingManager(threading.Thread):
    def __init__(self):
        super().__init__()
        load_env()

        money_manager_config = MoneyManagerConfig(
            position_stop_distance=10
        )

        self.trading_runtime = TradingRuntime(money_manager_config)
        self.recording_runtime = RecordingRuntime()
        self.backtest_runtime = BacktestRuntime()
        self._runtime_lock = threading.RLock()
        self.web_api = WebAPI(self)

    def run(self):
        self.web_api.start()

        if self._env_enabled("FT_IG_AUTO_CONNECT", default=False):
            try:
                self.start_trading(os.environ.get("FT_IG_MODE", "demo"))
            except Exception as error:
                logger.error(f"Initial trading connection failed: {error}")

        if self._env_enabled("FT_RECORDING_AUTO_CONNECT", default=False):
            try:
                recording_mode = os.environ.get(
                    "FT_RECORDING_IG_MODE",
                    os.environ.get("FT_IG_MODE", "demo"),
                )
                self.start_recording(recording_mode)
            except Exception as error:
                logger.error(f"Initial recording connection failed: {error}")

        self.web_api.join()

    def stop(self):
        with self._runtime_lock:
            self.trading_runtime.stop()
            self.recording_runtime.stop()
        self.web_api.stop()

    def connect_broker(self, mode: str, passphrase: Optional[str] = None) -> dict:
        return self.start_trading(mode, passphrase)

    def start_trading(self, mode: str, passphrase: Optional[str] = None) -> dict:
        with self._runtime_lock:
            if self.recording_runtime.get_status()["connected"]:
                raise ValueError("Disconnect recorder before starting trading")

            return self.trading_runtime.start(mode, passphrase)

    def stop_trading(self) -> dict:
        with self._runtime_lock:
            self.trading_runtime.stop()
            return self.trading_runtime.get_status()

    def start_recording(self, mode: str, passphrase: Optional[str] = None) -> dict:
        with self._runtime_lock:
            if self.trading_runtime.get_status()["connected"]:
                raise ValueError("Disconnect trading before starting recorder")

            return self.recording_runtime.start(mode, passphrase)

    def stop_recording(self) -> dict:
        with self._runtime_lock:
            self.recording_runtime.stop()
            return self.recording_runtime.get_status()

    def get_broker_status(self) -> dict:
        trading = self.trading_runtime.get_status()
        return {
            "connected": trading["connected"],
            "mode": trading["mode"],
            "available_modes": ["demo", "live"],
        }

    def get_runtime_status(self) -> dict:
        return {
            "available_modes": ["demo", "live"],
            "trading": self.trading_runtime.get_health(),
            "recording": self.recording_runtime.get_status(),
            "backtest": self.backtest_runtime.get_status(),
        }

    def get_health(self) -> dict:
        trading = self.trading_runtime.get_health()
        recording = self.recording_runtime.get_status()
        connected_runtime = trading if trading["connected"] else recording

        return {
            "broker": {
                "connected": connected_runtime["connected"],
                "mode": connected_runtime["mode"],
            },
            "open_positions": trading["open_positions"],
            "day_balance": trading["day_balance"],
            "last_trade_balance": trading["last_trade_balance"],
            "subscriptions": trading["subscriptions"],
            "trading": trading,
            "recording": recording,
            "backtest": self.backtest_runtime.get_status(),
        }

    def get_prices(self) -> list[dict]:
        prices = self.trading_runtime.get_prices() + self.recording_runtime.get_prices()
        return sorted(prices, key=lambda price: (price["runtime"], price["instrument"]))

    def get_positions(self) -> list:
        return self.trading_runtime.get_positions()

    def close_position(self, position_id: str) -> None:
        self.trading_runtime.close_position(position_id)

    def update_limit(self, position_id: str, distance: Optional[float]) -> dict:
        return self.trading_runtime.update_limit(position_id, distance)

    def update_stop_profit(self, position_id: str, distance: Optional[float]) -> dict:
        return self.trading_runtime.update_stop_profit(position_id, distance)

    def _env_enabled(self, name: str, default: bool) -> bool:
        value = os.environ.get(name)
        if value is None:
            return default

        return value.lower() not in ("0", "false", "no")
