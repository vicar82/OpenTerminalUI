from __future__ import annotations

import pytest
from sqlalchemy import delete

from backend.core.research.index import search_items
from backend.core.research.models import ResearchItem


SYNTHETIC_ITEMS = [
    {
        "source": "arxiv",
        "external_id": "abs/test-research-001v1",
        "title": "Transformer volatility forecasting",
        "authors": ["Ada Lovelace", "Grace Hopper"],
        "abstract": "A deterministic volatility model for equity option surfaces and risk forecasts.",
        "url": "http://arxiv.org/abs/test-research-001v1",
        "categories": ["q-fin.ST", "cs.LG"],
        "published_at": "2026-01-01T00:00:00Z",
    },
    {
        "source": "arxiv",
        "external_id": "abs/test-research-002v1",
        "title": "Market microstructure liquidity",
        "authors": ["Katherine Johnson"],
        "abstract": "Limit order book imbalance and liquidity stress indicators.",
        "url": "http://arxiv.org/abs/test-research-002v1",
        "categories": ["q-fin.TR"],
        "published_at": "2026-01-02T00:00:00Z",
    },
    {
        "source": "arxiv",
        "external_id": "abs/test-research-003v1",
        "title": "Macro regime allocation",
        "authors": ["Mary Jackson"],
        "abstract": "Portfolio allocation across inflation and growth regimes.",
        "url": "http://arxiv.org/abs/test-research-003v1",
        "categories": ["q-fin.PM"],
        "published_at": "2026-01-03T00:00:00Z",
    },
]


@pytest.fixture(autouse=True)
def clean_research_rows():
    from backend.core.research import service

    external_ids = [item["external_id"] for item in SYNTHETIC_ITEMS]
    session = service.SessionLocal()
    try:
        session.execute(delete(ResearchItem).where(ResearchItem.external_id.in_(external_ids)))
        session.commit()
        yield
    finally:
        session.execute(delete(ResearchItem).where(ResearchItem.external_id.in_(external_ids)))
        session.commit()
        session.close()


@pytest.mark.asyncio
async def test_ingest_arxiv_dedupes_and_lists_items(monkeypatch):
    from backend.core.research import arxiv_source, service

    async def fake_fetch_arxiv(query: str = "cat:q-fin.*", *, max_results: int = 25, timeout: float = 20.0):
        return SYNTHETIC_ITEMS

    monkeypatch.setattr(arxiv_source, "fetch_arxiv", fake_fetch_arxiv)

    first = await service.ingest_arxiv("cat:q-fin.*", max_results=3)
    second = await service.ingest_arxiv("cat:q-fin.*", max_results=3)
    listed = service.list_items(limit=10)
    listed_ids = {item["external_id"] for item in listed}

    assert first == {"ingested": 3, "fetched": 3, "query": "cat:q-fin.*"}
    assert second == {"ingested": 0, "fetched": 3, "query": "cat:q-fin.*"}
    assert {item["external_id"] for item in SYNTHETIC_ITEMS}.issubset(listed_ids)
    assert all(isinstance(item["authors"], list) for item in listed if item["external_id"] in listed_ids)


def test_search_items_ranks_matching_item_first():
    results = search_items(SYNTHETIC_ITEMS, "volatility option surface", k=3)

    assert results
    assert results[0]["external_id"] == "abs/test-research-001v1"
    assert results[0]["score"] > 0


def test_search_items_empty_inputs_are_safe():
    assert search_items([], "volatility", k=3) == []
    assert search_items(SYNTHETIC_ITEMS, "", k=3) == []
