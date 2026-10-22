"""Architect memory — dossier, chat persistence, learned facts, improvement tracking."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.models.agent_memory import AdvisorChatThread, ImprovementSnapshot, UserMemoryFact
from backend.models.reputation import ReputationScore
from backend.models.user_profile import UserProfile
import backend.repositories.memory_repo as memory_repo
from backend.repositories.reputation_repo import load_self_trust_events
from backend.services.reputation_engine import compute_self_trust_index
from backend.services.financial_intake import build_financial_summary
from backend.services.journey_engine import assess_stage

MAX_CHAT_MESSAGES = 80
MAX_FACTS_IN_DOSSIER = 25
MAX_SNAPSHOTS_IN_DOSSIER = 8


def _employment_label(employment_type: str | None) -> str:
    labels = {
        "self_employed": "Self-employed / freelancer",
        "business_owner": "Business owner",
        "side_hustle": "Side hustle + W-2",
    }
    return labels.get(employment_type or "", "Self-employed operator")


def _latest_reputation_summary(db: Session, user_id: str) -> dict[str, Any] | None:
    row = (
        db.query(ReputationScore)
        .filter(ReputationScore.user_id == user_id)
        .order_by(ReputationScore.recorded_at.desc())
        .first()
    )
    events = load_self_trust_events(db, user_id)
    self_trust = compute_self_trust_index(events)
    if not row and not events:
        return None
    base = {"self_trust_index": self_trust.get("self_trust_index")}
    if row:
        try:
            snap = json.loads(row.snapshot_json or "{}")
        except json.JSONDecodeError:
            snap = {}
        base.update(
            {
                "tier": row.tier,
                "reputation_credit_score": row.composite_score,
                "pillars": snap.get("pillars") or {
                    "behavioral_trust": row.pillar_behavioral_trust,
                    "self_trust": row.pillar_self_trust,
                },
            }
        )
    return base


def build_architect_dossier(db: Session, user_id: str) -> dict[str, Any]:
    """Full context bundle so agents know who they are improving."""
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not profile:
        return {
            "user_id": user_id,
            "architect_identity": {"display_name": "Architect", "intake_completed": False},
            "remembered_facts": [],
            "improvement_history": [],
        }

    financial_summary = build_financial_summary(profile)
    journey = assess_stage(
        monthly_essentials=profile.monthly_essentials or 0,
        stability_fund_balance=profile.stability_fund_balance or 0,
        stability_fund_target_months=profile.stability_fund_target_months or 4,
        revenue_per_hour=profile.revenue_per_hour or 0,
        baseline_revenue_per_hour=profile.baseline_revenue_per_hour or 0,
    )

    reputation = _latest_reputation_summary(db, user_id)

    facts = memory_repo.list_facts(db, user_id, limit=MAX_FACTS_IN_DOSSIER)
    snapshots = memory_repo.list_snapshots(db, user_id, limit=MAX_SNAPSHOTS_IN_DOSSIER)

    gap = (profile.monthly_gross_income or 0) - (profile.monthly_essentials or 0)

    return {
        "user_id": user_id,
        "architect_identity": {
            "display_name": profile.display_name or "Architect",
            "primary_trade": profile.primary_trade,
            "employment_type": profile.employment_type,
            "employment_label": _employment_label(profile.employment_type),
            "intake_completed": profile.intake_completed_at is not None,
            "data_source": profile.data_source,
        },
        "financial_summary": financial_summary,
        "journey": journey,
        "gap_multiplier": {
            "monthly_income": profile.monthly_gross_income or 0,
            "monthly_essentials": profile.monthly_essentials or 0,
            "gap": round(gap, 2),
        },
        "reputation_summary": reputation,
        "cashflow_quadrant": financial_summary.get("cashflow_quadrant"),
        "remembered_facts": [
            {
                "category": f.category,
                "content": f.content,
                "source_agent": f.source_agent,
                "recorded_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in facts
        ],
        "improvement_history": [
            {
                "stage": s.stage,
                "metrics": json.loads(s.metrics_json or "{}"),
                "note": s.note,
                "recorded_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in snapshots
        ],
        "memory_instructions": (
            "You are improving THIS architect's wealth machine. Use their name, numbers, stage, "
            "remembered facts, and improvement history. Record new durable facts with RecordArchitectMemory "
            "when the user shares goals, constraints, or preferences worth remembering."
        ),
    }


def get_chat_history(db: Session, user_id: str, thread_id: str = "main") -> list[dict[str, Any]]:
    thread = memory_repo.get_thread(db, user_id, thread_id)
    if not thread:
        return []
    try:
        data = json.loads(thread.messages_json or "[]")
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def save_chat_history(
    db: Session,
    user_id: str,
    messages: list[dict[str, Any]],
    thread_id: str = "main",
) -> list[dict[str, Any]]:
    trimmed = messages[-MAX_CHAT_MESSAGES:] if len(messages) > MAX_CHAT_MESSAGES else messages
    memory_repo.upsert_thread(db, user_id, thread_id, trimmed)
    return trimmed


def merge_chat_history(
    existing: list[dict[str, Any]] | None,
    new_messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Append agency new_messages to stored history."""
    base = list(existing or [])
    for msg in new_messages:
        if isinstance(msg, dict):
            base.append(msg)
    return base[-MAX_CHAT_MESSAGES:]


