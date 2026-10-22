"""Architect memory API — dossier, chat history, learned facts, progress snapshots."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
import backend.repositories.memory_repo as memory_repo
from backend.schemas.memory import MemoryFactCreate, SnapshotCreate
from backend.services.memory_service import (
    add_memory_fact,
    build_architect_dossier,
    get_chat_history,
    record_improvement_snapshot,
    save_chat_history,
)

router = APIRouter(prefix="/user/memory", tags=["memory"])


def _user_id(user_id: str = Query(default="default")) -> str:
    return user_id or "default"


@router.get("/dossier")
def get_dossier(user_id: str = Depends(_user_id), db: Session = Depends(get_db)):
    """Full architect context for agents — identity, numbers, stage, facts, progress."""
    return build_architect_dossier(db, user_id)


@router.get("/chat")
def get_chat(
    user_id: str = Depends(_user_id),
    thread_id: str = Query(default="main"),
    db: Session = Depends(get_db),
):
    messages = get_chat_history(db, user_id, thread_id)
    return {"user_id": user_id, "thread_id": thread_id, "messages": messages, "count": len(messages)}


@router.put("/chat")
def put_chat(
    body: dict,
    user_id: str = Depends(_user_id),
    thread_id: str = Query(default="main"),
    db: Session = Depends(get_db),
):
    messages = body.get("messages")
    if not isinstance(messages, list):
        raise HTTPException(status_code=400, detail="messages must be a list")
    saved = save_chat_history(db, user_id, messages, thread_id)
    return {"user_id": user_id, "thread_id": thread_id, "messages": saved, "count": len(saved)}


@router.delete("/chat")
def clear_chat(
    user_id: str = Depends(_user_id),
    thread_id: str = Query(default="main"),
    db: Session = Depends(get_db),
):
    memory_repo.clear_thread(db, user_id, thread_id)
    return {"cleared": True, "user_id": user_id, "thread_id": thread_id}


@router.get("/facts")
def list_facts(user_id: str = Depends(_user_id), db: Session = Depends(get_db)):
    facts = memory_repo.list_facts(db, user_id, limit=50)
    return {
        "facts": [
            {
                "id": f.id,
                "category": f.category,
                "content": f.content,
                "source_agent": f.source_agent,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in facts
        ]
    }


@router.post("/facts")
def create_fact(
    payload: MemoryFactCreate,
    user_id: str = Depends(_user_id),
    db: Session = Depends(get_db),
):
    fact = add_memory_fact(
        db,
        user_id,
        payload.content,
        category=payload.category,
        source_agent=payload.source_agent,
    )
    return {
        "id": fact.id,
        "category": fact.category,
        "content": fact.content,
        "source_agent": fact.source_agent,
    }


@router.delete("/facts/{fact_id}")
def delete_fact(fact_id: int, user_id: str = Depends(_user_id), db: Session = Depends(get_db)):
    if not memory_repo.delete_fact(db, user_id, fact_id):
        raise HTTPException(status_code=404, detail="Fact not found")
    return {"deleted": True, "id": fact_id}


@router.get("/snapshots")
def list_snapshots(user_id: str = Depends(_user_id), db: Session = Depends(get_db)):
    import json

    rows = memory_repo.list_snapshots(db, user_id, limit=20)
    return {
        "snapshots": [
            {
                "id": s.id,
                "stage": s.stage,
                "metrics": json.loads(s.metrics_json or "{}"),
                "note": s.note,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in rows
        ]
    }


@router.post("/snapshots")
def create_snapshot(
    payload: SnapshotCreate,
    user_id: str = Depends(_user_id),
    db: Session = Depends(get_db),
):
    snap = record_improvement_snapshot(db, user_id, note=payload.note)
    if not snap:
        raise HTTPException(status_code=404, detail="User profile not found")
    import json

    return {
        "id": snap.id,
        "stage": snap.stage,
        "metrics": json.loads(snap.metrics_json or "{}"),
        "note": snap.note,
    }
