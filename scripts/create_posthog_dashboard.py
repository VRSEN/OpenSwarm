#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from typing import Any

DEFAULT_POSTHOG_APP_HOST = "https://us.posthog.com"
DASHBOARD_NAME = "OpenSwarm Product Analytics"
DASHBOARD_TAGS = ["OpenSwarm", "Telemetry"]
DASHBOARD_LAYOUT = [
    ("OpenSwarm / Active installs today", 0, 0, 0, 3, 3),
    ("OpenSwarm / Messages today", 1, 3, 0, 3, 3),
    ("OpenSwarm / Agent runs today", 2, 6, 0, 3, 3),
    ("OpenSwarm / Errors today", 3, 9, 0, 3, 3),
    ("OpenSwarm / Product activity by day", 4, 0, 3, 12, 5),
    ("OpenSwarm / Messages by role", 5, 0, 8, 6, 4),
    ("OpenSwarm / Agent usage by agent", 6, 6, 8, 6, 4),
    ("OpenSwarm / Tool usage by tool", 7, 0, 12, 6, 4),
    ("OpenSwarm / Errors by category", 8, 6, 12, 6, 4),
    ("OpenSwarm / Errors by type", 9, 0, 16, 6, 4),
    ("OpenSwarm / Error rate by day", 10, 6, 16, 6, 4),
    ("OpenSwarm / Recent telemetry samples", 11, 0, 20, 12, 5),
]


def build_dashboard_payload() -> dict[str, Any]:
    return {
        "name": DASHBOARD_NAME,
        "description": "Privacy-safe OpenSwarm telemetry: installs, messages, agent usage, tools, and errors.",
        "pinned": True,
        "tags": DASHBOARD_TAGS,
    }


def _trends_query(
    *,
    event: str | None = None,
    name: str | None = None,
    series: list[dict[str, Any]] | None = None,
    math: str = "total",
    breakdown: str | None = None,
    display: str = "ActionsLineGraph",
    date_from: str = "-30d",
) -> dict[str, Any]:
    if series is None:
        if event is None or name is None:
            raise ValueError("event and name are required when series is not provided")
        series = [{"kind": "EventsNode", "event": event, "name": name, "math": math}]
    source: dict[str, Any] = {
        "kind": "TrendsQuery",
        "dateRange": {"date_from": date_from},
        "interval": "day",
        "series": series,
        "trendsFilter": {"display": display},
    }
    if breakdown:
        source["breakdownFilter"] = {"breakdown_type": "event", "breakdown": breakdown}
    return {"kind": "InsightVizNode", "source": source}


def _hogql_query(query: str) -> dict[str, Any]:
    return {"kind": "DataVisualizationNode", "source": {"kind": "HogQLQuery", "query": query}}


def _insight(name: str, description: str, query: dict[str, Any], dashboard_id: int | str) -> dict[str, Any]:
    return {
        "name": f"OpenSwarm / {name}",
        "description": description,
        "query": query,
        "dashboards": [dashboard_id],
        "tags": DASHBOARD_TAGS,
    }


