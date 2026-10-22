"""User profile for onboarding and journey tracking."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, default="default")
    display_name: Mapped[str] = mapped_column(String(128), default="")
    primary_trade: Mapped[str] = mapped_column(String(256), default="")
    employment_type: Mapped[str] = mapped_column(String(32), default="self_employed")
    cashflow_quadrant_primary: Mapped[str] = mapped_column(String(1), default="S")
    cashflow_quadrant_json: Mapped[str] = mapped_column(Text, default="{}")
    monthly_gross_income: Mapped[float] = mapped_column(Float, default=0)
    monthly_essentials: Mapped[float] = mapped_column(Float, default=0)
    stability_fund_balance: Mapped[float] = mapped_column(Float, default=0)
    stability_fund_target_months: Mapped[int] = mapped_column(Integer, default=4)
    baseline_revenue_per_hour: Mapped[float] = mapped_column(Float, default=0)
    revenue_per_hour: Mapped[float] = mapped_column(Float, default=0)
    focus_season_active: Mapped[bool] = mapped_column(Boolean, default=False)
    solitude_mode_active: Mapped[bool] = mapped_column(Boolean, default=False)
    creation_hour: Mapped[str] = mapped_column(String(8), default="07:00")
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    intake_step: Mapped[int] = mapped_column(Integer, default=0)
    intake_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_source: Mapped[str] = mapped_column(String(16), default="none")
    debts_json: Mapped[str] = mapped_column(Text, default="[]")
    credit_snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    business_budget_json: Mapped[str] = mapped_column(Text, default="{}")
    income_streams_json: Mapped[str] = mapped_column(Text, default="[]")
    expenses_json: Mapped[str] = mapped_column(Text, default="{}")
    bills_json: Mapped[str] = mapped_column(Text, default="[]")
    wealth_state_json: Mapped[str] = mapped_column(Text, default="{}")
    north_star_json: Mapped[str] = mapped_column(Text, default="{}")
    opportunities_json: Mapped[str] = mapped_column(Text, default="[]")
    inflows_json: Mapped[str] = mapped_column(Text, default="[]")
    contract_signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    audit_json: Mapped[str] = mapped_column(Text, default="{}")
    footprints_json: Mapped[str] = mapped_column(Text, default="{}")
    literacy_completed_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
