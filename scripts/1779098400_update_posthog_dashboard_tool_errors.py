#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.create_posthog_dashboard import DEFAULT_POSTHOG_APP_HOST, _post_json


DASHBOARD_TAGS = ["OpenSwarm", "Telemetry"]


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


def build_tool_error_insight_payloads(dashboard_id: int | str) -> list[dict[str, Any]]:
    return [
        _insight(
            "Tool errors by tool",
            "Tool error events grouped by safe tool_name.",
            _hogql_query(
                "SELECT "
                "coalesce(toString(properties.tool_name), 'unknown') AS tool_name, "
                "count() AS errors "
                "FROM events "
                "WHERE {filters} "
                "AND event = 'error' "
                "AND properties.error_category = 'tool' "
                "AND timestamp >= now() - INTERVAL 30 DAY "
                "GROUP BY tool_name "
                "ORDER BY errors DESC "
                "LIMIT 25"
            ),
            dashboard_id,
        ),
        _insight(
            "Tool success/error by tool",
            "Tool invocations grouped by safe tool_name and status.",
            _hogql_query(
                "SELECT "
                "coalesce(toString(properties.tool_name), 'unknown') AS tool_name, "
                "coalesce(toString(properties.status), 'unknown') AS status, "
                "count() AS invocations "
                "FROM events "
                "WHERE {filters} "
                "AND event = 'tool_invoked' "
                "AND timestamp >= now() - INTERVAL 30 DAY "
                "GROUP BY tool_name, status "
                "ORDER BY invocations DESC "
                "LIMIT 50"
            ),
            dashboard_id,
        ),
    ]


def build_dry_run_payload(environment_id: str = "POSTHOG_ENVIRONMENT_ID", dashboard_id: str = "POSTHOG_DASHBOARD_ID") -> dict[str, Any]:
    return {
        "insights": [
            {
                "method": "POST",
                "path": f"/api/environments/{environment_id}/insights/",
                "payload": payload,
            }
            for payload in build_tool_error_insight_payloads(dashboard_id)
        ],
    }


def update_dashboard(host: str, environment_id: str, dashboard_id: str, personal_api_key: str) -> dict[str, Any]:
    insights = [
        _post_json(
            host,
            f"/api/environments/{environment_id}/insights/",
            personal_api_key,
            payload,
        )
        for payload in build_tool_error_insight_payloads(dashboard_id)
    ]
    return {"insights": insights}


def main() -> int:
    parser = argparse.ArgumentParser(description="Add OpenSwarm tool error telemetry dashboard tiles.")
    parser.add_argument("--dry-run", action="store_true", help="Print insight API payloads without creating anything.")
    args = parser.parse_args()

    environment_id = os.getenv("POSTHOG_ENVIRONMENT_ID")
    dashboard_id = os.getenv("POSTHOG_DASHBOARD_ID")
    if args.dry_run:
        print(
            json.dumps(
                build_dry_run_payload(environment_id or "POSTHOG_ENVIRONMENT_ID", dashboard_id or "POSTHOG_DASHBOARD_ID"),
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    personal_api_key = os.getenv("POSTHOG_PERSONAL_API_KEY")
    host = os.getenv("POSTHOG_APP_HOST", DEFAULT_POSTHOG_APP_HOST)
    if not personal_api_key:
        raise SystemExit("POSTHOG_PERSONAL_API_KEY is required")
    if not environment_id:
        raise SystemExit("POSTHOG_ENVIRONMENT_ID is required")
    if not dashboard_id:
        raise SystemExit("POSTHOG_DASHBOARD_ID is required")

    update_dashboard(host, environment_id, dashboard_id, personal_api_key)
    dashboard_url = f"{host.rstrip('/')}/project/{environment_id}/dashboard/{dashboard_id}"
    print(f"Updated OpenSwarm tool telemetry dashboard tiles: {dashboard_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
