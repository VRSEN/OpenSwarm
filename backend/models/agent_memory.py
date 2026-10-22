"""Persistent memory for advisor conversations, learned facts, and progress snapshots."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AdvisorChatThread(Base):
    """One advisor conversation thread per user (default thread id = 'main')."""

    __tablename__ = "advisor_chat_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, default="default")
    thread_id: Mapped[str] = mapped_column(String(64), default="main", index=True)
    title: Mapped[str] = mapped_column(String(256), default="Advisor")
    messages_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class UserMemoryFact(Base):
    """Long-term facts agents learn about the architect (goals, preferences, context)."""

    __tablename__ = "user_memory_facts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, default="default")
    category: Mapped[str] = mapped_column(String(64), default="general")
    content: Mapped[str] = mapped_column(Text, default="")
    source_agent: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ImprovementSnapshot(Base):
    """Point-in-time record of who the system is improving and how."""

    __tablename__ = "improvement_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, default="default")
    stage: Mapped[str] = mapped_column(String(64), default="Stability")
    metrics_json: Mapped[str] = mapped_column(Text, default="{}")
    note: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