def build_insight_payloads(dashboard_id: int | str) -> list[dict[str, Any]]:
    return [
        _insight(
            "Active installs today",
            "Unique anonymous installs that started OpenSwarm in the last 24 hours.",
            _trends_query(event="app_started", name="Active installs", math="dau", display="BoldNumber", date_from="-24h"),
            dashboard_id,
        ),
        _insight(
            "Messages today",
            "User and assistant messages captured in the last 24 hours.",
            _trends_query(event="message_sent", name="Messages", display="BoldNumber", date_from="-24h"),
            dashboard_id,
        ),
        _insight(
            "Agent runs today",
            "Completed agent runs in the last 24 hours.",
            _trends_query(event="agent_run_completed", name="Completed agent runs", display="BoldNumber", date_from="-24h"),
            dashboard_id,
        ),
        _insight(
            "Errors today",
            "Safe error events in the last 24 hours.",
            _trends_query(event="error", name="Errors", display="BoldNumber", date_from="-24h"),
            dashboard_id,
        ),
        _insight(
            "Product activity by day",
            "Core OpenSwarm events over time.",
            _trends_query(
                series=[
                    {"kind": "EventsNode", "event": "app_started", "name": "App starts", "math": "total"},
                    {"kind": "EventsNode", "event": "message_sent", "name": "Messages", "math": "total"},
                    {"kind": "EventsNode", "event": "swarm_run_started", "name": "Swarm runs started", "math": "total"},
                    {"kind": "EventsNode", "event": "agent_run_completed", "name": "Agent runs completed", "math": "total"},
                    {"kind": "EventsNode", "event": "tool_invoked", "name": "Tools invoked", "math": "total"},
                    {"kind": "EventsNode", "event": "error", "name": "Errors", "math": "total"},
                ],
            ),
            dashboard_id,
        ),
        _insight(
            "Messages by role",
            "Message volume split by user vs assistant.",
            _trends_query(event="message_sent", name="Messages", breakdown="message_role", display="ActionsBarValue"),
            dashboard_id,
        ),
        _insight(
            "Agent usage by agent",
            "Completed agent runs grouped by raw agent_name.",
            _trends_query(event="agent_run_completed", name="Agent runs", breakdown="agent_name", display="ActionsBarValue"),
            dashboard_id,
        ),
        _insight(
            "Tool usage by tool",
            "Tool invocations grouped by safe tool_name.",
            _trends_query(event="tool_invoked", name="Tool invocations", breakdown="tool_name", display="ActionsBarValue"),
            dashboard_id,
        ),
        _insight(
            "Errors by category",
            "Safe error events grouped by error_category.",
            _trends_query(event="error", name="Errors", breakdown="error_category", display="ActionsBarValue"),
            dashboard_id,
        ),
        _insight(
            "Errors by type",
            "Safe error events grouped by exception class only.",
            _trends_query(event="error", name="Errors", breakdown="error_type", display="ActionsBarValue"),
            dashboard_id,
        ),
        _insight(
            "Error rate by day",
            "Errors divided by completed swarm runs. Zero completed runs returns zero instead of null.",
            _hogql_query(
                "SELECT "
                "toStartOfDay(timestamp) AS day, "
                "if(countIf(event = 'swarm_run_completed') = 0, 0, "
                "countIf(event = 'error') / countIf(event = 'swarm_run_completed')) AS error_rate "
                "FROM events "
                "WHERE {filters} "
                "AND event IN ('error', 'swarm_run_completed') "
                "AND timestamp >= now() - INTERVAL 30 DAY "
                "GROUP BY day "
                "ORDER BY day ASC"
            ),
            dashboard_id,
        ),
        _insight(
            "Recent telemetry samples",
            "Recent OpenSwarm events with only safe structured metadata.",
            _hogql_query(
                "SELECT "
                "timestamp, event, properties.agent_name AS agent_name, properties.message_role AS message_role, "
                "properties.tool_name AS tool_name, properties.error_type AS error_type, "
                "properties.error_category AS error_category, properties.status AS status "
                "FROM events "
                "WHERE {filters} "
                "AND event IN ('app_started', 'install_created', 'message_sent', 'swarm_run_started', "
                "'swarm_run_completed', 'agent_run_started', 'agent_run_completed', 'tool_invoked', 'error') "
                "AND timestamp >= now() - INTERVAL 7 DAY "
                "ORDER BY timestamp DESC "
                "LIMIT 50"
            ),
            dashboard_id,
        ),
    ]


