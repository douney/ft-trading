import os
import sqlite3
import threading
from datetime import date, datetime, time, timedelta

from modules.base_type.instrument import Instrument
from modules.base_type.position import Position
from modules.base_type.singleton_meta import SingletonMeta
from modules.base_type.tick import Tick
from modules.config.env import load_env

load_env()

class Database(metaclass=SingletonMeta):
    FLUSH_LIMIT = 10
    
    DIR_PATH = os.path.join(os.getcwd(), "db")
    DEFAULT_DB_PATH = os.path.join(DIR_PATH, "trading.sqlite3")

    def __init__(self):
        self.db_path = os.environ.get("FT_DB_PATH", self.DEFAULT_DB_PATH)
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        self.lock = threading.Lock()
        self.ticks_db: dict[str, list[Tick]] = {}
        self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        with self.connection:
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ticks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    instrument_symbol TEXT NOT NULL,
                    bid REAL NOT NULL,
                    ask REAL NOT NULL,
                    timestamp_ms INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self.connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_ticks_symbol_time
                ON ticks (instrument_symbol, timestamp_ms)
                """
            )
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    deal_id TEXT NOT NULL,
                    instrument_symbol TEXT NOT NULL,
                    level REAL NOT NULL,
                    currency TEXT NOT NULL,
                    stop_level REAL,
                    limit_level REAL,
                    status TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    size REAL NOT NULL,
                    timestamp_ms INTEGER NOT NULL,
                    entry_level REAL NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS order_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    deal_id TEXT NOT NULL,
                    instrument_symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    size REAL NOT NULL,
                    level REAL NOT NULL,
                    stop_level REAL,
                    limit_level REAL,
                    timestamp_ms INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def add_tick(self, instrument: Instrument, tick: Tick) -> None:
        with self.lock:
            if instrument.symbol not in self.ticks_db:
                self.ticks_db[instrument.symbol] = []

            self.ticks_db[instrument.symbol].append(tick)

            if len(self.ticks_db[instrument.symbol]) >= self.FLUSH_LIMIT:
                self._flush_ticks_locked(instrument.symbol)

    def add_position(self, position: Position) -> None:
        with self.lock, self.connection:
            self.connection.execute(
                """
                INSERT INTO positions (
                    deal_id,
                    instrument_symbol,
                    level,
                    currency,
                    stop_level,
                    limit_level,
                    status,
                    direction,
                    size,
                    timestamp_ms,
                    entry_level
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    position.id,
                    position.instrument.symbol,
                    position.level,
                    str(position.currency),
                    position.stop_level,
                    position.limit_level,
                    str(position.status),
                    str(position.direction),
                    position.size,
                    position.timestamp,
                    position.entry_level,
                ),
            )

    def add_order_event(self, action: str, position: Position) -> None:
        with self.lock, self.connection:
            self.connection.execute(
                """
                INSERT INTO order_events (
                    action,
                    deal_id,
                    instrument_symbol,
                    direction,
                    size,
                    level,
                    stop_level,
                    limit_level,
                    timestamp_ms
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action,
                    position.id,
                    position.instrument.symbol,
                    str(position.direction),
                    position.size,
                    position.level,
                    position.stop_level,
                    position.limit_level,
                    position.timestamp,
                ),
            )

    def flush_ticks(self, instrument_symbol: str) -> None:
        with self.lock:
            self._flush_ticks_locked(instrument_symbol)

    def _flush_ticks_locked(self, instrument_symbol: str) -> None:
        ticks = self.ticks_db.get(instrument_symbol, [])
        if not ticks:
            return

        with self.connection:
            self.connection.executemany(
                """
                INSERT INTO ticks (
                    instrument_symbol,
                    bid,
                    ask,
                    timestamp_ms
                )
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        instrument_symbol,
                        tick.bid,
                        tick.ask,
                        tick.timestamp_ms,
                    )
                    for tick in ticks
                ],
            )

        self.ticks_db[instrument_symbol].clear()

    def flush_all_ticks(self) -> None:
        for instrument in list(self.ticks_db.keys()):
            if self.ticks_db[instrument]:
                self.flush_ticks(instrument)

    def load_ticks(self, instrument: Instrument, day: date | None = None) -> list[Tick]:
        self.flush_ticks(instrument.symbol)

        if day is None:
            day = date.today()

        start_ms, end_ms = self._day_range_ms(day)
        with self.lock:
            rows = self.connection.execute(
                """
                SELECT bid, ask, timestamp_ms
                FROM ticks
                WHERE instrument_symbol = ?
                  AND timestamp_ms >= ?
                  AND timestamp_ms < ?
                ORDER BY timestamp_ms ASC
                """,
                (instrument.symbol, start_ms, end_ms),
            ).fetchall()

        return [Tick(float(bid), float(ask), int(timestamp_ms)) for bid, ask, timestamp_ms in rows]

    def count_order_events(self) -> int:
        with self.lock:
            row = self.connection.execute("SELECT COUNT(*) FROM order_events").fetchone()
        return int(row[0])

    def close(self) -> None:
        self.flush_all_ticks()
        self.connection.close()

    def _day_range_ms(self, day: date) -> tuple[int, int]:
        start = datetime.combine(day, time.min)
        end = start + timedelta(days=1)
        return int(start.timestamp() * 1000), int(end.timestamp() * 1000)
