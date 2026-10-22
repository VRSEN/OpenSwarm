"""SQLAlchemy database configuration."""

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_DATABASE_URL = f"sqlite:///{DATA_DIR / 'architect_blueprint.db'}"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from backend.models import agent_memory, fork_moment, reputation, user_profile  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_sqlite_columns()


def _migrate_sqlite_columns():
    """Add new columns to existing SQLite DBs without Alembic."""
    if not DATABASE_URL.startswith("sqlite"):
        return
    import sqlalchemy as sa

    new_cols = {
        "user_profiles": [
            ("solitude_mode_active", "BOOLEAN DEFAULT 0"),
            ("creation_hour", "VARCHAR(8) DEFAULT '07:00'"),
            ("contract_signed_at", "DATETIME"),
            ("audit_json", "TEXT DEFAULT '{}'"),
            ("footprints_json", "TEXT DEFAULT '{}'"),
            ("employment_type", "VARCHAR(32) DEFAULT 'self_employed'"),
            ("intake_step", "INTEGER DEFAULT 0"),
            ("intake_completed_at", "DATETIME"),
            ("data_source", "VARCHAR(16) DEFAULT 'none'"),
            ("debts_json", "TEXT DEFAULT '[]'"),
            ("credit_snapshot_json", "TEXT DEFAULT '{}'"),
            ("business_budget_json", "TEXT DEFAULT '{}'"),
            ("cashflow_quadrant_primary", "VARCHAR(1) DEFAULT 'S'"),
            ("cashflow_quadrant_json", "TEXT DEFAULT '{}'"),
            ("income_streams_json", "TEXT DEFAULT '[]'"),
            ("expenses_json", "TEXT DEFAULT '{}'"),
            ("bills_json", "TEXT DEFAULT '[]'"),
            ("wealth_state_json", "TEXT DEFAULT '{}'"),
            ("north_star_json", "TEXT DEFAULT '{}'"),
            ("opportunities_json", "TEXT DEFAULT '[]'"),
            ("inflows_json", "TEXT DEFAULT '[]'"),
        ],
    }
    with engine.connect() as conn:
        for table, columns in new_cols.items():
            existing = {row[1] for row in conn.execute(sa.text(f"PRAGMA table_info({table})"))}
            for name, typedef in columns:
                if name not in existing:
                    conn.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN {name} {typedef}"))
        conn.commit()
