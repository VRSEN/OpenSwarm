"""Persist durable facts about the architect for future sessions."""

import os
from pathlib import Path

from agency_swarm.tools import BaseTool
from pydantic import Field
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base, init_db
from backend.services.memory_service import add_memory_fact

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
_DEFAULT_URL = f"sqlite:///{_DATA_DIR / 'architect_blueprint.db'}"
_DATABASE_URL = os.getenv("DATABASE_URL", _DEFAULT_URL)
_engine = create_engine(
    _DATABASE_URL,
    connect_args={"check_same_thread": False} if _DATABASE_URL.startswith("sqlite") else {},
)
_Session = sessionmaker(bind=_engine)
_tables_ready = False


def _ensure_tables() -> None:
    global _tables_ready
    if _tables_ready:
        return
    from backend.models import agent_memory  # noqa: F401

    Base.metadata.create_all(bind=_engine)
    _tables_ready = True


class RecordArchitectMemory(BaseTool):
    """
    Save a durable fact about this architect for future conversations.
    Use when the user shares goals, constraints, preferences, or context
    worth remembering across sessions.
    """

    content: str = Field(..., description="The fact to remember — one clear sentence.")
    category: str = Field(
        default="general",
        description="Category: goal, constraint, preference, tax, credit, business, family, or general.",
    )

    def run(self) -> str:
        user_id = "default"
        source_agent = "Agent"
        try:
            uid = self._context.get("user_id")
            if uid:
                user_id = str(uid)
            identity = self._context.get("architect_identity") or {}
            if identity.get("user_id"):
                user_id = str(identity["user_id"])
            if self._context.get("current_agent_name"):
                source_agent = str(self._context.get("current_agent_name"))
        except Exception:
            pass

        db = _Session()
        try:
            _ensure_tables()
            fact = add_memory_fact(
                db,
                user_id,
                self.content,
                category=self.category[:64],
                source_agent=source_agent[:128],
            )
            return f"Remembered: [{fact.category}] {fact.content} (id {fact.id})"
        finally:
            db.close()


if __name__ == "__main__":
    init_db()
    tool = RecordArchitectMemory(content="User targets 30% tax set-aside.", category="tax")
    print(tool.run())
