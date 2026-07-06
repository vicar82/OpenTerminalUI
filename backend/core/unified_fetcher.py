from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional

from backend.adapters.base import OHLCV, QuoteResponse
from backend.adapters.registry import get_adapter_registry
from backend.core.finnhub_client import FinnhubClient
from backend.core.fmp_client import FMPClient
from backend.core.yahoo_client import YahooClient
from backend.shared.market_classifier import market_classifier
from backend.services.orderbook_service import service as orderbook_service
from backend.api.schemas.market_data import MarketDepth, DepthLevel

logger = logging.getLogger(__name__)

_RANGE_TO_DAYS = {
    "1d": 1,
    "5d": 5,
    "7d": 7,
    "1mo": 31,
    "3mo": 92,
    "6mo": 183,
    "1y": 366,
    "2y": 731,
    "5y": 3653,
    "10y": 3653,
    "max": 3653,
}


def _to_float(value: Any) -> Optional[float]:
    if value in (None, "", "NA", "N/A", "-"):
        return None
    try:
        out = float(value)
        if out != out:  # NaN guard
            return None
        return out
    except (TypeError, ValueError):
        return None


def _is_yahoo_native_symbol(symbol: str) -> bool:
    return symbol.startswith("^") or symbol.endswith("=F") or symbol.endswith("=X")


def _range_to_dates(range_str: str) -> tuple[date, date]:
    normalized = str(range_str or "1y").strip().lower() or "1y"
    end = datetime.now(timezone.utc).date()
    if normalized == "ytd":
        return date(end.year, 1, 1), end
    days = _RANGE_TO_DAYS.get(normalized, 366)
    return end - timedelta(days=days), end


def _chart_payload_from_rows(rows: list[OHLCV]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: int(row.t))
    return {
        "chart": {
            "result": [
                {
                    "timestamp": [int(row.t) for row in ordered],
                    "indicators": {
                        "quote": [
                            {
                                "open": [float(row.o) for row in ordered],
                                "high": [float(row.h) for row in ordered],
                                "low": [float(row.l) for row in ordered],
                                "close": [float(row.c) for row in ordered],
                                "volume": [float(row.v) for row in ordered],
                            }
                        ]
                    },
                }
            ],
            "error": None,
        }
    }


def _quote_payload_from_adapter(quote: QuoteResponse) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "symbol": quote.symbol,
        "price": quote.price,
        "last_price": quote.price,
        "regularMarketPrice": quote.price,
        "c": quote.price,
        "change": quote.change,
        "regularMarketChange": quote.change,
        "d": quote.change,
        "change_pct": quote.change_pct,
        "regularMarketChangePercent": quote.change_pct,
        "dp": quote.change_pct,
        "currency": quote.currency,
    }
    if quote.ts:
        payload["ts"] = quote.ts
    return payload


def _extract_quote_price(payload: dict[str, Any]) -> tuple[float | None, float | None, str]:
    if not isinstance(payload, dict):
        return None, None, "unavailable"
    if payload.get("last_price") is not None:
        return _to_float(payload.get("last_price")), _to_float(payload.get("change_pct")), "adapter"
    if payload.get("priceInfo") is not None:
        return _to_float(((payload.get("priceInfo") or {}).get("lastPrice"))), _to_float(((payload.get("priceInfo") or {}).get("pChange"))), "moex"
    if payload.get("regularMarketPrice") is not None:
        return _to_float(payload.get("regularMarketPrice")), _to_float(payload.get("regularMarketChangePercent")), "yahoo"
    if payload.get("price") is not None:
        return _to_float(payload.get("price")), _to_float(payload.get("change_pct")), "fmp"
    if payload.get("c") is not None:
        return _to_float(payload.get("c")), _to_float(payload.get("dp")), "finnhub"
    return None, None, "unavailable"


async def _adapter_exchange_and_symbol(symbol: str) -> tuple[str, str]:
    normalized = symbol.strip().upper()
    if normalized.startswith("CRYPTO:"):
        return "CRYPTO", normalized
    if "-USD" in normalized or normalized.endswith("USD"):
        return "CRYPTO", normalized if normalized.startswith("CRYPTO:") else f"CRYPTO:{normalized}"
    if _is_yahoo_native_symbol(normalized):
        return "", normalized
    classification = await market_classifier.classify(normalized)
    return classification.exchange or "MOEX", normalized

