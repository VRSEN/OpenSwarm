import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from enterprise.agents import ENTERPRISE_AGENTS
from enterprise.database import SessionLocal, create_all
from enterprise.models import AgentConfig, Organization, Role, User, Workspace
from enterprise.security import hash_password


def main() -> None:
    create_all()
    db = SessionLocal()
    try:
        org = db.query(Organization).filter(Organization.slug == "acme").first()
        if not org:
            org = Organization(name="Acme Corp", slug="acme")
            db.add(org)
            db.commit()
            db.refresh(org)

        user = db.query(User).filter(User.organization_id == org.id, User.email == "admin@openswarm.local").first()
        if not user:
            db.add(
                User(
                    organization_id=org.id,
                    email="admin@openswarm.local",
                    name="Enterprise Admin",
                    role=Role.owner,
                    password_hash=hash_password("ChangeMe123!"),
                )
            )

        workspace = db.query(Workspace).filter(Workspace.organization_id == org.id, Workspace.name == "Default Workspace").first()
        if not workspace:
            db.add(Workspace(organization_id=org.id, name="Default Workspace", description="Seeded enterprise workspace"))

        for agent in ENTERPRISE_AGENTS:
            exists = db.query(AgentConfig).filter(AgentConfig.organization_id == org.id, AgentConfig.key == agent["key"]).first()
            if not exists:
                db.add(AgentConfig(organization_id=org.id, key=agent["key"], name=agent["name"], description=agent["description"]))

        db.commit()
        print("Seeded admin@openswarm.local / ChangeMe123!")
    finally:
        db.close()


if __name__ == "__main__":
    main()
