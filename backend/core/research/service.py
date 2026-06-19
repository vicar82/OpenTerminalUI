from __future__ import annotations

from sqlalchemy import select

from backend.core.research import arxiv_source
from backend.core.research.index import search_items
from backend.core.research.models import ResearchItem, ResearchItemOut
from backend.shared.db import Base, SessionLocal, engine

Base.metadata.create_all(bind=engine, tables=[ResearchItem.__table__])


def _join_values(values: object) -> str:
    if isinstance(values, list):
        return ", ".join(str(value).strip() for value in values if str(value).strip())
    return str(values or "")


def _item_to_dict(item: ResearchItem) -> dict:
    return ResearchItemOut.from_orm_item(item).model_dump()


async def ingest_arxiv(query: str = "cat:q-fin.*", *, max_results: int = 25) -> dict:
    fetched_items = await arxiv_source.fetch_arxiv(query, max_results=max_results)
    session = SessionLocal()
    ingested = 0
    try:
        for raw in fetched_items:
            try:
                external_id = str(raw.get("external_id") or "").strip()
                title = str(raw.get("title") or "").strip()
                if not external_id or not title:
                    continue
                exists = session.execute(
                    select(ResearchItem.id).where(ResearchItem.external_id == external_id)
                ).scalar_one_or_none()
                if exists:
                    continue
                session.add(
                    ResearchItem(
                        source=str(raw.get("source") or "arxiv"),
                        external_id=external_id,
                        title=title,
                        authors=_join_values(raw.get("authors")),
                        abstract=str(raw.get("abstract") or ""),
                        url=str(raw.get("url") or ""),
                        categories=_join_values(raw.get("categories")),
                        published_at=str(raw.get("published_at") or ""),
                    )
                )
                ingested += 1
            except Exception:
                continue
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()
    return {"ingested": ingested, "fetched": len(fetched_items), "query": query}


def search(query: str, *, k: int = 10) -> list[dict]:
    session = SessionLocal()
    try:
        items = session.execute(
            select(ResearchItem).order_by(ResearchItem.created_at.desc()).limit(5000)
        ).scalars().all()
        return search_items([_item_to_dict(item) for item in items], query, k)
    finally:
        session.close()


def list_items(*, limit: int = 50) -> list[dict]:
    session = SessionLocal()
    try:
        items = session.execute(
            select(ResearchItem).order_by(ResearchItem.created_at.desc()).limit(limit)
        ).scalars().all()
        return [_item_to_dict(item) for item in items]
    finally:
        session.close()
