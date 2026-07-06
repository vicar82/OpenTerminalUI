"""
Shareholding pattern service.
Returns quarterly shareholding data via FMP institutional holders fallback.
MOEX does not expose a free structured shareholding API.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field

from backend.shared.cache import cache


class ShareholdingCategory(BaseModel):
    category: str
    percentage: float
    shares: Optional[int] = None
    quarter: str


class ShareholdingPattern(BaseModel):
    symbol: str
    total_shares: int = 0
    promoter_holding: float = 0.0
    fii_holding: float = 0.0
    dii_holding: float = 0.0
    public_holding: float = 0.0
    government_holding: float = 0.0
    categories: list[ShareholdingCategory] = Field(default_factory=list)
    quarter: str
    as_of_date: str
    historical: list[dict] = Field(default_factory=list)
    source: str = "fmp"
    institutional_holders: list[dict[str, Any]] = Field(default_factory=list)
    warning: Optional[str] = None


def _to_float(value: Any) -> float:
    if value in (None, "", "-", "NA", "N/A"):
        return 0.0
    try:
        out = float(value)
        if out != out:
            return 0.0
        return out
    except (TypeError, ValueError):
        return 0.0


def _to_int(value: Any) -> Optional[int]:
    if value in (None, "", "-", "NA", "N/A"):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _normalize_symbol(symbol: str) -> str:
    raw = symbol.strip().upper()
    if "." in raw:
        return raw.split(".", 1)[0]
    return raw


def _quarter_sort_key(label: str) -> datetime:
    txt = (label or "").strip()
    for fmt in ("%b %Y", "%B %Y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(txt, fmt)
        except ValueError:
            continue
    return datetime.min


def _model_to_dict(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()  # type: ignore[attr-defined]
    return model.dict()


def _default_pattern_payload(symbol: str, warning: Optional[str] = None) -> dict[str, Any]:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    quarter = "Latest"
    categories = [
        {
            "category": "Public Shareholders",
            "percentage": 100.0,
            "shares": None,
            "quarter": quarter,
        }
    ]
    historical = [
        {
            "quarter": quarter,
            "promoter": 0.0,
            "fii": 0.0,
            "dii": 0.0,
            "public": 100.0,
            "government": 0.0,
        }
    ]
    return {
        "symbol": symbol,
        "total_shares": 0,
        "promoter_holding": 0.0,
        "fii_holding": 0.0,
        "dii_holding": 0.0,
        "public_holding": 100.0,
        "government_holding": 0.0,
        "categories": categories,
        "quarter": quarter,
        "as_of_date": today,
        "historical": historical,
        "source": "fallback",
        "institutional_holders": [],
        "warning": warning,
    }


class ShareholdingService:
    """
    Primary source: FMP institutional holders API.
    MOEX free ISS API does not expose structured shareholding patterns.
    """

    SHAREHOLDING_TTL = 86400

    async def get_shareholding(self, symbol: str) -> ShareholdingPattern:
        clean_symbol = _normalize_symbol(symbol)
        cache_key = cache.build_key("shareholding", clean_symbol, {})
        cached = await cache.get(cache_key)
        if isinstance(cached, dict):
            return ShareholdingPattern(**cached)

        fallback = await self.get_fmp_institutional(clean_symbol)
        pattern = ShareholdingPattern(**fallback)
        await cache.set(cache_key, _model_to_dict(pattern), ttl=self.SHAREHOLDING_TTL)
        return pattern

    async def get_historical_shareholding(self, symbol: str, quarters: int = 8) -> list[dict]:
        clean_symbol = _normalize_symbol(symbol)
        cache_key = cache.build_key("shareholding_trend", clean_symbol, {"quarters": quarters})
        cached = await cache.get(cache_key)
        if isinstance(cached, list):
            return cached

        fmp_payload = await self.get_fmp_institutional(clean_symbol)
        out = fmp_payload.get("historical") or _default_pattern_payload(clean_symbol).get("historical", [])
        await cache.set(cache_key, out, ttl=self.SHAREHOLDING_TTL)
        return out

    async def get_fmp_institutional(self, symbol: str) -> dict:
        api_key = os.getenv("FMP_API_KEY", "").strip()
        holders: list[dict[str, Any]] = []
        warning: Optional[str] = None

        if not api_key:
            warning = "FMP_API_KEY not configured"
        else:
            endpoint = f"https://financialmodelingprep.com/api/v3/institutional-holder/{symbol}"
            try:
                async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, trust_env=False) as client:
                    response = await client.get(endpoint, params={"apikey": api_key})
                    response.raise_for_status()
                    payload = response.json()
                    if isinstance(payload, list):
                        for row in payload[:50]:
                            if not isinstance(row, dict):
                                continue
                            holder_name = str(
                                row.get("holder")
                                or row.get("holderName")
                                or row.get("investorName")
                                or "Institutional Holder"
                            )
                            shares = _to_int(row.get("shares") or row.get("sharesNumber") or row.get("position"))
                            change = _to_float(row.get("change") or row.get("changeInShares"))
                            holders.append(
                                {
                                    "holder": holder_name,
                                    "shares": shares or 0,
                                    "change": round(change, 2),
                                    "date_reported": str(row.get("dateReported") or row.get("reportDate") or ""),
                                }
                            )
            except Exception as exc:
                warning = f"FMP institutional fallback unavailable: {exc}"

        quarter = "Latest"
        as_of = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        payload = _default_pattern_payload(symbol, warning)
        payload["source"] = "fmp"
        payload["institutional_holders"] = holders
        payload["quarter"] = quarter
        payload["as_of_date"] = as_of
        return payload
