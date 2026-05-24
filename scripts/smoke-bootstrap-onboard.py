#!/usr/bin/env python3
"""Focused smoke checks for OpenSwarm import bootstrap and onboarding writes."""

from __future__ import annotations

import importlib.util
import io
import os
import sys
import tempfile
import types
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def swapped_modules(replacements: dict[str, types.ModuleType]) -> Iterator[None]:
    marker = object()
    previous = {name: sys.modules.get(name, marker) for name in replacements}
    sys.modules.update(replacements)
    try:
        yield
    finally:
        for name, module in previous.items():
            if module is marker:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def module(name: str, **attrs: object) -> types.ModuleType:
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    return mod


def smoke_swarm_import_skips_bootstrap() -> None:
    order: list[str] = []

    patches = module("patches", __path__=[])
    replacements = {
        "run_utils": module(
            "run_utils",
            _bootstrap=lambda: order.append("bootstrap"),
            _preload_agentswarm_bin=lambda: order.append("preload"),
        ),
        "dotenv": module("dotenv", load_dotenv=lambda: order.append("dotenv")),
        "agents": module(
            "agents",
            set_tracing_disabled=lambda _value: order.append("agents"),
            set_tracing_export_api_key=lambda _value: order.append("agents"),
        ),
        "patches": patches,
        "patches.patch_agency_swarm_dual_comms": module(
            "patches.patch_agency_swarm_dual_comms",
            apply_dual_comms_patch=lambda: order.append("patch"),
        ),
        "patches.patch_file_attachment_refs": module(
            "patches.patch_file_attachment_refs",
            apply_file_attachment_reference_patch=lambda: order.append("patch"),
        ),
        "patches.patch_ipython_interpreter_composio": module(
            "patches.patch_ipython_interpreter_composio",
            apply_ipython_composio_context_patch=lambda: order.append("patch"),
        ),
        "patches.patch_utf8_file_reads": module(
            "patches.patch_utf8_file_reads",
            apply_utf8_file_read_patch=lambda: order.append("patch"),
        ),
    }

    spec = importlib.util.spec_from_file_location("swarm_bootstrap_smoke", ROOT / "swarm.py")
    if not spec or not spec.loader:
        raise RuntimeError("could not load swarm.py import spec")

    old_key = os.environ.pop("OPENAI_API_KEY", None)
    try:
        with swapped_modules(replacements):
            swarm = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(swarm)
    finally:
        if old_key is not None:
            os.environ["OPENAI_API_KEY"] = old_key
        sys.modules.pop("swarm_bootstrap_smoke", None)

    if "bootstrap" in order:
        raise RuntimeError(f"swarm.py ran bootstrap during import: {order}")
    if not order or order[0] != "dotenv":
        raise RuntimeError(f"swarm.py did not configure runtime during import: {order}")


def smoke_onboard_env_writes() -> None:
    sys.path.insert(0, str(ROOT))
    try:
        import onboard
        from rich.console import Console
    finally:
        sys.path.pop(0)

    provider = next(item for item in onboard.PROVIDERS if item["name"] == "OpenAI")
    secrets = iter(
        [
            "sk-test-openai",
            "search-test-key",
            "composio-test-key",
            "composio-test-user",
        ]
    )

    with tempfile.TemporaryDirectory(prefix="openswarm-onboard-smoke-") as tmp:
        env = Path(tmp) / ".env"
        sink = io.StringIO()
        with (
            patch.object(onboard, "ENV_PATH", env),
            patch.object(onboard, "console", Console(file=sink, force_terminal=False)),
            patch.object(onboard, "_ask_select", lambda _message, _choices: provider),
            patch.object(
                onboard,
                "_ask_checkbox",
                lambda _message, _choices: ["search", "composio"],
            ),
            patch.object(onboard, "_ask_secret", lambda _label, _url: next(secrets)),
            patch.object(onboard, "_ask_confirm", lambda _message, default=True: default),
        ):
            onboard.run_onboarding()

        values = onboard.dotenv_values(str(env))

    expected = {
        "OPENAI_API_KEY": "sk-test-openai",
        "DEFAULT_MODEL": provider["default_model"],
        "SEARCH_API_KEY": "search-test-key",
        "COMPOSIO_API_KEY": "composio-test-key",
        "COMPOSIO_USER_ID": "composio-test-user",
    }
    missing = {key: value for key, value in expected.items() if values.get(key) != value}
    if missing:
        raise RuntimeError(f"onboarding did not write expected .env values: {missing}")


def main() -> int:
    smoke_swarm_import_skips_bootstrap()
    smoke_onboard_env_writes()
    print("OpenSwarm import bootstrap and onboarding smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
