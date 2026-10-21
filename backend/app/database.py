"""SQLAlchemy persistence for aggregate analysis metadata only."""

from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
from typing import Any

from sqlalchemy import Integer, String, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.engine import Engine


class Base(DeclarativeBase):
    pass


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[str] = mapped_column(
        String, nullable=False, server_default=func.current_timestamp()
    )
    total_posts: Mapped[int] = mapped_column(Integer, nullable=False)
    positive_count: Mapped[int] = mapped_column(Integer, nullable=False)
    neutral_count: Mapped[int] = mapped_column(Integer, nullable=False)
    negative_count: Mapped[int] = mapped_column(Integer, nullable=False)
    analysis_mode: Mapped[str] = mapped_column(String, nullable=False)


def database_path() -> Path:
    return Path(os.getenv("SOCIALPULSE_DATABASE_PATH", "data/socialpulse.db"))


@lru_cache(maxsize=4)
def _engine_for_path(path: str) -> Engine:
    database_file = Path(path)
    database_file.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        f"sqlite:///{database_file.resolve().as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )


def engine() -> Engine:
    return _engine_for_path(str(database_path()))


def initialize() -> None:
    Base.metadata.create_all(engine())


def save_analysis(summary: dict[str, Any], mode: str) -> int:
    counts = summary.get("sentiment_counts", {})
    with Session(engine()) as session:
        analysis = Analysis(
            total_posts=int(summary["total_posts"]),
            positive_count=int(counts.get("positive", 0)),
            neutral_count=int(counts.get("neutral", 0)),
            negative_count=int(counts.get("negative", 0)),
            analysis_mode=mode,
        )
        session.add(analysis)
        session.commit()
        session.refresh(analysis)
        return analysis.id


def _as_record(analysis: Analysis) -> dict[str, Any]:
    return {
        "id": analysis.id,
        "created_at": analysis.created_at,
        "total_posts": analysis.total_posts,
        "positive_count": analysis.positive_count,
        "neutral_count": analysis.neutral_count,
        "negative_count": analysis.negative_count,
        "analysis_mode": analysis.analysis_mode,
    }


def history(limit: int = 50) -> list[dict[str, Any]]:
    with Session(engine()) as session:
        rows = session.scalars(
            select(Analysis).order_by(Analysis.id.desc()).limit(limit)
        ).all()
    return [_as_record(row) for row in rows]


def summary() -> dict[str, Any]:
    with Session(engine()) as session:
        total = session.scalar(select(func.count()).select_from(Analysis)) or 0
        latest = session.scalar(select(Analysis).order_by(Analysis.id.desc()).limit(1))
    return {"analysis_count": int(total), "latest_analysis": _as_record(latest) if latest else None}
