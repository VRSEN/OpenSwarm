"""Seed default reputation tier unlocks and create tables."""

from backend.database import SessionLocal, init_db
from backend.models.reputation import ReputationUnlock
from backend.services.reputation_engine import get_tier_unlocks


def seed_unlocks():
    db = SessionLocal()
    try:
        for tier in ("Bronze", "Silver", "Gold", "Platinum"):
            existing = db.query(ReputationUnlock).filter(ReputationUnlock.tier == tier).first()
            if existing:
                continue
            u = get_tier_unlocks(tier)
            db.add(
                ReputationUnlock(
                    tier=tier,
                    arbitrage_funding=u["arbitrage_funding"],
                    max_fund_amount=u["max_fund_amount"],
                    coc_adjustment_bps=u["coc_adjustment_bps"],
                    pipeline_priority=u["pipeline_priority"],
                )
            )
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    seed_unlocks()
    print("Database initialized and tier unlocks seeded.")
