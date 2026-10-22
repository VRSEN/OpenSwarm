"""Integrity Engine persistence models."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserSelfCommitment(Base):
    __tablename__ = "user_self_commitments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, default="default")
    benchmark_type: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(String(512))
    target_value: Mapped[str] = mapped_column(String(128), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    streak_days: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class SelfTrustEvent(Base):
    __tablename__ = "self_trust_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, default="default")
    event_type: Mapped[str] = mapped_column(String(32))
    kept_commitment: Mapped[bool] = mapped_column(Boolean, default=False)
    commitment_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class StrategyPersistence(Base):
    __tablename__ = "strategy_persistence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, default="default")
    strategy_name: Mapped[str] = mapped_column(String(256))
    strategy_start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    restart_count: Mapped[int] = mapped_column(Integer, default=0)
    invisible_season_days: Mapped[int] = mapped_column(Integer, default=0)
    steady_months: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class ReputationScore(Base):
    __tablename__ = "reputation_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, default="default")
    composite_score: Mapped[float] = mapped_column(Float)
    tier: Mapped[str] = mapped_column(String(16))
    pillar_behavioral_trust: Mapped[float] = mapped_column(Float, default=0)
    pillar_self_trust: Mapped[float] = mapped_column(Float, default=0)
    pillar_pressure: Mapped[float] = mapped_column(Float, default=0)
    pillar_authenticity: Mapped[float] = mapped_column(Float, default=0)
    pillar_consistency: Mapped[float] = mapped_column(Float, default=0)
    rarity_score: Mapped[float] = mapped_column(Float, default=0)
    snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ReputationUnlock(Base):
    __tablename__ = "reputation_unlocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tier: Mapped[str] = mapped_column(String(16), unique=True)
    arbitrage_funding: Mapped[bool] = mapped_column(Boolean, default=False)
    max_fund_amount: Mapped[float] = mapped_column(Float, default=0)
    coc_adjustment_bps: Mapped[int] = mapped_column(Integer, default=0)
    pipeline_priority: Mapped[bool] = mapped_column(Boolean, default=False)


class RecalibrationAlert(Base):
    __tablename__ = "recalibration_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, default="default")
    severity: Mapped[str] = mapped_column(String(16), default="amber")
    message: Mapped[str] = mapped_column(Text)
    reasons_json: Mapped[str] = mapped_column(Text, default="[]")
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False)
    corrective_action: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
