from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from scripts.check_telemetry_artifact import contains_generated_config
from scripts.create_posthog_dashboard import build_dashboard_payload, build_dry_run_payload, build_insight_payloads
from scripts.smoke_telemetry import SMOKE_EVENT, build_smoke_properties
from scripts.write_telemetry_config import build_config_source


def test_config_writer_builds_generated_module() -> None:
    source = build_config_source("ph_test", "https://eu.i.posthog.com")

    assert "POSTHOG_API_KEY = 'ph_test'" in source
    assert "POSTHOG_HOST = 'https://eu.i.posthog.com'" in source
    assert "Do not commit this file" in source


def test_config_writer_requires_key() -> None:
    with pytest.raises(ValueError):
        build_config_source("")


def test_dashboard_payload_name() -> None:
    assert build_dashboard_payload()["name"] == "OpenSwarm Product Analytics"


def test_dashboard_agent_usage_groups_by_agent_name() -> None:
    payloads = build_insight_payloads(123)
    agent_usage = next(payload for payload in payloads if payload["name"] == "Agent usage by agent")

    source = agent_usage["query"]["source"]
    assert source["series"][0]["event"] == "agent_run_completed"
    assert source["breakdownFilter"]["breakdown"] == "agent_name"
    assert agent_usage["dashboards"] == [123]


def test_dashboard_dry_run_payload_has_no_secret_fields() -> None:
    payload = build_dry_run_payload("env_123")

    assert payload["dashboard"]["path"] == "/api/environments/env_123/dashboards/"
    assert payload["insights"][0]["path"] == "/api/environments/env_123/insights/"
    assert "POSTHOG_PERSONAL_API_KEY" not in str(payload)


def test_smoke_script_uses_manual_smoke_event() -> None:
    props = build_smoke_properties()

    assert SMOKE_EVENT == "telemetry_smoke_test"
    assert props["status"] == "manual"
    assert "POSTHOG_API_KEY" not in str(props)


def test_artifact_checker_detects_stale_generated_config(tmp_path) -> None:
    build_dir = tmp_path / "build" / "lib"
    build_dir.mkdir(parents=True)
    (build_dir / "openswarm_telemetry_config.py").write_text("POSTHOG_API_KEY = 'ph_stale'\n", encoding="utf-8")

    assert contains_generated_config(tmp_path / "build")


def test_python_wheel_excludes_stale_generated_config(tmp_path) -> None:
    repo = Path(__file__).resolve().parents[1]
    root_generated_config = repo / "openswarm_telemetry_config.py"
    stale_build_config = repo / "build" / "lib" / "openswarm_telemetry_config.py"
    root_generated_config.write_text("POSTHOG_API_KEY = 'ph_root'\n", encoding="utf-8")
    stale_build_config.parent.mkdir(parents=True, exist_ok=True)
    stale_build_config.write_text("POSTHOG_API_KEY = 'ph_stale'\n", encoding="utf-8")

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-build-isolation",
                "--no-deps",
                "-w",
                str(tmp_path),
                ".",
            ],
            cwd=repo,
            env={**os.environ, "OPENSWARM_TELEMETRY_ALLOW_TESTS": "1"},
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, result.stderr
        wheel = next(tmp_path.glob("*.whl"))
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
        assert "openswarm_telemetry_config.py" not in names
        assert not any(name.startswith("build/") for name in names)
    finally:
        root_generated_config.unlink(missing_ok=True)
        stale_build_config.unlink(missing_ok=True)


def test_npm_pack_includes_generated_config_after_writer() -> None:
    if not shutil.which("npm"):
        pytest.skip("npm is not installed")

    repo = Path(__file__).resolve().parents[1]
    root_generated_config = repo / "openswarm_telemetry_config.py"

    try:
        writer = subprocess.run(
            [sys.executable, "scripts/write_telemetry_config.py"],
            cwd=repo,
            env={
                **os.environ,
                "POSTHOG_API_KEY": "ph_pack_test",
                "POSTHOG_HOST": "https://example.i.posthog.com",
            },
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert writer.returncode == 0, writer.stderr

        packed = subprocess.run(
            ["npm", "pack", "--dry-run", "--json"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert packed.returncode == 0, packed.stderr
        package = json.loads(packed.stdout)[0]
        paths = {entry["path"] for entry in package["files"]}

        assert "openswarm_telemetry_config.py" in paths
    finally:
        root_generated_config.unlink(missing_ok=True)
