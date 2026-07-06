from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import httpx

from backend.adapters.base import DataAdapter, FuturesContract, Instrument, OHLCV, OptionChain, QuoteResponse


def _f(value: Any) -> float | None:
    try:
        out = float(value)
        return out if out == out else None
    except (TypeError, ValueError):
        return None


class MOEXClient:
    """Minimal async client for Moscow Exchange ISS API.

    Uses the public, unauthenticated endpoints documented at
    https://www.moex.com/a2193. Quotes are fetched from the TQBR
    (main equity) board; indices use the SNDX board.
    """

    BASE_URL = "https://iss.moex.com/iss"

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.BASE_URL}{path}"
        async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
            resp = await client.get(url, params=params or {})
            resp.raise_for_status()
            return resp.json()

    def _board_for_symbol(self, symbol: str) -> tuple[str, str]:
        """Return (engine, market, board) tuple for a symbol."""
        sym = symbol.strip().upper()
        # Index tickers on MOEX
        if sym in {"IMOEX", "RTSI", "MOEX10", "MOEXCN", "MOEXEU", "MOEXMM"}:
            return ("stock", "index", "SNDX")
        # FX/board ETFs could be added here; default to main equity board.
        return ("stock", "shares", "TQBR")

    async def get_quote(self, symbol: str) -> dict[str, Any] | None:
        sym = symbol.strip().upper()
        engine, market, board = self._board_for_symbol(sym)
        try:
            data = await self._get(
                f"/engines/{engine}/markets/{market}/boards/{board}/securities/{sym}.json",
                {"iss.meta": "off", "iss.only": "securities", "securities.columns": "SECID,SHORTNAME,LAST,CLOSE,OPEN,HIGH,LOW,VALUE"},
            )
        except httpx.HTTPError:
            return None
        securities = ((data.get("securities") or {}).get("data") or [])
        if not securities:
            return None
        row = securities[0]
        # columns order: SECID, SHORTNAME, LAST, CLOSE, OPEN, HIGH, LOW, VALUE
        last = _f(row[2]) if len(row) > 2 else None
        close = _f(row[3]) if len(row) > 3 else None
        if last is None:
            last = close
        if last is None:
            return None
        change = (last - close) if close else 0.0
        change_pct = (change / close * 100) if close else 0.0
        return {
            "symbol": sym,
            "shortName": row[1] if len(row) > 1 else sym,
            "regularMarketPrice": last,
            "regularMarketChange": change,
            "regularMarketChangePercent": change_pct,
            "currency": "RUB",
        }

    async def get_history(
        self,
        symbol: str,
        start: date | None = None,
        end: date | None = None,
    ) -> list[OHLCV]:
        sym = symbol.strip().upper()
        engine, market, board = self._board_for_symbol(sym)
        start_date = (start or (datetime.utcnow().date() - timedelta(days=365))).strftime("%Y-%m-%d")
        end_date = (end or datetime.utcnow().date()).strftime("%Y-%m-%d")
        try:
            data = await self._get(
                f"/engines/{engine}/markets/{market}/boards/{board}/securities/{sym}/candles.json",
                {
                    "iss.meta": "off",
                    "from": start_date,
                    "till": end_date,
                    "interval": "24",
                    "columns": "OPEN,CLOSE,HIGH,LOW,VALUE,VOLUME,BEGIN",
                },
            )
        except httpx.HTTPError:
            return []
        rows = ((data.get("candles") or {}).get("data") or [])
        out: list[OHLCV] = []
        for row in rows:
            if len(row) < 7:
                continue
            o, c, h, l, value, volume, begin = row[:7]
            if None in (o, c, h, l, begin):
                continue
            try:
                ts = int(datetime.fromisoformat(str(begin).replace("Z", "+00:00")).timestamp())
            except ValueError:
                continue
            out.append(
                OHLCV(
                    t=ts,
                    o=float(o),
                    h=float(h),
                    l=float(l),
                    c=float(c),
                    v=float(volume or value or 0),
                )
            )
        return out

    async def search_instruments(self, query: str) -> list[Instrument]:
        q = query.strip().upper()
        if not q or len(q) < 2:
            return []
        try:
            data = await self._get(
                "/securities.json",
                {"iss.meta": "off", "q": q, "limit": 20},
            )
        except httpx.HTTPError:
            return []
        rows = ((data.get("securities") or {}).get("data") or [])
        out: list[Instrument] = []
        for row in rows:
            if len(row) < 5:
                continue
            # columns: SECID, NAME, SHORTNAME, ISIN, ...
            secid, name, shortname = row[0], row[1], row[2]
            if not secid or not str(secid).upper().startswith(q):
                continue
            out.append(
                Instrument(
                    symbol=str(secid).upper(),
                    name=str(shortname or name or secid),
                    exchange="MOEX",
                    currency="RUB",
                )
            )
        return out


class MOEXAdapter(DataAdapter):
    def __init__(self, client: MOEXClient | None = None) -> None:
        self.client = client or MOEXClient()

    async def get_quote(self, symbol: str) -> QuoteResponse | None:
        row = await self.client.get_quote(symbol)
        if not row:
            return None
        return QuoteResponse(
            symbol=str(row.get("symbol") or symbol).upper(),
            price=_f(row.get("regularMarketPrice")) or 0.0,
            change=_f(row.get("regularMarketChange")) or 0.0,
            change_pct=_f(row.get("regularMarketChangePercent")) or 0.0,
            currency="RUB",
            ts=None,
            company_name=row.get("shortName"),
        )

    async def get_history(self, symbol: str, timeframe: str, start: date, end: date) -> list[OHLCV]:
        return await self.client.get_history(symbol, start, end)

    async def search_instruments(self, query: str) -> list[Instrument]:
        return await self.client.search_instruments(query)

    async def get_fundamentals(self, symbol: str) -> dict[str, Any]:
        # MOEX ISS does not expose rich fundamentals in the free tier;
        # return a minimal payload so downstream code can degrade gracefully.
        return {"symbol": symbol.upper(), "source": "moex", "note": "Fundamentals not available via free MOEX ISS API"}

    async def supports_streaming(self) -> bool:
        return False

    async def get_option_chain(self, underlying: str, expiry: date) -> OptionChain | None:
        return None

    async def get_futures_chain(self, underlying: str) -> list[FuturesContract]:
        return []
