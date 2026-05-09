from fastapi import Request
from sqlalchemy.orm import Session

from .models import AuditEvent, User
from .security import request_ip


def write_audit(
    db: Session,
    *,
    organization_id: str,
    action: str,
    resource_type: str,
    actor: User | None = None,
    resource_id: str | None = None,
    request: Request | None = None,
    metadata: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        organization_id=organization_id,
        actor_id=actor.id if actor else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=request_ip(request) if request else None,
        user_agent=request.headers.get("user-agent") if request else None,
        metadata_json=metadata or {},
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event

