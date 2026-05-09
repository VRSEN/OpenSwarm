import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_enterprise.db")
os.environ.setdefault("ENTERPRISE_SECRET_KEY", "test-secret")
os.environ.setdefault("ENTERPRISE_ENCRYPTION_KEY", "AGQGfNV8e6-F3dtbbdH5SewiLPBl5hP4Y73Dfs4sVAk=")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "10000")

from fastapi.testclient import TestClient

from enterprise.database import Base, SessionLocal, engine
from enterprise.main import app
from enterprise.models import Organization, Role, User, Workspace
from enterprise.security import decrypt_secret, hash_password


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    org = Organization(name="Acme", slug="acme")
    other = Organization(name="Other", slug="other")
    db.add_all([org, other])
    db.commit()
    db.refresh(org)
    db.refresh(other)
    owner = User(
        organization_id=org.id,
        email="owner@example.com",
        name="Owner",
        role=Role.owner,
        password_hash=hash_password("Password123!"),
    )
    viewer = User(
        organization_id=org.id,
        email="viewer@example.com",
        name="Viewer",
        role=Role.viewer,
        password_hash=hash_password("Password123!"),
    )
    other_user = User(
        organization_id=other.id,
        email="other@example.com",
        name="Other",
        role=Role.owner,
        password_hash=hash_password("Password123!"),
    )
    workspace = Workspace(organization_id=other.id, name="Private", description="")
    db.add_all([owner, viewer, other_user, workspace])
    db.commit()
    db.close()


def token(client: TestClient, email: str) -> str:
    response = client.post("/api/auth/login", json={"email": email, "password": "Password123!"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_auth_rbac_and_audit_logging():
    client = TestClient(app)
    owner_token = token(client, "owner@example.com")
    viewer_token = token(client, "viewer@example.com")

    denied = client.post(
        "/api/workspaces",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={"name": "Denied", "description": ""},
    )
    assert denied.status_code == 403

    created = client.post(
        "/api/workspaces",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"name": "Enterprise", "description": "Shared team space"},
    )
    assert created.status_code == 200

    audit = client.get("/api/audit", headers={"Authorization": f"Bearer {owner_token}"})
    assert audit.status_code == 200
    assert any(event["action"] == "workspace.create" for event in audit.json())


def test_organization_isolation_for_workspace_runs():
    client = TestClient(app)
    owner_token = token(client, "owner@example.com")
    other_token = token(client, "other@example.com")

    workspace = client.post(
        "/api/workspaces",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"name": "Acme Workspace", "description": ""},
    ).json()

    response = client.post(
        "/api/runs",
        headers={"Authorization": f"Bearer {other_token}"},
        json={"workspace_id": workspace["id"], "prompt": "Research competitors"},
    )
    assert response.status_code == 404


def test_run_creation_and_approval_gate():
    client = TestClient(app)
    owner_token = token(client, "owner@example.com")
    response = client.post(
        "/api/runs",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"prompt": "Generate a product launch video with Sora", "auto_start": False},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["state"] == "waiting_for_input"
    assert body["cost_approval_required"] is True


def test_secret_encryption_api_access_control():
    client = TestClient(app)
    owner_token = token(client, "owner@example.com")
    viewer_token = token(client, "viewer@example.com")

    denied = client.post(
        "/api/integrations/secrets",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={"provider": "openai", "value": "sk-test-secret", "scope": "organization"},
    )
    assert denied.status_code == 403

    created = client.post(
        "/api/integrations/secrets",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"provider": "openai", "value": "sk-test-secret", "scope": "organization"},
    )
    assert created.status_code == 200
    assert created.json()["masked_value"] == "sk-t...cret"

    db = SessionLocal()
    try:
        from enterprise.models import ProviderSecret

        stored = db.query(ProviderSecret).first()
        assert stored.encrypted_value != "sk-test-secret"
        assert decrypt_secret(stored.encrypted_value) == "sk-test-secret"
    finally:
        db.close()