def add_memory_fact(
    db: Session,
    user_id: str,
    content: str,
    *,
    category: str = "general",
    source_agent: str = "",
) -> UserMemoryFact:
    content = content.strip()
    if not content:
        raise ValueError("Memory content cannot be empty")
    return memory_repo.add_fact(db, user_id, content, category=category, source_agent=source_agent)


def record_improvement_snapshot(
    db: Session,
    user_id: str,
    *,
    note: str = "",
) -> ImprovementSnapshot | None:
    """Capture current stage and key metrics for progress tracking."""
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not profile:
        return None

    journey = assess_stage(
        monthly_essentials=profile.monthly_essentials or 0,
        stability_fund_balance=profile.stability_fund_balance or 0,
        stability_fund_target_months=profile.stability_fund_target_months or 4,
        revenue_per_hour=profile.revenue_per_hour or 0,
        baseline_revenue_per_hour=profile.baseline_revenue_per_hour or 0,
    )
    financial = build_financial_summary(profile)

    metrics = {
        "stability_fund_pct": journey.get("stability_fund_pct"),
        "income_density_improvement_pct": journey.get("income_density_improvement_pct"),
        "monthly_gross_income": profile.monthly_gross_income,
        "debt_total": financial.get("debt_total"),
        "stage_index": journey.get("stage_index"),
    }

    # Avoid duplicate snapshots within the same hour unless note differs
    recent = memory_repo.list_snapshots(db, user_id, limit=1)
    if recent:
        last = recent[0]
        if last.stage == journey["stage"] and last.created_at:
            age = datetime.now(timezone.utc) - last.created_at.replace(tzinfo=timezone.utc)
            if age.total_seconds() < 3600 and not note:
                return last

    return memory_repo.add_snapshot(
        db,
        user_id,
        stage=journey["stage"],
        metrics=metrics,
        note=note or journey.get("next_mechanical_action", ""),
    )


def format_dossier_for_instructions(dossier: dict[str, Any]) -> str:
    """Compact text block for additional_instructions."""
    identity = dossier.get("architect_identity") or {}
    name = identity.get("display_name") or "Architect"
    journey = dossier.get("journey") or {}
    stage = journey.get("stage", "unknown")
    facts = dossier.get("remembered_facts") or []
    fact_lines = "\n".join(f"- [{f.get('category', 'general')}] {f.get('content')}" for f in facts[:12])
    history = dossier.get("improvement_history") or []
    hist_lines = ""
    if history:
        latest = history[0]
        hist_lines = f"Latest progress snapshot: stage {latest.get('stage')} at {latest.get('recorded_at', 'unknown')}."

    cq = dossier.get("cashflow_quadrant") or (dossier.get("financial_summary") or {}).get("cashflow_quadrant")
    esbi_block = ""
    if cq:
        mix = cq.get("income_mix_pct") or {}
        mix_line = ", ".join(f"{k}={mix.get(k, 0)}%" for k in ("E", "S", "B", "I"))
        esbi_block = (
            f"\n## Cashflow Quadrant (ESBI) — use in every wealth/strategy answer\n"
            f"- Primary: {cq.get('primary_quadrant')} ({cq.get('primary_label')}) — {cq.get('primary_description', '')}\n"
            f"- Target for stage {stage}: {cq.get('target_quadrant')} ({cq.get('target_label')}) — badge {cq.get('badge', '')}\n"
            f"- Income mix: {mix_line} | Left side {cq.get('left_side_pct')}% vs Right side {cq.get('right_side_pct')}%\n"
            f"- Next ESBI move: {cq.get('next_mechanical_move', '')}\n"
            f"- NOT Covey Quadrant II (time management). ESBI = how income is earned.\n"
            f"- Reference Learn lesson 14 or playbook tag `esbi` when coaching quadrant shifts.\n"
        )

    return (
        f"## Architect Memory — {name}\n"
        f"Stage: {stage}. User id: {dossier.get('user_id', 'default')}.\n"
        f"{hist_lines}\n"
        f"{esbi_block}"
        f"Remembered facts:\n{fact_lines or '- (none yet)'}\n"
        f"Use financial_summary and journey from user_context for all numbers."
    )
