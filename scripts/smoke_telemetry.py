#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import telemetry

SMOKE_EVENT = "telemetry_smoke_test"


def build_smoke_properties() -> dict[str, str]:
    return {
        "install_source": telemetry.config_source() or "source",
        "status": "manual",
    }


def main() -> int:
    if not telemetry.is_enabled():
        print(
            "Telemetry smoke test not sent: telemetry is disabled, opted out, running in CI/test mode, "
            "or no PostHog capture key is configured.",
            file=sys.stderr,
        )
        print(
            "Set POSTHOG_API_KEY, optional POSTHOG_HOST, and for CI smoke checks OPENSWARM_TELEMETRY_ALLOW_TESTS=1.",
            file=sys.stderr,
        )
        return 1

    sent = telemetry.capture(SMOKE_EVENT, build_smoke_properties())
    telemetry.shutdown()
    if not sent:
        print("Telemetry smoke test failed before the event could be queued.", file=sys.stderr)
        return 1

    print(f"Queued {SMOKE_EVENT}; check PostHog ingestion for this event.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