def build_dashboard_tile_layouts(dashboard: dict[str, Any]) -> list[dict[str, Any]]:
    tiles_by_name = {
        tile.get("insight", {}).get("name"): tile
        for tile in dashboard.get("tiles", [])
        if tile.get("insight", {}).get("name")
    }
    layouts: list[dict[str, Any]] = []
    xs_y = 0
    for insight_name, order, x, y, width, height in DASHBOARD_LAYOUT:
        tile = tiles_by_name.get(insight_name)
        if not tile:
            raise ValueError(f"Dashboard is missing tile for {insight_name}")
        layouts.append(
            {
                "id": tile["id"],
                "order": order,
                "layouts": {
                    "sm": {"x": x, "y": y, "w": width, "h": height},
                    "xs": {"x": 0, "y": xs_y, "w": 1, "h": height},
                },
            }
        )
        xs_y += height
    return layouts


def build_dry_run_payload(environment_id: str = "POSTHOG_ENVIRONMENT_ID") -> dict[str, Any]:
    dashboard_id = "DRY_RUN_DASHBOARD_ID"
    return {
        "dashboard": {
            "method": "POST",
            "path": f"/api/environments/{environment_id}/dashboards/",
            "payload": build_dashboard_payload(),
        },
        "insights": [
            {
                "method": "POST",
                "path": f"/api/environments/{environment_id}/insights/",
                "payload": payload,
            }
            for payload in build_insight_payloads(dashboard_id)
        ],
    }


def _post_json(host: str, path: str, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json(host, path, api_key, method="POST", payload=payload)


def _patch_json(host: str, path: str, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json(host, path, api_key, method="PATCH", payload=payload)


def _get_json(host: str, path: str, api_key: str) -> dict[str, Any]:
    return _request_json(host, path, api_key, method="GET")


def _request_json(
    host: str,
    path: str,
    api_key: str,
    *,
    method: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{host.rstrip('/')}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"PostHog API request failed with {error.code}: {body}") from error


def create_dashboard(host: str, environment_id: str, personal_api_key: str) -> dict[str, Any]:
    dashboard = _post_json(
        host,
        f"/api/environments/{environment_id}/dashboards/",
        personal_api_key,
        build_dashboard_payload(),
    )
    dashboard_id = dashboard["id"]
    # PostHog inserts API-created dashboard tiles with the latest tile first.
    # Create in reverse so the dashboard opens with the KPI cards at the top.
    insights = [
        _post_json(
            host,
            f"/api/environments/{environment_id}/insights/",
            personal_api_key,
            insight_payload,
        )
        for insight_payload in reversed(build_insight_payloads(dashboard_id))
    ]
    dashboard = _get_json(host, f"/api/environments/{environment_id}/dashboards/{dashboard_id}/", personal_api_key)
    layout = build_dashboard_tile_layouts(dashboard)
    dashboard = _patch_json(
        host,
        f"/api/environments/{environment_id}/dashboards/{dashboard_id}/",
        personal_api_key,
        {"tiles": layout},
    )
    return {"dashboard": dashboard, "insights": insights, "layout": layout}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create the OpenSwarm PostHog product analytics dashboard.")
    parser.add_argument("--dry-run", action="store_true", help="Print dashboard and insight API payloads without creating anything.")
    args = parser.parse_args()

    environment_id = os.getenv("POSTHOG_ENVIRONMENT_ID")
    if args.dry_run:
        print(json.dumps(build_dry_run_payload(environment_id or "POSTHOG_ENVIRONMENT_ID"), indent=2, sort_keys=True))
        return 0

    personal_api_key = os.getenv("POSTHOG_PERSONAL_API_KEY")
    host = os.getenv("POSTHOG_APP_HOST", DEFAULT_POSTHOG_APP_HOST)
    if not personal_api_key:
        raise SystemExit("POSTHOG_PERSONAL_API_KEY is required")
    if not environment_id:
        raise SystemExit("POSTHOG_ENVIRONMENT_ID is required")

    result = create_dashboard(host, environment_id, personal_api_key)
    dashboard = result["dashboard"]
    dashboard_url = f"{host.rstrip('/')}/project/{environment_id}/dashboard/{dashboard['id']}"
    print(f"Created {DASHBOARD_NAME}: {dashboard_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
