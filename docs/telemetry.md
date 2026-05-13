# OpenSwarm Telemetry

OpenSwarm has backend-only PostHog telemetry for product analytics. It is enabled only when a PostHog capture key is available.

## Distribution Behavior

- npm releases can include a generated `openswarm_telemetry_config.py` file created by CI from `POSTHOG_API_KEY` and `POSTHOG_HOST` GitHub secrets.
- GitHub/source installs do not include a capture key and do not send telemetry unless the user explicitly sets `POSTHOG_API_KEY`.
- Python wheel/sdist artifacts intentionally exclude `openswarm_telemetry_config.py`; default telemetry injection is npm-release-only.
- Environment variables always win over the generated npm config.
- The runtime PostHog capture key shipped in npm is treated as public. Never use a personal API key for runtime telemetry.

Runtime config:

- `POSTHOG_API_KEY`: PostHog project capture key.
- `POSTHOG_HOST`: PostHog ingestion host. Defaults to `https://us.i.posthog.com`.

## Opt Out

Telemetry sends nothing when any of these are set:

- `OPENSWARM_TELEMETRY=false`
- `OPENSWARM_TELEMETRY=0`
- `OPENSWARM_TELEMETRY=no`
- `OPENSWARM_TELEMETRY=off`
- `DO_NOT_TRACK=1`

Telemetry is also disabled automatically under CI and pytest unless `OPENSWARM_TELEMETRY_ALLOW_TESTS=1` is set.

## Runtime Status

To inspect local telemetry status without printing any key:

```bash
python - <<'PY'
import telemetry

print({
    "enabled": telemetry.is_enabled(),
    "config_source": telemetry.config_source() or "missing",
    "has_capture_key": telemetry.has_posthog_key(),
})
PY
```

`config_source` is `env`, `npm_config`, or `missing`. This check does not print the capture key.

## Identity

OpenSwarm stores an anonymous local install UUID and install secret in `~/.openswarm/telemetry.json` by default. Set `OPENSWARM_CONFIG_DIR` to change that location.

Only derived identifiers are sent:

- `user_id`: SHA-256 of the anonymous install UUID.
- `workspace_id`: HMAC of the workspace path using the local install secret.
- `agent_id` and `parent_agent_id`: HMACs derived from agent names.

Raw workspace paths, raw user identifiers, API keys, emails, and Composio IDs are never sent.

## Events

- `app_started`
- `install_created`
- `onboarding_completed`
- `provider_configured`
- `message_sent`
- `swarm_run_started`
- `swarm_run_completed`
- `agent_run_started`
- `agent_run_completed`
- `llm_generation_completed`
- `tool_invoked`
- `handoff`
- `error`
- `telemetry_smoke_test` (manual smoke script only)

`agent_name` is sent as a raw, first-class property on agent-relevant events so product analytics can group usage by agent. `agent_id` remains HMAC-derived.

Runtime telemetry rejects event names outside this allowlist before initializing PostHog or building event properties.

## Allowed Properties

Only allowlisted scalar properties are sent:

- IDs: `user_id`, `workspace_id`, `session_id`, `thread_id`, `run_trace_id`, `agent_run_id`, `parent_run_id`
- Agent/model: `agent_name`, `agent_id`, `parent_agent_id`, `caller_agent_name`, `model`, `provider`, `tool_name`
- Message metadata: `message_role`, `message_type`
- Usage/performance: `tokens_input`, `tokens_output`, `cost_usd`, `latency_ms`, `stop_reason`, `status`, `is_streaming`
- Setup/auth: `auth_method`, `provider`, `has_provider_key`, `install_source`
- Errors: `error_type`, `error_category`, `status`, `http_status`

`model` and `provider` are additionally validated as short identifier-like values. Values that look like file paths, URLs, email addresses, API keys, tokens, or secrets are dropped. Numeric fields such as token counts, latency, HTTP status, and cost must be real numbers, and boolean fields must be real booleans.

## Privacy Policy

Telemetry must not include message contents, prompts, tool arguments, tool results, generated content, exception messages, stack traces, tracebacks, file paths, API keys, emails, Composio IDs, raw workspace paths, raw user IDs, or `telemetry_opted_out`.

If a user opts out, OpenSwarm emits no telemetry event at all.

## Dashboard

Run this with a PostHog personal API key to create the default dashboard:

```bash
POSTHOG_PERSONAL_API_KEY=phx_... \
POSTHOG_ENVIRONMENT_ID=12345 \
python scripts/create_posthog_dashboard.py
```

Optional:

```bash
POSTHOG_APP_HOST=https://us.posthog.com
```

The dashboard is named `OpenSwarm Product Analytics` and includes DAU, messages/day, agent runs/day, tool usage, error rate, and agent usage grouped by raw `agent_name`.

To inspect the exact API payloads without creating anything:

```bash
python scripts/create_posthog_dashboard.py --dry-run
```

## Smoke Test

To verify runtime telemetry can queue a safe manual event:

```bash
POSTHOG_API_KEY=phc_... \
POSTHOG_HOST=https://us.i.posthog.com \
python scripts/smoke_telemetry.py
```

The smoke script sends `telemetry_smoke_test` with only allowlisted metadata. It does not send message contents, prompts, tool arguments/results, exception messages, file paths, or keys.
