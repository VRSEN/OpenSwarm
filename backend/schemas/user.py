import json

from pydantic import BaseModel, Field


class OnboardingComplete(BaseModel):
    display_name: str = Field(..., min_length=1)
    primary_trade: str = Field(default="")
    monthly_gross_income: float = Field(..., gt=0)
    monthly_essentials: float = Field(..., gt=0)
    stability_fund_balance: float = Field(default=0, ge=0)
    stability_fund_target_months: int = Field(default=4, ge=3, le=6)
    baseline_revenue_per_hour: float = Field(default=0, ge=0)
    revenue_per_hour: float = Field(default=0, ge=0)
    focus_season_active: bool = Field(default=False)


class ProfileUpdate(BaseModel):
    monthly_gross_income: float | None = None
    monthly_essentials: float | None = None
    stability_fund_balance: float | None = None
    revenue_per_hour: float | None = None


class LiteracyProgress(BaseModel):
    module_id: str
    completed: bool = True


class IncomeStreamItem(BaseModel):
    name: str = Field(..., min_length=1)
    source_type: str = Field(default="business")
    amount_monthly: float = Field(..., ge=0)
    frequency: str = Field(default="monthly")
    notes: str = Field(default="")


class BillItem(BaseModel):
    name: str = Field(..., min_length=1)
    amount_monthly: float = Field(..., ge=0)
    due_day: int = Field(default=0, ge=0, le=31)
    category: str = Field(default="other")
    autopay: bool = Field(default=False)


class CollectionItem(BaseModel):
    creditor: str = Field(..., min_length=1)
    balance: float = Field(..., ge=0)
    status: str = Field(default="open")
    notes: str = Field(default="")


class DebtItem(BaseModel):
    name: str = Field(..., min_length=1)
    balance: float = Field(..., ge=0)
    apr: float = Field(..., ge=0)
    minimum_payment: float = Field(default=0, ge=0)
    secured: bool = Field(default=False)
    debt_type: str = Field(default="other")
    past_due_amount: float = Field(default=0, ge=0)
    in_collections: bool = Field(default=False)


class IntakeStep1(BaseModel):
    display_name: str = Field(..., min_length=1)
    primary_trade: str = Field(default="")
    employment_type: str = Field(default="self_employed")
    cashflow_quadrant_primary: str = Field(default="S", pattern="^[ESBI]$")
    income_mix_e_pct: float = Field(default=0, ge=0, le=100)
    income_mix_s_pct: float = Field(default=100, ge=0, le=100)
    income_mix_b_pct: float = Field(default=0, ge=0, le=100)
    income_mix_i_pct: float = Field(default=0, ge=0, le=100)


class IntakeStep2(BaseModel):
    """Income streams — legacy monthly_gross_income still accepted."""
    income_streams: list[IncomeStreamItem] = Field(default_factory=list)
    monthly_gross_income: float | None = Field(default=None, ge=0)


class IntakeStep3(BaseModel):
    """Monthly expense categories ($/month)."""
    housing: float = Field(default=0, ge=0)
    utilities: float = Field(default=0, ge=0)
    food_groceries: float = Field(default=0, ge=0)
    transportation: float = Field(default=0, ge=0)
    insurance: float = Field(default=0, ge=0)
    healthcare: float = Field(default=0, ge=0)
    childcare: float = Field(default=0, ge=0)
    personal: float = Field(default=0, ge=0)
    business_opex: float = Field(default=0, ge=0)
    debt_minimums: float = Field(default=0, ge=0)
    other: float = Field(default=0, ge=0)
    monthly_essentials: float | None = Field(default=None, ge=0)


class IntakeStep4(BaseModel):
    """Recurring bills + Stability Fund."""
    bills: list[BillItem] = Field(default_factory=list)
    stability_fund_balance: float = Field(default=0, ge=0)
    stability_fund_target_months: int = Field(default=4, ge=3, le=6)


class IntakeStep5(BaseModel):
    debts: list[DebtItem] = Field(default_factory=list)


class IntakeStep6(BaseModel):
    score_band: str = Field(default="unknown")
    estimated_score: int | None = Field(default=None, ge=300, le=850)
    utilization_pct: float = Field(default=0, ge=0, le=100)
    total_credit_limit: float = Field(default=0, ge=0)
    total_revolver_balance: float = Field(default=0, ge=0)
    late_payments_12mo: bool = Field(default=False)
    collections: bool = Field(default=False)
    collections_items: list[CollectionItem] = Field(default_factory=list)
    charge_offs: int = Field(default=0, ge=0)
    bankruptcies: int = Field(default=0, ge=0)
    inquiries_6mo: int = Field(default=0, ge=0)


class IntakeStep7(BaseModel):
    business_type: str = Field(default="")
    monthly_revenue: float = Field(default=0, ge=0)
    profit_pct: float = Field(default=5, ge=0, le=100)
    tax_pct: float = Field(default=15, ge=0, le=100)
    owner_pay_pct: float = Field(default=50, ge=0, le=100)
    opex_pct: float = Field(default=30, ge=0, le=100)


class IntakeStep8(BaseModel):
    footprints: dict = Field(default_factory=dict)


class IntakeComplete(BaseModel):
    display_name: str = Field(default="Architect")
    focus_season_months: int = Field(default=6, ge=1, le=12)
