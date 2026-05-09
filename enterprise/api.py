from typing import Annotated
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .agents import ENTERPRISE_AGENTS
from .audit import write_audit
from .database import get_db
from .models import AgentConfig, Artifact, AuditEvent, ProviderSecret, Role, RunState, SwarmRun, User, Workspace
from .orchestration import create_run_tasks, execute_run_once, requires_approval
from .schemas import (
    AgentOut,
    LoginIn,
    ProviderSecretIn,
    ProviderSecretOut,
    RunCreate,
    RunOut,
    TokenOut,
    UserOut,
    WorkspaceCreate,
    WorkspaceOut,
)
from .security import create_access_token, current_user, encrypt_secret, mask_secret, require_role, verify_password

router = APIRouter(prefix="/api")


@router.post("/auth/login", response_model=TokenOut)
def login(payload: LoginIn, request: Request, db: Annotated[Session, Depends(get_db)]) -> TokenOut:
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    write_audit(db, organization_id=user.organization_id, actor=user, action="login", resource_type="user", resource_id=user.id, request=request)
    return TokenOut(access_token=create_access_token(user))


@router.get("/me", response_model=UserOut)
def me(user: Annotated[User, Depends(current_user)]) -> User:
    return user


@router.get("/agents", response_model=list[AgentOut])
def list_agents(user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> list[AgentConfig]:
    configs = db.query(AgentConfig).filter(AgentConfig.organization_id == user.organization_id).order_by(AgentConfig.name).all()
    if configs:
        return configs
    for agent in ENTERPRISE_AGENTS:
        db.add(AgentConfig(organization_id=user.organization_id, key=agent["key"], name=agent["name"], description=agent["description"]))
    db.commit()
    return db.query(AgentConfig).filter(AgentConfig.organization_id == user.organization_id).order_by(AgentConfig.name).all()


@router.patch("/agents/{agent_id}", response_model=AgentOut)
def update_agent(
    agent_id: str,
    payload: dict,
    request: Request,
    user: Annotated[User, Depends(require_role(Role.manager))],
    db: Annotated[Session, Depends(get_db)],
) -> AgentConfig:
    agent = db.get(AgentConfig, agent_id)
    if not agent or agent.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Agent not found")
    if "enabled" in payload:
        agent.enabled = bool(payload["enabled"])
    if "settings" in payload and isinstance(payload["settings"], dict):
        agent.settings = payload["settings"]
    db.commit()
    db.refresh(agent)
    write_audit(db, organization_id=user.organization_id, actor=user, action="agent.update", resource_type="agent", resource_id=agent.id, request=request)
    return agent


@router.post("/workspaces", response_model=WorkspaceOut)
def create_workspace(
    payload: WorkspaceCreate,
    request: Request,
    user: Annotated[User, Depends(require_role(Role.manager))],
    db: Annotated[Session, Depends(get_db)],
) -> Workspace:
    workspace = Workspace(organization_id=user.organization_id, name=payload.name, description=payload.description)
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    write_audit(db, organization_id=user.organization_id, actor=user, action="workspace.create", resource_type="workspace", resource_id=workspace.id, request=request)
    return workspace


@router.get("/workspaces", response_model=list[WorkspaceOut])
def list_workspaces(user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> list[Workspace]:
    return db.query(Workspace).filter(Workspace.organization_id == user.organization_id).order_by(Workspace.created_at.desc()).all()


@router.post("/runs", response_model=RunOut, status_code=201)
def create_run(
    payload: RunCreate,
    request: Request,
    background: BackgroundTasks,
    user: Annotated[User, Depends(require_role(Role.member))],
    db: Annotated[Session, Depends(get_db)],
) -> SwarmRun:
    if payload.workspace_id:
        workspace = db.get(Workspace, payload.workspace_id)
        if not workspace or workspace.organization_id != user.organization_id:
            raise HTTPException(status_code=404, detail="Workspace not found")
    approval_required = requires_approval(payload.prompt)
    run = SwarmRun(
        organization_id=user.organization_id,
        workspace_id=payload.workspace_id,
        created_by_id=user.id,
        prompt=payload.prompt,
        state=RunState.waiting_for_input if approval_required else RunState.queued,
        cost_approval_required=approval_required,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    create_run_tasks(db, run)
    db.commit()
    write_audit(db, organization_id=user.organization_id, actor=user, action="run.create", resource_type="swarm_run", resource_id=run.id, request=request)
    if payload.auto_start and not approval_required:
        background.add_task(_execute_run_background, run.id)
    return run


def _execute_run_background(run_id: str) -> None:
    from .database import SessionLocal

    db = SessionLocal()
    try:
        execute_run_once(db, run_id)
    finally:
        db.close()


@router.post("/runs/{run_id}/approve", response_model=RunOut)
def approve_run(
    run_id: str,
    request: Request,
    background: BackgroundTasks,
    user: Annotated[User, Depends(require_role(Role.manager))],
    db: Annotated[Session, Depends(get_db)],
) -> SwarmRun:
    run = db.get(SwarmRun, run_id)
    if not run or run.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Run not found")
    run.state = RunState.queued
    run.cost_approval_required = False
    db.commit()
    write_audit(db, organization_id=user.organization_id, actor=user, action="run.approve", resource_type="swarm_run", resource_id=run.id, request=request)
    background.add_task(_execute_run_background, run.id)
    return run


@router.post("/runs/{run_id}/cancel", response_model=RunOut)
def cancel_run(
    run_id: str,
    request: Request,
    user: Annotated[User, Depends(require_role(Role.member))],
    db: Annotated[Session, Depends(get_db)],
) -> SwarmRun:
    run = db.get(SwarmRun, run_id)
    if not run or run.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Run not found")
    run.state = RunState.cancelled
    db.commit()
    write_audit(db, organization_id=user.organization_id, actor=user, action="run.cancel", resource_type="swarm_run", resource_id=run.id, request=request)
    return run


@router.get("/runs", response_model=list[RunOut])
def list_runs(user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> list[SwarmRun]:
    return db.query(SwarmRun).filter(SwarmRun.organization_id == user.organization_id).order_by(SwarmRun.created_at.desc()).limit(100).all()


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: str, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> SwarmRun:
    run = db.get(SwarmRun, run_id)
    if not run or run.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/runs/{run_id}/stream")
def stream_run(run_id: str, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]):
    run = db.get(SwarmRun, run_id)
    if not run or run.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Run not found")

    def events():
        yield f"event: status\ndata: {run.state.value}\n\n"
        yield f"event: summary\ndata: {run.result_summary or 'Run accepted'}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@router.get("/artifacts/{artifact_id}")
def get_artifact(
    artifact_id: str,
    request: Request,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    artifact = db.get(Artifact, artifact_id)
    if not artifact or artifact.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Artifact not found")
    write_audit(db, organization_id=user.organization_id, actor=user, action="artifact.read", resource_type="artifact", resource_id=artifact.id, request=request)
    return {"id": artifact.id, "name": artifact.name, "path": artifact.path, "content_type": artifact.content_type}


@router.post("/integrations/secrets", response_model=ProviderSecretOut)
def upsert_secret(
    payload: ProviderSecretIn,
    request: Request,
    user: Annotated[User, Depends(require_role(Role.admin))],
    db: Annotated[Session, Depends(get_db)],
) -> ProviderSecret:
    user_id = user.id if payload.scope == "user" else None
    secret = (
        db.query(ProviderSecret)
        .filter(
            ProviderSecret.organization_id == user.organization_id,
            ProviderSecret.user_id == user_id,
            ProviderSecret.provider == payload.provider,
        )
        .first()
    )
    if not secret:
        secret = ProviderSecret(organization_id=user.organization_id, user_id=user_id, provider=payload.provider, encrypted_value="", masked_value="")
        db.add(secret)
    secret.encrypted_value = encrypt_secret(payload.value)
    secret.masked_value = mask_secret(payload.value)
    db.commit()
    db.refresh(secret)
    write_audit(db, organization_id=user.organization_id, actor=user, action="secret.upsert", resource_type="provider_secret", resource_id=secret.id, request=request)
    return secret


@router.get("/integrations/secrets", response_model=list[ProviderSecretOut])
def list_secrets(user: Annotated[User, Depends(require_role(Role.admin))], db: Annotated[Session, Depends(get_db)]) -> list[ProviderSecret]:
    return db.query(ProviderSecret).filter(ProviderSecret.organization_id == user.organization_id).order_by(ProviderSecret.provider).all()


@router.get("/audit")
def list_audit(user: Annotated[User, Depends(require_role(Role.viewer))], db: Annotated[Session, Depends(get_db)]) -> list[dict]:
    events = db.query(AuditEvent).filter(AuditEvent.organization_id == user.organization_id).order_by(AuditEvent.created_at.desc()).limit(200).all()
    return [
        {
            "id": event.id,
            "action": event.action,
            "resource_type": event.resource_type,
            "resource_id": event.resource_id,
            "actor_id": event.actor_id,
            "created_at": event.created_at,
            "metadata": event.metadata_json,
        }
        for event in events
    ]


@router.get("/audit/export.csv")
def export_audit(user: Annotated[User, Depends(require_role(Role.admin))], db: Annotated[Session, Depends(get_db)]) -> Response:
    events = db.query(AuditEvent).filter(AuditEvent.organization_id == user.organization_id).order_by(AuditEvent.created_at.desc()).all()
    rows = ["created_at,actor_id,action,resource_type,resource_id"]
    rows.extend(f"{e.created_at},{e.actor_id or ''},{e.action},{e.resource_type},{e.resource_id or ''}" for e in events)
    return Response("\n".join(rows), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=audit.csv"})


@router.get("/usage")
def usage_summary(user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> dict:
    runs = db.query(SwarmRun).filter(SwarmRun.organization_id == user.organization_id).count()
    completed = db.query(SwarmRun).filter(SwarmRun.organization_id == user.organization_id, SwarmRun.state == RunState.completed).count()
    return {"runs": runs, "completed_runs": completed, "estimated_cost_cents": 0}

