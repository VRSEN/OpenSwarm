"""Database access for advisor memory."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from backend.models.agent_memory import AdvisorChatThread, ImprovementSnapshot, UserMemoryFact


def get_thread(db: Session, user_id: str, thread_id: str = "main") -> AdvisorChatThread | None:
    return (
        db.query(AdvisorChatThread)
        .filter(AdvisorChatThread.user_id == user_id, AdvisorChatThread.thread_id == thread_id)
        .first()
    )


def upsert_thread(
    db: Session,
    user_id: str,
    thread_id: str,
    messages: list[dict[str, Any]],
) -> AdvisorChatThread:
    row = get_thread(db, user_id, thread_id)
    payload = json.dumps(messages)
    if row:
        row.messages_json = payload
        db.commit()
        db.refresh(row)
        return row
    row = AdvisorChatThread(user_id=user_id, thread_id=thread_id, messages_json=payload)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_facts(db: Session, user_id: str, limit: int = 25) -> list[UserMemoryFact]:
    return (
        db.query(UserMemoryFact)
        .filter(UserMemoryFact.user_id == user_id)
        .order_by(UserMemoryFact.created_at.desc())
        .limit(limit)
        .all()
    )


def add_fact(
    db: Session,
    user_id: str,
    content: str,
    *,
    category: str = "general",
    source_agent: str = "",
) -> UserMemoryFact:
    row = UserMemoryFact(
        user_id=user_id,
        category=category,
        content=content,
        source_agent=source_agent,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def delete_fact(db: Session, user_id: str, fact_id: int) -> bool:
    row = (
        db.query(UserMemoryFact)
        .filter(UserMemoryFact.id == fact_id, UserMemoryFact.user_id == user_id)
        .first()
    )
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


def list_snapshots(db: Session, user_id: str, limit: int = 8) -> list[ImprovementSnapshot]:
    return (
        db.query(ImprovementSnapshot)
        .filter(ImprovementSnapshot.user_id == user_id)
        .order_by(ImprovementSnapshot.created_at.desc())
        .limit(limit)
        .all()
    )


def add_snapshot(
    db: Session,
    user_id: str,
    *,
    stage: str,
    metrics: dict[str, Any],
    note: str = "",
) -> ImprovementSnapshot:
    row = ImprovementSnapshot(
        user_id=user_id,
        stage=stage,
        metrics_json=json.dumps(metrics),
        note=note[:512],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def clear_thread(db: Session, user_id: str, thread_id: str = "main") -> None:
    row = get_thread(db, user_id, thread_id)
    if row:
        row.messages_json = "[]"
        db.commit()
