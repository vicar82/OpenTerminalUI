from __future__ import annotations

import asyncio
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from backend.api.deps import get_unified_fetcher
from backend.config.settings import get_settings
from backend.db.base import sqlite_file_from_url
from backend.shared.sqlite_utils import configure_sqlite_connection

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _to_iso_date(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if hasattr(value, "isoformat"):
        try:
            text = value.isoformat()
            return str(text)[:10]
        except Exception:
            return ""
    text = str(value).strip()
    return text[:10] if text else ""


@dataclass
class FutureContractRow:
    underlying: str
    expiry_date: str
    exchange: str
    tradingsymbol: str
    instrument_token: int
    lot_size: int
    tick_size: float
    updated_at: str


class InstrumentsLoader:
    def __init__(self, refresh_interval_seconds: int = 24 * 60 * 60) -> None:
        settings = get_settings()
        self.sqlite_path = sqlite_file_from_url(settings.sqlite_url)
        self.refresh_interval_seconds = refresh_interval_seconds
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._loop(), name="instruments-loader")
        logger.info("Instruments loader started")

    async def stop(self) -> None:
        if not self._task:
            return
        self._stop_event.set()
        try:
            await self._task
        finally:
            self._task = None
        logger.info("Instruments loader stopped")

    async def refresh_once(self) -> bool:
        """Placeholder refresh: MOEX futures are not loaded via Kite/NFO."""
        logger.info("Futures instruments refresh skipped: MOEX futures loader not implemented")
        return False

    async def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self.refresh_once()
            except Exception as exc:
                logger.warning("Futures instruments loader loop failed: %s", exc)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.refresh_interval_seconds)
            except asyncio.TimeoutError:
                continue

    def _connect(self) -> sqlite3.Connection:
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.sqlite_path), check_same_thread=False, timeout=15)
        configure_sqlite_connection(conn)
        return conn

    def _upsert_rows(self, rows: list[FutureContractRow]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS future_contracts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    underlying TEXT NOT NULL,
                    expiry_date TEXT NOT NULL,
                    exchange TEXT NOT NULL,
                    tradingsymbol TEXT NOT NULL,
                    instrument_token INTEGER NOT NULL,
                    lot_size INTEGER NOT NULL DEFAULT 0,
                    tick_size REAL NOT NULL DEFAULT 0.0,
                    updated_at TEXT NOT NULL,
                    UNIQUE(exchange, tradingsymbol)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_future_contracts_underlying ON future_contracts(underlying)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_future_contracts_expiry ON future_contracts(expiry_date)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_future_contracts_token ON future_contracts(instrument_token)")
            conn.executemany(
                """
                INSERT INTO future_contracts(
                    underlying, expiry_date, exchange, tradingsymbol, instrument_token, lot_size, tick_size, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(exchange, tradingsymbol) DO UPDATE SET
                    underlying = excluded.underlying,
                    expiry_date = excluded.expiry_date,
                    instrument_token = excluded.instrument_token,
                    lot_size = excluded.lot_size,
                    tick_size = excluded.tick_size,
                    updated_at = excluded.updated_at
                """,
                [
                    (
                        row.underlying,
                        row.expiry_date,
                        row.exchange,
                        row.tradingsymbol,
                        row.instrument_token,
                        row.lot_size,
                        row.tick_size,
                        row.updated_at,
                    )
                    for row in rows
                ],
            )
            conn.commit()


_instruments_loader = InstrumentsLoader()


def get_instruments_loader() -> InstrumentsLoader:
    return _instruments_loader
