from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.db import Base


class ResearchItem(Base):
    __tablename__ = "research_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source: Mapped[str] = mapped_column(String(32), index=True)
    external_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    title: Mapped[str] = mapped_column(Text)
    authors: Mapped[str] = mapped_column(Text, default="")
    abstract: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(String(512), default="")
    categories: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


class ResearchItemOut(BaseModel):
    id: str
    source: str
    external_id: str
    title: str
    authors: list[str]
    abstract: str
    url: str
    categories: list[str]
    published_at: str
    created_at: datetime

    @classmethod
    def from_orm_item(cls, item: ResearchItem) -> "ResearchItemOut":
        return cls(
            id=item.id,
            source=item.source,
            external_id=item.external_id,
            title=item.title,
            authors=_split_csv(item.authors),
            abstract=item.abstract,
            url=item.url,
            categories=_split_csv(item.categories),
            published_at=item.published_at,
            created_at=item.created_at,
        )
