"""Pydantic schemas for Integrity Engine API."""

from pydantic import BaseModel, Field


class SelfCommitmentCreate(BaseModel):
    benchmark_type: str = Field(..., description="rhythm|financial_machine|focus_season|operator_standard")
    description: str
    target_value: str = ""


class SelfCommitmentResponse(BaseModel):
    id: int
    benchmark_type: str
    description: str
    target_value: str
    active: bool
    streak_days: int


class SelfTrustCheckIn(BaseModel):
    commitment_id: int | None = None
    event_type: str = "check_in"
    kept_commitment: bool
    notes: str = ""


class ProviderEngagement(BaseModel):
    date: str = ""
    promised: str = ""
    delivered: bool = False
    on_time: bool = False


class VetProviderRequest(BaseModel):
    provider_name: str
    engagements: list[ProviderEngagement]
    references_verified: int = 0
    project_value: float = 0


class CharacterMirrorQuery(BaseModel):
    essentials_pct: float = 65.0
    life_bucket_pct: float = 20.0
    stability_fund_pct: float = 0.0
    money_velocity_tier: str = "B"
    consumer_tag_count: int = 0
    acquirer_tag_count: int = 0
    pause_breaches_recent: int = 0


class FundEligibilityRequest(BaseModel):
    requested_amount: float = Field(..., gt=0)
    composite_score: float | None = None
    self_trust_pillar: float | None = None
    tier: str | None = None
