#!/usr/bin/env python3
"""Focused smoke checks for OpenSwarm import bootstrap and onboarding writes."""

from __future__ import annotations

import importlib.util
import io
import json
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
            _openswarm_state_root=lambda: ROOT,
            _preload_agentswarm_bin=lambda: order.append("preload"),
        ),
        "dotenv": module("dotenv", load_dotenv=lambda *args, **kwargs: order.append("dotenv")),
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


def smoke_product_state_root_env() -> None:
    sys.path.insert(0, str(ROOT))
    try:
        import run_utils
    finally:
        sys.path.pop(0)

    with tempfile.TemporaryDirectory(prefix="openswarm-state-root-smoke-") as tmp:
        root = Path(tmp).resolve()
        env = root / ".env"
        env.write_text(
            'AGENTSWARM_BIN="/tmp/test-agentswarm"\nOPENAI_API_KEY="state-openai"\n',
            encoding="utf-8",
        )
        caller = root / "caller"
        caller.mkdir()
        (caller / ".env").write_text(
            'AGENTSWARM_BIN="/tmp/caller-agentswarm"\nOPENAI_API_KEY="caller-openai"\n',
            encoding="utf-8",
        )
        old_state = os.environ.pop("AGENTSWARM_PRODUCT_STATE_ROOT", None)
        old_bin = os.environ.pop("AGENTSWARM_BIN", None)
        old_key = os.environ.pop("OPENAI_API_KEY", None)
        old_cwd = Path.cwd()
        try:
            os.chdir(caller)
            with patch.dict(
                os.environ,
                {
                    "OPENSWARM_STATE_ROOT": str(root),
                    "AGENTSWARM_PRODUCT_STATE_ROOT": "/tmp/stale-openswarm-root",
                    "AGENTSWARM_BIN": "/explicit/bin",
                },
                clear=False,
            ):
                run_utils._preload_agentswarm_bin()
                run_utils._load_openswarm_dotenv()
                run_utils._configure_product_env()

                if os.environ.get("AGENTSWARM_PRODUCT_STATE_ROOT") != str(root):
                    raise RuntimeError("OpenSwarm did not configure AGENTSWARM_PRODUCT_STATE_ROOT from OPENSWARM_STATE_ROOT")
                if os.environ.get("OPENAI_API_KEY") != "state-openai":
                    raise RuntimeError("OpenSwarm did not load dotenv values from the fixed state root before caller cwd")
                if os.environ.get("AGENTSWARM_BIN") != "/explicit/bin":
                    raise RuntimeError("OpenSwarm overwrote explicit AGENTSWARM_BIN from the fixed state root .env")
                addons = json.loads(os.environ.get("AGENTSWARM_PRODUCT_ADDONS", "[]"))
                if {addon.get("id") for addon in addons} != {
                    "search",
                    "anthropic",
                    "composio",
                    "google",
                    "fal",
                    "pexels",
                    "pixabay",
                    "unsplash",
                }:
                    raise RuntimeError("OpenSwarm Python path did not configure the generic add-ons JSON")
                if "AGENTSWARM_PRODUCT_ENABLE_ADDONS" in os.environ:
                    raise RuntimeError("OpenSwarm Python path still configured the legacy add-ons flag")
                env.write_text(
                    'AGENTSWARM_BIN="/tmp/test-agentswarm"\nOPENAI_API_KEY="state-openai-updated"\n',
                    encoding="utf-8",
                )
                os.environ["OPENAI_API_KEY"] = "stale-openai"
                run_utils._load_openswarm_dotenv(override=True)
                if os.environ.get("OPENAI_API_KEY") != "state-openai-updated":
                    raise RuntimeError("OpenSwarm post-onboarding dotenv refresh did not replace stale process values")
        finally:
            os.chdir(old_cwd)
            if old_state is None:
                os.environ.pop("AGENTSWARM_PRODUCT_STATE_ROOT", None)
            else:
                os.environ["AGENTSWARM_PRODUCT_STATE_ROOT"] = old_state
            if old_bin is None:
                os.environ.pop("AGENTSWARM_BIN", None)
            else:
                os.environ["AGENTSWARM_BIN"] = old_bin
            if old_key is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = old_key

    with tempfile.TemporaryDirectory(prefix="openswarm-state-root-smoke-") as tmp:
        base = Path(tmp).resolve()
        root = base / "state"
        caller = base / "caller"
        caller.mkdir(parents=True)
        (caller / ".env").write_text('AGENTSWARM_BIN="/tmp/caller-agentswarm"\n', encoding="utf-8")
        old_bin = os.environ.pop("AGENTSWARM_BIN", None)
        old_cwd = Path.cwd()
        try:
            os.chdir(caller)
            with patch.dict(os.environ, {"OPENSWARM_STATE_ROOT": str(root)}, clear=False):
                run_utils._preload_agentswarm_bin(repo=caller)
                if "AGENTSWARM_BIN" in os.environ:
                    raise RuntimeError("OpenSwarm preloaded AGENTSWARM_BIN outside the fixed state root")
        finally:
            os.chdir(old_cwd)
            if old_bin is None:
                os.environ.pop("AGENTSWARM_BIN", None)
            else:
                os.environ["AGENTSWARM_BIN"] = old_bin


