from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from typing import Any

from backend.core.ttl_policy import market_open_now
from backend.api.deps import get_unified_fetcher
from backend.fno.services.greeks_engine import get_greeks_engine
from backend.shared.cache import cache as default_cache
from backend.shared.symbol_resolver import SymbolResolver

INDEX_SYMBOLS = {"IMOEX", "RTSI"}


class OptionChainFetcher:
    """Fetches and normalizes option chain data (US via adapter; MOEX returns empty stub)."""

    def __init__(
        self,
        cache: Any = None,
        symbol_resolver: SymbolResolver | None = None,
    ) -> None:
        self._cache = cache or default_cache
        self._resolver = symbol_resolver or SymbolResolver()
        self._greeks = get_greeks_engine()

    def _get_us_adapter(self):
        from backend.adapters.us_options_adapter import USOptionsAdapter
        return USOptionsAdapter()

    def _get_market_classifier(self):
        from backend.shared.market_classifier import market_classifier
        return market_classifier

    def _to_float(self, value: Any, default: float = 0.0) -> float:
        try:
            out = float(value)
            if out != out:
                return default
            return out
        except (TypeError, ValueError):
            return default

    def _to_int(self, value: Any, default: int = 0) -> int:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    def _pick_expiry(self, available: list[str], expiry: str | None) -> str:
        if not available:
            return expiry or ""
        if expiry and expiry in available:
            return expiry
        today = date.today()
        future_sorted = sorted(available)
        for val in future_sorted:
            try:
                if date.fromisoformat(val) >= today:
                    return val
            except Exception:
                continue
        return future_sorted[0]

    def _find_atm(self, spot_price: float, strikes: list[dict[str, Any]]) -> float:
        if not strikes:
            return 0.0
        vals = [self._to_float(row.get("strike_price"), 0.0) for row in strikes]
        vals = [v for v in vals if v > 0]
        if not vals:
            return 0.0
        return min(vals, key=lambda x: abs(x - spot_price))

    def _days_to_expiry(self, expiry_iso: str) -> int:
        try:
            d = date.fromisoformat(expiry_iso)
            return max((d - date.today()).days, 1)
        except Exception:
            return 1

    def _normalize_leg(self, leg: dict[str, Any] | None, spot: float, strike: float, dte: int, option_type: str) -> dict[str, Any]:
        if not isinstance(leg, dict):
            return {
                "oi": 0,
                "oi_change": 0,
                "volume": 0,
                "iv": 0.0,
                "ltp": 0.0,
                "bid": 0.0,
                "ask": 0.0,
                "price_change": 0.0,
                "greeks": self._greeks.compute_greeks(spot, strike, dte, 0.0, option_type),
            }
        iv = self._to_float(leg.get("impliedVolatility"), 0.0)
        ltp = self._to_float(leg.get("lastPrice"), 0.0)
        if iv <= 0 and ltp > 0:
            iv = self._greeks.compute_iv(spot, strike, dte, ltp, option_type)
        return {
            "oi": self._to_int(leg.get("openInterest"), 0),
            "oi_change": self._to_int(leg.get("changeinOpenInterest"), 0),
            "volume": self._to_int(leg.get("totalTradedVolume"), 0),
            "iv": round(iv, 4),
            "ltp": round(ltp, 4),
            "bid": round(self._to_float(leg.get("bidprice"), 0.0), 4),
            "ask": round(self._to_float(leg.get("askPrice"), 0.0), 4),
            "price_change": round(self._to_float(leg.get("change"), 0.0), 4),
            "greeks": self._greeks.compute_greeks(spot, strike, dte, iv, option_type),
        }

    async def get_option_chain(self, symbol: str, expiry: str | None = None, strike_range: int = 20) -> dict[str, Any]:
        """
        Fetch full option chain for a US symbol. MOEX options are not supported in the free tier.
        """
        symbol_u = (symbol or "").strip().upper()
        empty_chain = {
            "symbol": symbol_u,
            "spot_price": 0.0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "expiry_date": expiry or "",
            "available_expiries": [],
            "atm_strike": 0.0,
            "strikes": [],
            "totals": {"ce_oi_total": 0, "pe_oi_total": 0, "ce_volume_total": 0, "pe_volume_total": 0, "pcr_oi": 0.0, "pcr_volume": 0.0},
        }
        if not symbol_u:
            return empty_chain

        market_classifier = self._get_market_classifier()
        cls = await market_classifier.classify(symbol_u)
        is_us = cls.country_code == "US"

        cache_key = self._cache.build_key("fno_option_chain", symbol_u, {"expiry": expiry or "", "range": int(strike_range)})
        cached = await self._cache.get(cache_key)
        if cached:
            return cached

        if is_us:
            us_adapter = self._get_us_adapter()
            if not expiry:
                expiries = await us_adapter.get_expiry_dates(symbol_u)
                expiry = self._pick_expiry(expiries, None)

            chain = await us_adapter.get_option_chain(symbol_u, expiry, strike_range)
            if not chain.get("available_expiries"):
                chain["available_expiries"] = await us_adapter.get_expiry_dates(symbol_u)
            chain["market"] = "US"
        else:
            # MOEX free ISS API does not expose option chains; return empty stub.
            chain = {**empty_chain, "market": "MOEX", "note": "MOEX option chain not available via free ISS API"}

        # Add IV Rank and Percentile
        try:
            from backend.fno.services.iv_engine import get_iv_engine
            iv_engine = get_iv_engine()
            atm_iv = iv_engine._atm_iv(chain)
            iv_percentile, iv_rank = await iv_engine._iv_rank_percentile(symbol_u, atm_iv)
            chain["iv_rank"] = iv_rank
            chain["iv_percentile"] = iv_percentile
            chain["atm_iv"] = atm_iv
        except Exception:
            chain["iv_rank"] = 0.0
            chain["iv_percentile"] = 0.0
            chain["atm_iv"] = 0.0

        ttl = 60 if market_open_now() else 120
        await self._cache.set(cache_key, chain, ttl=ttl)
        return chain

    async def get_expiry_dates(self, symbol: str) -> list[str]:
        symbol_u = symbol.strip().upper()
        market_classifier = self._get_market_classifier()
        cls = await market_classifier.classify(symbol_u)
        if cls.country_code == "US":
            return await self._get_us_adapter().get_expiry_dates(symbol_u)
        return []