@dataclass
class UnifiedFetcher:
    yahoo: YahooClient
    fmp: FMPClient
    finnhub: FinnhubClient

    @classmethod
    def build_default(cls) -> "UnifiedFetcher":
        return cls(
            yahoo=YahooClient(),
            fmp=FMPClient(),
            finnhub=FinnhubClient(),
        )

    async def startup(self) -> None:
        pass

    async def shutdown(self) -> None:
        await asyncio.gather(
            self.yahoo.close(),
            self.fmp.close(),
            self.finnhub.close(),
            return_exceptions=True,
        )

    def _has_yahoo_fundamentals(self, y_fund: Any) -> bool:
        if not isinstance(y_fund, dict) or not y_fund:
            return False
        return any(k.startswith("annual") or k.startswith("quarterly") for k in y_fund.keys())

    async def fetch_history(self, ticker: str, range_str: str = "1y", interval: str = "1d") -> Dict[str, Any]:
        symbol = ticker.strip().upper()
        exchange, adapter_symbol = await _adapter_exchange_and_symbol(symbol)

        if exchange:
            start_date, end_date = _range_to_dates(range_str)
            try:
                rows = await get_adapter_registry().invoke(exchange, "get_history", adapter_symbol, interval, start_date, end_date)
                if isinstance(rows, list) and rows:
                    return _chart_payload_from_rows(rows)
            except Exception as e:
                logger.debug("Adapter history failed for %s via %s: %s", symbol, exchange, e)

        try:
            yahoo_sym = await market_classifier.yfinance_symbol(symbol)
            data = await self.yahoo.get_chart(yahoo_sym, range_str, interval)
            if data and "chart" in data:
                return data
        except Exception as e:
            logger.warning(f"Yahoo history failed for {symbol}: {e}")

        try:
            fmp_data = await self.fmp.get_historical_price_full(symbol)
            if fmp_data:
                return fmp_data
        except Exception as e:
            logger.warning(f"FMP history failed for {symbol}: {e}")

        return {}

    async def fetch_quote(self, ticker: str) -> Dict[str, Any]:
        symbol = ticker.strip().upper()
        exchange, adapter_symbol = await _adapter_exchange_and_symbol(symbol)

        if exchange:
            try:
                quote = await get_adapter_registry().invoke(exchange, "get_quote", adapter_symbol)
                if isinstance(quote, QuoteResponse):
                    return _quote_payload_from_adapter(quote)
            except Exception as e:
                logger.debug("Adapter quote failed for %s via %s: %s", symbol, exchange, e)

        cls = await market_classifier.classify(symbol)

        try:
            yahoo_sym = await market_classifier.yfinance_symbol(symbol)
            data = await self.yahoo.get_quotes([yahoo_sym])
            if data:
                return data[0]
        except Exception as e:
             logger.debug(f"Yahoo quote failed for {symbol}: {e}")

        try:
            data = await self.fmp.get_quote(symbol)
            if data:
                return data
        except Exception as e:
             logger.debug(f"FMP quote failed for {symbol}: {e}")

        return {}

    # --- SNAPSHOT (Parallel) ---
    async def fetch_stock_snapshot(self, ticker: str) -> dict[str, Any]:
        symbol = ticker.strip().upper()
        cls = await market_classifier.classify(symbol)
        ysym = await market_classifier.yfinance_symbol(symbol)
        quote_payload = await self.fetch_quote(symbol)
        price, change_pct, price_source = _extract_quote_price(quote_payload)

        # Launch parallel requests
        moex_summary_task = self._moex_summary(symbol) if cls.country_code == "RU" else asyncio.sleep(0, result={})
        yahoo_summary_task = self.yahoo.get_quote_summary(
            ysym, ["financialData", "summaryDetail", "defaultKeyStatistics", "assetProfile"]
        )
        yahoo_quotes_task = self.yahoo.get_quotes([ysym])
        fmp_task = self.fmp.get_quote(symbol)
        finnhub_task = self.finnhub.get_company_profile(symbol)

        results = await asyncio.gather(
            moex_summary_task, yahoo_summary_task, yahoo_quotes_task, fmp_task, finnhub_task,
            return_exceptions=True,
        )

        moex_q, yahoo_summary, yahoo_quotes, fmp_q, finnhub_p = results

        # Helpers
        def _get_val(obj, *keys):
            for k in keys:
                if isinstance(obj, dict):
                    obj = obj.get(k)
                else:
                    return None
            return obj

        def _yraw(obj: dict, key: str) -> Optional[float]:
            """Extract raw numeric value from Yahoo's {raw: N, fmt: '...'} format."""
            v = obj.get(key)
            if isinstance(v, dict):
                return _to_float(v.get("raw"))
            return _to_float(v)

        # Extract data
        mq = moex_q if isinstance(moex_q, dict) else {}
        ys = yahoo_summary if isinstance(yahoo_summary, dict) else {}
        yq_rows = yahoo_quotes if isinstance(yahoo_quotes, list) else []
        yq = yq_rows[0] if yq_rows and isinstance(yq_rows[0], dict) else {}
        fq = fmp_q if isinstance(fmp_q, dict) else {}
        fp = finnhub_p if isinstance(finnhub_p, dict) else {}

        # Yahoo quoteSummary modules
        fd = ys.get("financialData", {})   # ROE, ROA, margins, growth
        sd = ys.get("summaryDetail", {})   # PE, PB, div yield, beta, market cap
        ks = ys.get("defaultKeyStatistics", {})  # EV, EV/EBITDA, forward PE
        ap = ys.get("assetProfile", {})    # sector, industry

        # --- Synthesize fundamental fields ---
        price = price or _to_float(mq.get("last")) or _yraw(fd, "currentPrice") or _to_float(fq.get("price"))
        change_pct = change_pct or _to_float(mq.get("changePct"))

        pe = _yraw(sd, "trailingPE") or _to_float(fq.get("pe"))

        market_cap = _yraw(sd, "marketCap") or _to_float(fq.get("marketCap"))

        company_name = mq.get("shortName") or \
                       yq.get("shortName") or \
                       yq.get("longName") or \
                       fq.get("name") or \
                       fp.get("name")
        exchange = mq.get("exchange") or cls.exchange or "MOEX"
        country_code = cls.country_code
        indices: list[str] = []

        forward_pe = _yraw(ks, "forwardPE") or _yraw(sd, "forwardPE")
        pb = _yraw(ks, "priceToBook") or _yraw(sd, "priceToBook")
        ps = _yraw(sd, "priceToSalesTrailing12Months")
        ev_ebitda = _yraw(ks, "enterpriseToEbitda")
        enterprise_value = _yraw(ks, "enterpriseValue")

        roe = _yraw(fd, "returnOnEquity")
        roa = _yraw(fd, "returnOnAssets")
        op_margin = _yraw(fd, "operatingMargins")
        net_margin = _yraw(fd, "profitMargins")
        rev_growth = _yraw(fd, "revenueGrowth")
        eps_growth = _yraw(fd, "earningsGrowth")
        div_yield = _yraw(sd, "dividendYield") or _yraw(sd, "trailingAnnualDividendYield")
        beta = _yraw(sd, "beta") or _to_float(fp.get("beta"))

        return {
            "ticker": symbol,
            "company_name": company_name,
            "current_price": price,
            "change_pct": change_pct,
            "market_cap": market_cap,
            "enterprise_value": enterprise_value,
            "pe": pe,
            "forward_pe": forward_pe,
            "pb": pb,
            "ps": ps,
            "ev_ebitda": ev_ebitda,
            "roe_pct": roe * 100 if roe else None,
            "roa_pct": roa * 100 if roa else None,
            "op_margin_pct": op_margin * 100 if op_margin else None,
            "net_margin_pct": net_margin * 100 if net_margin else None,
            "rev_growth_pct": rev_growth * 100 if rev_growth else None,
            "eps_growth_pct": eps_growth * 100 if eps_growth else None,
            "div_yield_pct": div_yield * 100 if div_yield else None,
            "beta": beta,
            "sector": ap.get("sector") or fp.get("finnhubIndustry"),
            "industry": ap.get("industry") or fp.get("finnhubIndustry") or ap.get("sector"),
            "country_code": country_code,
            "exchange": str(exchange),
            "currency": cls.currency,
            "flag_emoji": cls.flag_emoji,
            "has_futures": cls.has_futures,
            "has_options": cls.has_options,
            "market_status": cls.market_status,
            "indices": indices,
            "details": {
                "moex": bool(mq),
                "yahoo": bool(ys),
                "fmp": bool(fq),
                "finnhub": bool(fp),
                "price_source": price_source,
            },
        }

    async def _moex_summary(self, symbol: str) -> dict[str, Any]:
        """Minimal MOEX quote summary for snapshot synthesis."""
        try:
            quote = await get_adapter_registry().invoke("MOEX", "get_quote", symbol)
            if isinstance(quote, QuoteResponse):
                return {
                    "symbol": quote.symbol,
                    "last": quote.price,
                    "changePct": quote.change_pct,
                    "shortName": quote.company_name,
                    "exchange": "MOEX",
                }
        except Exception as exc:
            logger.debug("MOEX summary failed for %s: %s", symbol, exc)
        return {}

    # --- FUNDAMENTALS: Yahoo primary, FMP fallback only if Yahoo unavailable ---
    async def fetch_10yr_financials(self, ticker: str) -> Dict[str, Any]:
        symbol = ticker.strip().upper()
        ysym = await market_classifier.yfinance_symbol(symbol)

        y_fund: Any = {}
        try:
            y_fund = await self.yahoo.get_fundamentals_timeseries(ysym)
        except Exception as exc:
            logger.debug("Yahoo fundamentals failed for %s: %s", symbol, exc)

        f_inc: Any = []
        f_bal: Any = []
        f_cf: Any = []
        if not self._has_yahoo_fundamentals(y_fund):
            results = await asyncio.gather(
                self.fmp.get_income_statement(symbol, limit=20),
                self.fmp.get_balance_sheet(symbol, limit=20),
                self.fmp.get_cash_flow(symbol, limit=20),
                return_exceptions=True,
            )
            f_inc, f_bal, f_cf = results

        return {
            "symbol": symbol,
            "yahoo_fundamentals": y_fund if not isinstance(y_fund, Exception) else {},
            "fmp_income": f_inc if not isinstance(f_inc, Exception) else [],
            "fmp_balance": f_bal if not isinstance(f_bal, Exception) else [],
            "fmp_cashflow": f_cf if not isinstance(f_cf, Exception) else [],
        }

    async def fetch_pit_fundamentals_records(self, ticker: str) -> list[dict[str, Any]]:
        from backend.services.pit_fundamentals_service import (
            _records_from_fmp_rows,
            _records_from_yahoo_timeseries,
        )

        symbol = ticker.strip().upper()
        cls = await market_classifier.classify(symbol)
        market = cls.country_code
        ysym = await market_classifier.yfinance_symbol(symbol)
        records: list[dict[str, Any]] = []

        try:
            yahoo_payload = await self.yahoo.get_fundamentals_timeseries(ysym)
            for record in _records_from_yahoo_timeseries(symbol, yahoo_payload, market):
                records.append(record.__dict__)
        except Exception as exc:
            logger.debug("Yahoo PIT fundamentals failed for %s: %s", symbol, exc)

        fmp_symbol = ysym if market == "IN" else symbol
        try:
            fmp_results = await asyncio.gather(
                self.fmp.get_income_statement(fmp_symbol, period="annual", limit=20),
                self.fmp.get_income_statement(fmp_symbol, period="quarter", limit=40),
                self.fmp.get_balance_sheet(fmp_symbol, period="annual", limit=20),
                self.fmp.get_balance_sheet(fmp_symbol, period="quarter", limit=40),
                self.fmp.get_cash_flow(fmp_symbol, period="annual", limit=20),
                self.fmp.get_cash_flow(fmp_symbol, period="quarter", limit=40),
                return_exceptions=True,
            )
            for rows in fmp_results:
                if isinstance(rows, list):
                    for record in _records_from_fmp_rows(symbol, rows, "fmp", market):
                        records.append(record.__dict__)
        except Exception as exc:
            logger.debug("FMP PIT fundamentals failed for %s: %s", symbol, exc)

        return records

    async def fetch_shareholding(self, ticker: str) -> Dict[str, Any]:
        symbol = ticker.strip().upper()
        history: list[dict[str, float | str]] = []
        warning: str | None = None

        # Fallback: Yahoo major holders snapshot (single point, not historical trend).
        try:
            ysym = await market_classifier.yfinance_symbol(symbol)
            ysum = await self.yahoo.get_quote_summary(ysym, ["majorHoldersBreakdown"])
            mh = ysum.get("majorHoldersBreakdown", {}) if isinstance(ysum, dict) else {}
            insiders = _to_float((mh.get("heldPercentInsiders") or {}).get("raw") if isinstance(mh.get("heldPercentInsiders"), dict) else mh.get("heldPercentInsiders"))
            institutions = _to_float((mh.get("heldPercentInstitutions") or {}).get("raw") if isinstance(mh.get("heldPercentInstitutions"), dict) else mh.get("heldPercentInstitutions"))
            promoter = (insiders or 0.0) * 100.0
            fii = (institutions or 0.0) * 100.0
            dii = 0.0
            public = max(0.0, 100.0 - promoter - fii - dii)
            if insiders is not None or institutions is not None:
                history.append(
                    {
                        "date": "Latest",
                        "promoter": promoter,
                        "fii": fii,
                        "dii": dii,
                        "public": public,
                    }
                )
                warning = "Showing Yahoo holders snapshot fallback"
        except Exception as exc:
            warning = f"Yahoo holders fallback unavailable: {exc}"

        # Last-resort deterministic fallback so UI sections still render.
        if not history:
            history.append(
                {
                    "date": "Latest",
                    "promoter": 0.0,
                    "fii": 0.0,
                    "dii": 0.0,
                    "public": 100.0,
                }
            )
            warning = (warning + " | " if warning else "") + "Using default fallback distribution"

        payload = {"ticker": symbol, "history": history}
        if warning:
            payload["warning"] = warning
        return payload

    async def fetch_corporate_actions(self, ticker: str) -> Dict[str, Any]:
        # MOEX free ISS API does not expose a structured corporate-actions feed.
        return {"ticker": ticker.strip().upper(), "actions": [], "source": "moex", "note": "Corporate actions not available via free MOEX ISS API"}

    async def fetch_analyst_consensus(self, ticker: str) -> Dict[str, Any]:
        # Finnhub is good for this
        return await self.finnhub.get_recommendation_trends(ticker.strip().upper())

    async def search_news(self, query: str, limit: int = 30) -> list[dict[str, Any]]:
        q = str(query or "").strip()
        if not q:
            return []
        try:
            rows = await self.yahoo.search_news(q, limit=limit)
            if isinstance(rows, list) and rows:
                return [row for row in rows if isinstance(row, dict)][:limit]
        except Exception as exc:
            logger.debug("Yahoo news search failed for %s: %s", q, exc)
        return []

    async def get_company_news(self, ticker: str, limit: int = 30) -> list[dict[str, Any]]:
        symbol = ticker.strip().upper()
        if not symbol or not self.finnhub.api_key:
            return []
        try:
            rows = await self.finnhub.get_company_news(symbol, limit=limit)
            return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
        except Exception as exc:
            logger.debug("Finnhub company news failed for %s: %s", symbol, exc)
            return []

    async def get_market_news(self, category: str = "general", limit: int = 30) -> list[dict[str, Any]]:
        if not self.finnhub.api_key:
            return []
        try:
            rows = await self.finnhub.get_market_news(category=category, limit=limit)
            return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
        except Exception as exc:
            logger.debug("Finnhub market news failed for %s: %s", category, exc)
            return []

    async def fetch_depth(self, ticker: str, levels: int = 10) -> MarketDepth:
        symbol = ticker.strip().upper()
        cls = await market_classifier.classify(symbol)

        # MOEX free ISS API does not expose a live order book; use synthetic fallback.
        snap = orderbook_service.get_snapshot(symbol, market_hint=cls.country_code, levels=levels)
        return MarketDepth(
            symbol=symbol,
            market=snap.market,
            as_of=snap.as_of,
            bids=[DepthLevel(price=b.price, size=b.size, orders=b.orders) for b in snap.bids],
            asks=[DepthLevel(price=a.price, size=a.size, orders=a.orders) for a in snap.asks],
            total_bid_quantity=snap.total_bid_quantity,
            total_ask_quantity=snap.total_ask_quantity,
        )
