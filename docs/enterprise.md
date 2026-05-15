# OpenSwarm Enterprise

OpenSwarm Enterprise adds a multi-tenant control plane around the existing terminal-first OpenSwarm agents. The original `python swarm.py` CLI still starts the Agency Swarm TUI, and `python server.py` still starts the legacy Agency Swarm FastAPI integration unless `OPENSWARM_ENTERPRISE=true` is set.

## Architecture

- `enterprise/main.py` creates the enterprise FastAPI app, OpenAPI docs, dashboard routes, security headers, CORS, request-size limits, and rate limiting.
- `enterprise/models.py` defines organizations, users, workspaces, agent configs, durable swarm runs, agent tasks, artifacts, encrypted provider keys, integration metadata, audit events, and usage records.
- `enterprise/api.py` exposes the enterprise REST API.
- `enterprise/orchestration.py` persists run lifecycle state and provides the adapter point for executing the live Agency Swarm workflow from a worker.
- `enterprise/templates` and `enterprise/static` provide the web dashboard without adding a separate frontend build system.

## Local Development

```powershell
pip install -r requirements.txt -r requirements-dev.txt
Copy-Item .env.enterprise.example .env.enterprise
$env:OPENSWARM_ENTERPRISE = "true"
$env:ENTERPRISE_ENCRYPTION_KEY = python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
python scripts/migrate.py
python scripts/seed_enterprise.py
python server.py
```

Open `http://localhost:8080/login` and sign in with `admin@openswarm.local` / `ChangeMe123!`.

## Docker

```bash
cp .env.enterprise.example .env.enterprise
docker compose --profile enterprise up --build enterprise-api enterprise-worker postgres redis
```

## API

OpenAPI is available at `/api/docs`.

Important endpoints include `POST /api/auth/login`, `GET /api/me`, `GET /api/agents`, `POST /api/workspaces`, `POST /api/runs`, `GET /api/runs/{run_id}/stream`, `GET /api/artifacts/{artifact_id}`, `POST /api/integrations/secrets`, `GET /api/audit`, `GET /healthz`, and `GET /metrics`.

## Security Notes

Provider keys are encrypted with `ENTERPRISE_ENCRYPTION_KEY` and only masked values are returned by the API. Use a stable Fernet key in production, rotate it through a managed secret store, and never leave the example value in place.

All API queries are scoped by `organization_id`. RBAC uses owner, admin, manager, member, and viewer roles.
