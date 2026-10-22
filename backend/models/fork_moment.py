"""Active Fork Moment pause records."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ForkMomentPause(Base):
    __tablename__ = "fork_moment_pauses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, default="default")
    item_description: Mapped[str] = mapped_column(String(512))
    amount: Mapped[float] = mapped_column(Float)
    bucket: Mapped[str] = mapped_column(String(32), default="life")
    emotion: Mapped[str] = mapped_column(String(32), default="")
    emotion_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    unlock_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    released: Mapped[bool] = mapped_column(Boolean, default=False)
    identity_notification: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
