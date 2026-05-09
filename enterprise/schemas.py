from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

from .models import Role, RunState


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class UserOut(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: Role
    organization_id: str

    model_config = {"from_attributes": True}


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str = ""


class WorkspaceOut(BaseModel):
    id: str
    name: str
    description: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RunCreate(BaseModel):
    prompt: str = Field(min_length=3, max_length=20000)
    workspace_id: str | None = None
    auto_start: bool = True


class RunOut(BaseModel):
    id: str
    workspace_id: str | None
    prompt: str
    state: RunState
    cost_approval_required: bool
    error: str | None
    result_summary: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentOut(BaseModel):
    id: str
    key: str
    name: str
    description: str
    enabled: bool
    settings: dict

    model_config = {"from_attributes": True}


class ProviderSecretIn(BaseModel):
    provider: str = Field(pattern="^(openai|anthropic|google|fal|search|composio)$")
    value: str = Field(min_length=8)
    scope: str = Field(default="organization", pattern="^(organization|user)$")


class ProviderSecretOut(BaseModel):
    id: str
    provider: str
    masked_value: str
    user_id: str | None

    model_config = {"from_attributes": True}

