from __future__ import annotations

import asyncio
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from backend.config.settings import get_settings
from backend.db.base import sqlite_file_from_url
from backend.shared.sqlite_utils import configure_sqlite_connection

logger = logging.getLogger(__name__)

SUPPORTED_EXCHANGES = {"MOEX"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass
class InstrumentRow:
    exchange: str
    symbol: str
    token: int
    tradingsymbol: str
    updated_at: str


class InstrumentMapService:
    def __init__(self) -> None:
        settings = get_settings()
        self.sqlite_path = sqlite_file_from_url(settings.sqlite_url)
        self._init_lock = asyncio.Lock()
        self._ready = False

    async def initialize(self) -> None:
        async with self._init_lock:
            if self._ready:
                return
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(self._init_table)
            self._ready = True

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.sqlite_path), check_same_thread=False, timeout=15)
        configure_sqlite_connection(conn)
        return conn

    def _init_table(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS instrument_map (
                    exchange TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    token INTEGER NOT NULL,
                    tradingsymbol TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (exchange, symbol)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_instrument_map_token ON instrument_map (token)"
            )
            conn.commit()

    async def refresh_if_stale(self, _: object | None = None, force: bool = False) -> bool:
        """Placeholder refresh: MOEX ISS does not require instrument-token mapping."""
        await self.initialize()
        logger.info("Instrument map refresh skipped: MOEX uses symbol-native quotes")
        return True

    async def resolve_many(self, symbols: list[str]) -> dict[str, int]:
        await self.initialize()
        return await asyncio.to_thread(self._resolve_many, symbols)

    def _resolve_many(self, symbols: list[str]) -> dict[str, int]:
        out: dict[str, int] = {}
        parsed: list[tuple[str, str, str]] = []
        for token in symbols:
            raw = (token or "").strip().upper()
            if ":" not in raw:
                continue
            exchange, symbol = raw.split(":", 1)
            if exchange not in SUPPORTED_EXCHANGES or not symbol:
                continue
            parsed.append((raw, exchange, symbol))
        if not parsed:
            return out

        with self._connect() as conn:
            for full, exchange, symbol in parsed:
                row = conn.execute(
                    "SELECT token FROM instrument_map WHERE exchange = ? AND symbol = ?",
                    (exchange, symbol),
                ).fetchone()
                if row and isinstance(row[0], int):
                    out[full] = row[0]
        return out

    async def symbol_by_token_many(self, tokens: list[int]) -> dict[int, str]:
        await self.initialize()
        return await asyncio.to_thread(self._symbol_by_token_many, tokens)

    def _symbol_by_token_many(self, tokens: list[int]) -> dict[int, str]:
        if not tokens:
            return {}
        unique_tokens = sorted({int(t) for t in tokens if isinstance(t, int)})
        if not unique_tokens:
            return {}
        placeholders = ",".join("?" for _ in unique_tokens)
        out: dict[int, str] = {}
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT exchange, symbol, token FROM instrument_map WHERE token IN ({placeholders})",
                tuple(unique_tokens),
            ).fetchall()
            for exchange, symbol, token in rows:
                if isinstance(exchange, str) and isinstance(symbol, str) and isinstance(token, int):
                    out[token] = f"{exchange.upper()}:{symbol.upper()}"
        return out


_instrument_map_service = InstrumentMapService()


def get_instrument_map_service() -> InstrumentMapService:
    return _instrument_map_service
