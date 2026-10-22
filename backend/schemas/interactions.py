from pydantic import BaseModel, Field


class FootprintConnect(BaseModel):
    banking: bool = False
    calendar: bool = False
    screen_time: bool = False


class PatternAcknowledge(BaseModel):
    pattern_id: str
    accepted: bool = True


class ContractSign(BaseModel):
    display_name: str = Field(default="Architect", min_length=1)
    accepted_patterns: list[str] = Field(default_factory=list)
    focus_season_months: int = Field(default=6, ge=1, le=12)


class ForkPauseStart(BaseModel):
    item_description: str = Field(..., min_length=2)
    amount: float = Field(..., gt=0)
    bucket: str = Field(default="life")


class ForkEmotionAck(BaseModel):
    pause_id: int
    emotion: str = Field(..., description="stress|boredom|status|social|comfort|unknown")
    choose_architect_path: bool = Field(default=True)


class ForkRelease(BaseModel):
    pause_id: int | None = None
    release_all_unlocked: bool = False


class FocusSeasonToggle(BaseModel):
    active: bool
    creation_hour: str = Field(default="07:00", pattern=r"^\d{2}:\d{2}$")
