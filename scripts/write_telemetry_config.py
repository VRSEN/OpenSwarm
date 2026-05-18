#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path

DEFAULT_POSTHOG_HOST = "https://us.i.posthog.com"
HEADER = """# Generated during npm release packaging.
# Do not commit this file. The PostHog capture key is treated as public.
"""


def build_config_source(api_key: str, host: str | None = None) -> str:
    if not api_key:
        raise ValueError("POSTHOG_API_KEY is required")
    resolved_host = host or DEFAULT_POSTHOG_HOST
    return (
        HEADER
        + f"POSTHOG_API_KEY = {api_key!r}\n"
        + f"POSTHOG_HOST = {resolved_host!r}\n"
    )


def write_config(path: Path, api_key: str, host: str | None = None) -> None:
    path.write_text(build_config_source(api_key, host), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Write npm-release-only OpenSwarm telemetry config.")
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parents[1] / "openswarm_telemetry_config.py"),
        help="Generated Python module path.",
    )
    args = parser.parse_args()

    api_key = os.getenv("POSTHOG_API_KEY", "")
    host = os.getenv("POSTHOG_HOST") or DEFAULT_POSTHOG_HOST
    if not api_key:
        raise SystemExit("POSTHOG_API_KEY is required to generate npm telemetry config")

    output = Path(args.output)
    write_config(output, api_key, host)
    print(f"Wrote telemetry config to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