def smoke_bootstrap_node_setup_installs_slides_dependencies() -> None:
    sys.path.insert(0, str(ROOT))
    try:
        import run_utils
    finally:
        sys.path.pop(0)

    calls: list[dict[str, object]] = []

    def run(cmd: list[str], **kwargs: object) -> types.SimpleNamespace:
        calls.append({"cmd": cmd, **kwargs})
        if cmd == ["npm", "install", "--legacy-peer-deps"]:
            modules = Path(str(kwargs["cwd"])) / "node_modules"
            modules.mkdir(exist_ok=True)
            (modules / ".package-lock.json").write_text("{}\n", encoding="utf-8")
            for name in run_utils._REQUIRED_SLIDES_NODE_PACKAGES:
                (modules / name).mkdir(parents=True, exist_ok=True)
            return types.SimpleNamespace(returncode=0)
        if cmd[-3:] == ["install", "chromium", "chromium-headless-shell"]:
            env = kwargs.get("env")
            if not isinstance(env, dict):
                raise RuntimeError("Playwright install did not receive an environment")
            browsers = Path(str(env["PLAYWRIGHT_BROWSERS_PATH"]))
            (browsers / "chromium-1000").mkdir(parents=True)
            (browsers / "chromium_headless_shell-1000").mkdir()
        return types.SimpleNamespace(returncode=0)

    with tempfile.TemporaryDirectory(prefix="openswarm-node-bootstrap-smoke-") as tmp:
        repo = Path(tmp)
        (repo / "package.json").write_text('{"dependencies":{"playwright":"^1.59.1"}}\n', encoding="utf-8")
        modules = repo / "node_modules"
        modules.mkdir()
        (modules / ".package-lock.json").write_text("{}\n", encoding="utf-8")
        present = ("dom-to-pptx", "playwright", "pptxgenjs", "react", "react-dom", "react-icons")
        for name in present:
            (modules / name).mkdir()

        with (
            patch.object(
                run_utils.shutil,
                "which",
                lambda name: "/usr/local/bin/npx" if name == "npx" else None,
            ),
            patch.object(run_utils.subprocess, "run", run),
        ):
            if not run_utils._ensure_node_dependencies(repo, "npm"):
                raise RuntimeError("bootstrap reported failed Node setup for successful commands")

        expected = [
            ["npm", "install", "--legacy-peer-deps"],
            [
                "/usr/local/bin/npx",
                "-y",
                "playwright",
                "install",
                "chromium",
                "chromium-headless-shell",
            ],
        ]
        actual = [call["cmd"] for call in calls]
        if actual != expected:
            raise RuntimeError(f"bootstrap ran unexpected Node setup commands: {actual}")

        missing = [
            name
            for name in run_utils._REQUIRED_SLIDES_NODE_PACKAGES
            if not (repo / "node_modules" / name).exists()
        ]
        if missing:
            raise RuntimeError(f"bootstrap left required Slides npm modules missing: {missing}")

        browsers = repo / ".playwright-browsers"
        browser_prefixes = {path.name.split("-")[0] for path in browsers.iterdir()}
        if {"chromium", "chromium_headless_shell"} - browser_prefixes:
            raise RuntimeError(f"bootstrap left required Node Playwright browser assets missing: {sorted(browser_prefixes)}")

        for call in calls:
            if call.get("cwd") != str(repo):
                raise RuntimeError(f"bootstrap ran Node setup from wrong cwd: {calls}")

        env = calls[1].get("env")
        if not isinstance(env, dict):
            raise RuntimeError(f"bootstrap did not pass an environment to Playwright: {calls[1]}")
        if env.get("PLAYWRIGHT_BROWSERS_PATH") != str(repo / ".playwright-browsers"):
            raise RuntimeError(f"bootstrap set wrong Playwright browser path: {env.get('PLAYWRIGHT_BROWSERS_PATH')}")

        sink = io.StringIO()
        with (
            patch.object(run_utils.shutil, "which", lambda _name: None),
            patch("sys.stdout", sink),
        ):
            if run_utils._ensure_node_playwright_browsers(repo):
                raise RuntimeError("bootstrap reported successful Node Playwright setup without npx")
        if "npx was not found" not in sink.getvalue():
            raise RuntimeError("bootstrap did not warn when npx was unavailable")

        def fail_run(_cmd: list[str], **_kwargs: object) -> types.SimpleNamespace:
            return types.SimpleNamespace(returncode=7)

        (repo / "node_modules" / "sharp").rmdir()
        sink = io.StringIO()
        with (
            patch.object(run_utils.subprocess, "run", fail_run),
            patch.object(
                run_utils.shutil,
                "which",
                lambda name: "/usr/local/bin/npx" if name == "npx" else None,
            ),
            patch("sys.stdout", sink),
        ):
            if run_utils._ensure_node_dependencies(repo, "npm"):
                raise RuntimeError("bootstrap reported successful Node setup after command failures")
        if "OpenSwarm will continue" not in sink.getvalue():
            raise RuntimeError("bootstrap did not continue visibly after failed Node setup")

    invoked: list[tuple[Path, str]] = []

    def which(name: str) -> str | None:
        if name == "npm":
            return "npm"
        if name in {"soffice", "soffice.com", "pdftoppm"}:
            return f"/usr/bin/{name}"
        return None

    replacements = {
        "dotenv": module("dotenv"),
        "rich": module("rich"),
        "questionary": module("questionary"),
        "agency_swarm": module("agency_swarm"),
    }
    with (
        swapped_modules(replacements),
        patch.object(run_utils.shutil, "which", which),
        patch.object(run_utils.subprocess, "check_call", lambda *_args, **_kwargs: None),
        patch.object(run_utils, "_ensure_node_dependencies", lambda repo, npm: invoked.append((repo, npm))),
        patch.dict(os.environ, {"AGENTSWARM_BIN": "test-bin"}),
    ):
        run_utils._bootstrap()

    if invoked != [(ROOT, "npm")]:
        raise RuntimeError(f"bootstrap did not invoke Node dependency setup for package.json: {invoked}")


def main() -> int:
    smoke_swarm_import_skips_bootstrap()
    smoke_onboard_env_writes()
    smoke_product_state_root_env()
    smoke_bootstrap_node_setup_installs_slides_dependencies()
    print("OpenSwarm import bootstrap and onboarding smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
