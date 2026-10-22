#!/usr/bin/env python3
"""Focused smoke checks for OpenSwarm import bootstrap."""

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
MARKETPLACE_ENV_KEYS = (
    "OPENSWARM_MARKETPLACE_SWARM_ID",
    "OPENSWARM_MARKETPLACE_PARENT_SWARM_ID",
    "OPENSWARM_MARKETPLACE_SWARM_ORIGIN",
    "AGENTSWARM_MARKETPLACE_SWARM_ID",
    "AGENTSWARM_MARKETPLACE_PARENT_SWARM_ID",
    "AGENTSWARM_MARKETPLACE_SWARM_ORIGIN",
)


@contextmanager
def clean_marketplace_env(extra: dict[str, str] | None = None) -> Iterator[None]:
    old = {key: os.environ.get(key) for key in MARKETPLACE_ENV_KEYS}
    try:
        for key in MARKETPLACE_ENV_KEYS:
            os.environ.pop(key, None)
        if extra:
            os.environ.update(extra)
        yield
    finally:
        for key in MARKETPLACE_ENV_KEYS:
            os.environ.pop(key, None)
            if old[key] is not None:
                os.environ[key] = old[key]


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


def swarm_replacements(order: list[str], *, include_agency: bool = False) -> dict[str, types.ModuleType]:
    patches = module("patches", __path__=[])
    replacements = {
        "run_utils": module(
            "run_utils",
            _bootstrap=lambda: order.append("bootstrap"),
            _configure_product_env=lambda: order.append("product-env"),
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
        "patches.patch_ipython_interpreter_composio": module(
            "patches.patch_ipython_interpreter_composio",
            apply_ipython_composio_context_patch=lambda: order.append("patch"),
        ),
        "patches.patch_utf8_file_reads": module(
            "patches.patch_utf8_file_reads",
            apply_utf8_file_read_patch=lambda: order.append("patch"),
        ),
    }
    if not include_agency:
        return replacements

    class Agent:
        def __gt__(self, other: object) -> tuple[object, object]:
            return (self, other)

    class Agency:
        def __init__(self, *args: object, **kwargs: object) -> None:
            order.append("agency")

        def tui(self, **kwargs: object) -> None:
            order.append("tui")

    replacements.update({
        "agency_swarm": module("agency_swarm", Agency=Agency),
        "agency_swarm.tools": module("agency_swarm.tools", Handoff=object, SendMessage=object),
        "orchestrator": module("orchestrator", create_orchestrator=lambda: Agent()),
        "virtual_assistant": module("virtual_assistant", create_virtual_assistant=lambda: Agent()),
        "deep_research": module("deep_research", create_deep_research=lambda: Agent()),
        "data_analyst_agent": module("data_analyst_agent", create_data_analyst=lambda: Agent()),
        "slides_agent": module("slides_agent", create_slides_agent=lambda: Agent()),
        "docs_agent": module("docs_agent", create_docs_agent=lambda: Agent()),
        "video_generation_agent": module("video_generation_agent", create_video_generation_agent=lambda: Agent()),
        "image_generation_agent": module("image_generation_agent", create_image_generation_agent=lambda: Agent()),
    })
    return replacements


def smoke_swarm_import_skips_bootstrap() -> None:
    order: list[str] = []
    replacements = swarm_replacements(order)

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
    if "product-env" in order:
        raise RuntimeError(f"swarm.py configured product env during import instead of agency creation: {order}")
    if not order or order[0] != "dotenv":
        raise RuntimeError(f"swarm.py did not configure runtime during import: {order}")


def smoke_swarm_create_agency_configures_product_env() -> None:
    order: list[str] = []
    replacements = swarm_replacements(order, include_agency=True)

    spec = importlib.util.spec_from_file_location("swarm_create_agency_smoke", ROOT / "swarm.py")
    if not spec or not spec.loader:
        raise RuntimeError("could not load swarm.py create_agency import spec")

    old_key = os.environ.pop("OPENAI_API_KEY", None)
    try:
        with swapped_modules(replacements):
            swarm = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(swarm)
            swarm.create_agency()
    finally:
        if old_key is not None:
            os.environ["OPENAI_API_KEY"] = old_key
        sys.modules.pop("swarm_create_agency_smoke", None)

    if "bootstrap" in order:
        raise RuntimeError(f"swarm.py ran bootstrap during imported create_agency flow: {order}")
    if "product-env" not in order:
        raise RuntimeError(f"swarm.py create_agency did not configure OpenSwarm product env: {order}")
    if order.index("product-env") < order.index("dotenv"):
        raise RuntimeError(f"swarm.py create_agency configured product env before loading state dotenv: {order}")
    if order.index("product-env") > order.index("agency"):
        raise RuntimeError(f"swarm.py create_agency configured product env after agency creation: {order}")


def smoke_swarm_main_configures_product_env() -> None:
    order: list[str] = []
    replacements = swarm_replacements(order, include_agency=True)
    spec = importlib.util.spec_from_file_location("__main__", ROOT / "swarm.py")
    if not spec or not spec.loader:
        raise RuntimeError("could not load swarm.py main import spec")

    old_key = os.environ.pop("OPENAI_API_KEY", None)
    old_main = sys.modules.get("__main__")
    try:
        with swapped_modules(replacements):
            swarm = importlib.util.module_from_spec(spec)
            sys.modules["__main__"] = swarm
            spec.loader.exec_module(swarm)
    finally:
        if old_key is not None:
            os.environ["OPENAI_API_KEY"] = old_key
        if old_main is None:
            sys.modules.pop("__main__", None)
        else:
            sys.modules["__main__"] = old_main

    if "product-env" not in order:
        raise RuntimeError(f"swarm.py main did not configure OpenSwarm product env: {order}")
    if order.index("product-env") < order.index("dotenv"):
        raise RuntimeError(f"swarm.py configured product env before loading state dotenv: {order}")
    if order.index("product-env") > order.index("tui"):
        raise RuntimeError(f"swarm.py configured product env after TUI start: {order}")


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
                    "ENABLE_TELEMETRY": "false",
                    "OPEN_SWARM_TELEMETRY": "1",
                    "AGENTSWARM_TELEMETRY": "true",
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
                if os.environ.get("AGENTSWARM_PRODUCT_ENABLE_ADDONS") != "true":
                    raise RuntimeError("OpenSwarm Python path did not enable AgentSwarm add-ons")
                if os.environ.get("OPEN_SWARM_TELEMETRY") != "0" or os.environ.get("AGENTSWARM_TELEMETRY") != "0":
                    raise RuntimeError("OpenSwarm Python path did not map ENABLE_TELEMETRY=0 to AgentSwarm telemetry opt-outs")
                env.write_text(
                    'AGENTSWARM_BIN="/tmp/test-agentswarm"\nOPENAI_API_KEY="state-openai-updated"\n',
                    encoding="utf-8",
                )
                os.environ["OPENAI_API_KEY"] = "stale-openai"
                run_utils._load_openswarm_dotenv(override=True)
                if os.environ.get("OPENAI_API_KEY") != "state-openai-updated":
                    raise RuntimeError("OpenSwarm post-onboarding dotenv refresh did not replace stale process values")

                with clean_marketplace_env({
                    "OPENSWARM_MARKETPLACE_SWARM_ID": "someone/custom-swarm",
                    "OPENSWARM_MARKETPLACE_PARENT_SWARM_ID": "VRSEN/OpenSwarm",
                    "OPENSWARM_MARKETPLACE_SWARM_ORIGIN": "fork",
                }):
                    values = run_utils._product_env_from_config()
                if values.get("AGENTSWARM_MARKETPLACE_SWARM_ID") != "VRSEN/OpenSwarm":
                    raise RuntimeError("OpenSwarm Python Node config allowed ambient marketplace env swarm id")
                if "AGENTSWARM_MARKETPLACE_PARENT_SWARM_ID" in values:
                    raise RuntimeError("OpenSwarm Python Node config allowed ambient marketplace env parent swarm id")
                if values.get("AGENTSWARM_MARKETPLACE_SWARM_ORIGIN") != "original":
                    raise RuntimeError("OpenSwarm Python Node config allowed ambient marketplace env origin")
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

    with tempfile.TemporaryDirectory(prefix="openswarm-userbase-config-smoke-") as tmp:
        base = Path(tmp).resolve()
        module_dir = base / "site-packages"
        prefix = base / "venv"
        userbase = base / "user-base"
        module_dir.mkdir()
        prefix.mkdir()
        userbase.mkdir()
        (userbase / "openswarm.config.mjs").write_text(
            (ROOT / "openswarm.config.mjs").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (userbase / "openswarm.marketplace.json").write_text(
            (ROOT / "openswarm.marketplace.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (userbase / "openswarm.product-env.json").write_text(
            (ROOT / "openswarm.product-env.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (userbase / "package.json").write_text('{"version":"9.8.7-userbase"}\n', encoding="utf-8")

        with (
            patch.object(run_utils, "__file__", str(module_dir / "run_utils.py")),
            patch.object(run_utils.sys, "prefix", str(prefix)),
            patch.object(run_utils.site, "USER_BASE", str(userbase)),
            patch.object(run_utils.shutil, "which", lambda _name: None),
            patch.dict(os.environ, {"OPENSWARM_STATE_ROOT": str(base / "state")}, clear=False),
            clean_marketplace_env(),
        ):
            values = run_utils._product_env_from_config()
        if values.get("AGENTSWARM_PRODUCT_DISPLAY_NAME") != "OpenSwarm":
            raise RuntimeError("OpenSwarm Python path loaded wrong fallback product config from site.USER_BASE")
        if values.get("AGENTSWARM_PRODUCT_VERSION") != "9.8.7-userbase":
            raise RuntimeError("OpenSwarm Python fallback product env did not send the package version")
        if values.get("AGENTSWARM_MARKETPLACE_SWARM_ID") != "VRSEN/OpenSwarm":
            raise RuntimeError("OpenSwarm Python fallback product env did not send marketplace metadata")

        project = base / "project"
        project.mkdir()
        (project / "openswarm.marketplace.json").write_text(
            '{"swarmId":"someone/project-swarm","parentSwarmId":"VRSEN/OpenSwarm","swarmOrigin":"fork"}\n',
            encoding="utf-8",
        )
        old_cwd = Path.cwd()
        try:
            os.chdir(project)
            with (
                patch.object(run_utils, "__file__", str(module_dir / "run_utils.py")),
                patch.object(run_utils.sys, "prefix", str(prefix)),
                patch.object(run_utils.site, "USER_BASE", str(userbase)),
                patch.object(run_utils.shutil, "which", lambda _name: None),
                patch.dict(os.environ, {"OPENSWARM_STATE_ROOT": str(base / "state")}, clear=False),
                clean_marketplace_env(),
            ):
                values = run_utils._product_env_from_config()
        finally:
            os.chdir(old_cwd)
        if values.get("AGENTSWARM_MARKETPLACE_SWARM_ID") != "someone/project-swarm":
            raise RuntimeError("OpenSwarm Python fallback did not prefer project marketplace metadata")
        if values.get("AGENTSWARM_MARKETPLACE_PARENT_SWARM_ID") != "VRSEN/OpenSwarm":
            raise RuntimeError("OpenSwarm Python fallback did not use project marketplace parent swarm id")
        if values.get("AGENTSWARM_MARKETPLACE_SWARM_ORIGIN") != "fork":
            raise RuntimeError("OpenSwarm Python fallback did not use project marketplace origin")

        with (
            patch.object(run_utils, "__file__", str(module_dir / "run_utils.py")),
            patch.object(run_utils.sys, "prefix", str(prefix)),
            patch.object(run_utils.site, "USER_BASE", str(userbase)),
            patch.object(run_utils.shutil, "which", lambda _name: None),
            patch.dict(os.environ, {"AGENTSWARM_PRODUCT_VERSION": "stale-parent-version", "OPENSWARM_STATE_ROOT": str(base / "state")}, clear=False),
            clean_marketplace_env({
                "AGENTSWARM_MARKETPLACE_SWARM_ID": "stale/swarm",
                "AGENTSWARM_MARKETPLACE_PARENT_SWARM_ID": "stale/parent",
                "AGENTSWARM_MARKETPLACE_SWARM_ORIGIN": "fork",
            }),
        ):
            run_utils._configure_product_env()
            if os.environ.get("AGENTSWARM_PRODUCT_VERSION") != "9.8.7-userbase":
                raise RuntimeError("OpenSwarm Python fallback product env preserved a stale parent version")
            if os.environ.get("AGENTSWARM_MARKETPLACE_SWARM_ID") != "VRSEN/OpenSwarm":
                raise RuntimeError("OpenSwarm Python fallback product env preserved a stale marketplace swarm id")
            if os.environ.get("AGENTSWARM_MARKETPLACE_SWARM_ORIGIN") != "original":
                raise RuntimeError("OpenSwarm Python fallback product env preserved a stale marketplace origin")
            if "AGENTSWARM_MARKETPLACE_PARENT_SWARM_ID" in os.environ:
                raise RuntimeError("OpenSwarm Python fallback product env preserved a stale marketplace parent id")

        with (
            patch.object(run_utils, "__file__", str(module_dir / "run_utils.py")),
            patch.object(run_utils.sys, "prefix", str(prefix)),
            patch.object(run_utils.site, "USER_BASE", str(userbase)),
            patch.object(run_utils.shutil, "which", lambda _name: None),
            patch.dict(os.environ, {"OPENSWARM_STATE_ROOT": str(base / "state")}, clear=False),
            clean_marketplace_env({
                "OPENSWARM_MARKETPLACE_SWARM_ID": "someone/custom-swarm",
                "OPENSWARM_MARKETPLACE_PARENT_SWARM_ID": "VRSEN/OpenSwarm",
                "OPENSWARM_MARKETPLACE_SWARM_ORIGIN": "fork",
                "AGENTSWARM_MARKETPLACE_SWARM_ID": "stale/swarm",
                "AGENTSWARM_MARKETPLACE_PARENT_SWARM_ID": "stale/parent",
                "AGENTSWARM_MARKETPLACE_SWARM_ORIGIN": "unknown",
            }),
        ):
            values = run_utils._product_env_from_config()
        if values.get("AGENTSWARM_MARKETPLACE_SWARM_ID") != "VRSEN/OpenSwarm":
            raise RuntimeError("OpenSwarm Python fallback allowed ambient marketplace env swarm id")
        if "AGENTSWARM_MARKETPLACE_PARENT_SWARM_ID" in values:
            raise RuntimeError("OpenSwarm Python fallback allowed ambient marketplace env parent swarm id")
        if values.get("AGENTSWARM_MARKETPLACE_SWARM_ORIGIN") != "original":
            raise RuntimeError("OpenSwarm Python fallback allowed ambient marketplace env origin")

        with (
            patch.object(run_utils, "__file__", str(module_dir / "run_utils.py")),
            patch.object(run_utils.sys, "prefix", str(prefix)),
            patch.object(run_utils.site, "USER_BASE", str(userbase)),
            patch.object(run_utils.shutil, "which", lambda _name: None),
            patch.dict(os.environ, {"OPENSWARM_STATE_ROOT": str(base / "state")}, clear=False),
            clean_marketplace_env({
                "OPENSWARM_MARKETPLACE_SWARM_ID": "someone/custom-swarm",
                "OPENSWARM_MARKETPLACE_PARENT_SWARM_ID": "",
                "OPENSWARM_MARKETPLACE_SWARM_ORIGIN": "original",
            }),
        ):
            values = run_utils._product_env_from_config()
        if values.get("AGENTSWARM_MARKETPLACE_SWARM_ID") != "VRSEN/OpenSwarm":
            raise RuntimeError("OpenSwarm Python fallback allowed ambient marketplace env with empty parent")
        if "AGENTSWARM_MARKETPLACE_PARENT_SWARM_ID" in values:
            raise RuntimeError("OpenSwarm Python fallback allowed ambient empty marketplace parent")
        if values.get("AGENTSWARM_MARKETPLACE_SWARM_ORIGIN") != "original":
            raise RuntimeError("OpenSwarm Python fallback allowed ambient marketplace origin with empty parent")

        full_owner = "a" * 39
        full_repo = "b" * 100
        with (
            patch.object(run_utils, "__file__", str(module_dir / "run_utils.py")),
            patch.object(run_utils.sys, "prefix", str(prefix)),
            patch.object(run_utils.site, "USER_BASE", str(userbase)),
            patch.object(run_utils.shutil, "which", lambda _name: None),
            patch.dict(os.environ, {"OPENSWARM_STATE_ROOT": str(base / "state")}, clear=False),
            clean_marketplace_env({
                "OPENSWARM_MARKETPLACE_SWARM_ID": f"{full_owner}/{full_repo}",
                "OPENSWARM_MARKETPLACE_PARENT_SWARM_ID": "VRSEN/OpenSwarm",
                "OPENSWARM_MARKETPLACE_SWARM_ORIGIN": "fork",
            }),
        ):
            values = run_utils._product_env_from_config()
        if values.get("AGENTSWARM_MARKETPLACE_SWARM_ID") != "VRSEN/OpenSwarm":
            raise RuntimeError("OpenSwarm Python fallback allowed full-length ambient marketplace env")
        if "AGENTSWARM_MARKETPLACE_PARENT_SWARM_ID" in values:
            raise RuntimeError("OpenSwarm Python fallback allowed full-length ambient marketplace parent")
        if values.get("AGENTSWARM_MARKETPLACE_SWARM_ORIGIN") != "original":
            raise RuntimeError("OpenSwarm Python fallback allowed full-length ambient marketplace origin")

        with (
            patch.object(run_utils, "__file__", str(module_dir / "run_utils.py")),
            patch.object(run_utils.sys, "prefix", str(prefix)),
            patch.object(run_utils.site, "USER_BASE", str(userbase)),
            patch.object(run_utils.shutil, "which", lambda _name: None),
            patch.dict(os.environ, {"OPENSWARM_STATE_ROOT": str(base / "state")}, clear=False),
            clean_marketplace_env({
                "OPENSWARM_MARKETPLACE_SWARM_ID": "someone/custom-swarm",
                "OPENSWARM_MARKETPLACE_SWARM_ORIGIN": "fork",
            }),
        ):
            values = run_utils._product_env_from_config()
        if values.get("AGENTSWARM_MARKETPLACE_SWARM_ID") != "VRSEN/OpenSwarm":
            raise RuntimeError("OpenSwarm Python fallback allowed malformed ambient marketplace env")

        with (
            patch.object(run_utils, "__file__", str(module_dir / "run_utils.py")),
            patch.object(run_utils.sys, "prefix", str(prefix)),
            patch.object(run_utils.site, "USER_BASE", str(userbase)),
            patch.object(run_utils.shutil, "which", lambda _name: None),
            patch.dict(os.environ, {"OPENSWARM_STATE_ROOT": str(base / "state")}, clear=False),
            clean_marketplace_env({
                "OPENSWARM_MARKETPLACE_SWARM_ID": f"owner/{'a' * 129}",
                "OPENSWARM_MARKETPLACE_SWARM_ORIGIN": "original",
            }),
        ):
            values = run_utils._product_env_from_config()
        if values.get("AGENTSWARM_MARKETPLACE_SWARM_ID") != "VRSEN/OpenSwarm":
            raise RuntimeError("OpenSwarm Python fallback allowed overlong ambient marketplace env")

        early = base / "early-root"
        later = base / "later-root"
        early.mkdir()
        later.mkdir()
        (early / "openswarm.product-env.json").write_text(
            (ROOT / "openswarm.product-env.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (early / "openswarm.marketplace.json").write_text(
            '{"swarmId":"someone/custom-swarm","parentSwarmId":"VRSEN/OpenSwarm","swarmOrigin":"fork"}\n',
            encoding="utf-8",
        )
        (early / "package.json").write_text('{"version":"4.5.6-fallback"}\n', encoding="utf-8")
        (later / "openswarm.config.mjs").write_text(
            (ROOT / "openswarm.config.mjs").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (later / "package.json").write_text('{"version":"0.0.0-wrong-root"}\n', encoding="utf-8")

        with (
            patch.object(run_utils, "__file__", str(early / "run_utils.py")),
            patch.object(run_utils.Path, "cwd", lambda: base),
            patch.object(run_utils.sys, "prefix", str(later)),
            patch.object(run_utils.site, "USER_BASE", str(userbase)),
            patch.object(run_utils.shutil, "which", lambda _name: None),
            patch.dict(os.environ, {"OPENSWARM_STATE_ROOT": str(base / "state")}, clear=False),
        ):
            values = run_utils._product_env_from_config()
        if values.get("AGENTSWARM_PRODUCT_VERSION") != "4.5.6-fallback":
            raise RuntimeError("OpenSwarm Python fallback product env used package metadata from another root")
        if values.get("AGENTSWARM_MARKETPLACE_SWARM_ID") != "someone/custom-swarm":
            raise RuntimeError("OpenSwarm Python fallback did not use fork marketplace swarm id")
        if values.get("AGENTSWARM_MARKETPLACE_PARENT_SWARM_ID") != "VRSEN/OpenSwarm":
            raise RuntimeError("OpenSwarm Python fallback did not use fork marketplace parent swarm id")
        if values.get("AGENTSWARM_MARKETPLACE_SWARM_ORIGIN") != "fork":
            raise RuntimeError("OpenSwarm Python fallback did not use fork marketplace origin")

        (early / "openswarm.marketplace.json").write_text('{"swarmId":"","swarmOrigin":"fork"}\n', encoding="utf-8")
        with (
            patch.object(run_utils, "__file__", str(early / "run_utils.py")),
            patch.object(run_utils.Path, "cwd", lambda: base),
            patch.object(run_utils.sys, "prefix", str(later)),
            patch.object(run_utils.site, "USER_BASE", str(userbase)),
            patch.object(run_utils.shutil, "which", lambda _name: None),
            patch.dict(os.environ, {"OPENSWARM_STATE_ROOT": str(base / "state")}, clear=False),
        ):
            try:
                run_utils._product_env_from_config()
            except RuntimeError as exc:
                if "OpenSwarm marketplace metadata" not in str(exc):
                    raise
            else:
                raise RuntimeError("OpenSwarm Python fallback accepted malformed marketplace metadata")

        (early / "openswarm.marketplace.json").write_text('{"swarmId":"openswarm","swarmOrigin":"fork"}\n', encoding="utf-8")
        with (
            patch.object(run_utils, "__file__", str(early / "run_utils.py")),
            patch.object(run_utils.Path, "cwd", lambda: base),
            patch.object(run_utils.sys, "prefix", str(later)),
            patch.object(run_utils.site, "USER_BASE", str(userbase)),
            patch.object(run_utils.shutil, "which", lambda _name: None),
            patch.dict(os.environ, {"OPENSWARM_STATE_ROOT": str(base / "state")}, clear=False),
        ):
            try:
                run_utils._product_env_from_config()
            except RuntimeError as exc:
                if "GitHub owner/repo" not in str(exc):
                    raise
            else:
                raise RuntimeError("OpenSwarm Python fallback accepted non-GitHub marketplace metadata")

        (early / "openswarm.marketplace.json").write_text(
            '{"swarmId":"bad--owner/custom-swarm","swarmOrigin":"original"}\n',
            encoding="utf-8",
        )
        with (
            patch.object(run_utils, "__file__", str(early / "run_utils.py")),
            patch.object(run_utils.Path, "cwd", lambda: base),
            patch.object(run_utils.sys, "prefix", str(later)),
            patch.object(run_utils.site, "USER_BASE", str(userbase)),
            patch.object(run_utils.shutil, "which", lambda _name: None),
            patch.dict(os.environ, {"OPENSWARM_STATE_ROOT": str(base / "state")}, clear=False),
        ):
            try:
                run_utils._product_env_from_config()
            except RuntimeError as exc:
                if "GitHub owner/repo" not in str(exc):
                    raise
            else:
                raise RuntimeError("OpenSwarm Python fallback accepted invalid GitHub owner metadata")

        (early / "openswarm.marketplace.json").write_text(
            '{"swarmId":"someone/custom-swarm.GIT","swarmOrigin":"original"}\n',
            encoding="utf-8",
        )
        with (
            patch.object(run_utils, "__file__", str(early / "run_utils.py")),
            patch.object(run_utils.Path, "cwd", lambda: base),
            patch.object(run_utils.sys, "prefix", str(later)),
            patch.object(run_utils.site, "USER_BASE", str(userbase)),
            patch.object(run_utils.shutil, "which", lambda _name: None),
            patch.dict(os.environ, {"OPENSWARM_STATE_ROOT": str(base / "state")}, clear=False),
        ):
            try:
                run_utils._product_env_from_config()
            except RuntimeError as exc:
                if "GitHub owner/repo" not in str(exc):
                    raise
            else:
                raise RuntimeError("OpenSwarm Python fallback accepted .git marketplace metadata")

        (early / "openswarm.marketplace.json").write_text(
            f'{{"swarmId":"owner/{"a" * 129}","swarmOrigin":"original"}}\n',
            encoding="utf-8",
        )
        with (
            patch.object(run_utils, "__file__", str(early / "run_utils.py")),
            patch.object(run_utils.Path, "cwd", lambda: base),
            patch.object(run_utils.sys, "prefix", str(later)),
            patch.object(run_utils.site, "USER_BASE", str(userbase)),
            patch.object(run_utils.shutil, "which", lambda _name: None),
            patch.dict(os.environ, {"OPENSWARM_STATE_ROOT": str(base / "state")}, clear=False),
        ):
            try:
                run_utils._product_env_from_config()
            except RuntimeError as exc:
                if "GitHub owner/repo" not in str(exc):
                    raise
            else:
                raise RuntimeError("OpenSwarm Python fallback accepted overlong marketplace metadata")

        (early / "openswarm.marketplace.json").write_text(
            '{"swarmId":"someone/custom-swarm","swarmOrigin":"fork"}\n',
            encoding="utf-8",
        )
        with (
            patch.object(run_utils, "__file__", str(early / "run_utils.py")),
            patch.object(run_utils.Path, "cwd", lambda: base),
            patch.object(run_utils.sys, "prefix", str(later)),
            patch.object(run_utils.site, "USER_BASE", str(userbase)),
            patch.object(run_utils.shutil, "which", lambda _name: None),
            patch.dict(os.environ, {"OPENSWARM_STATE_ROOT": str(base / "state")}, clear=False),
        ):
            try:
                run_utils._product_env_from_config()
            except RuntimeError as exc:
                if "parentSwarmId is required" not in str(exc):
                    raise
            else:
                raise RuntimeError("OpenSwarm Python fallback accepted fork marketplace metadata without a parent")

        (early / "openswarm.marketplace.json").write_text(
            '{"swarmId":"someone/custom-swarm","parentSwarmId":"VRSEN/OpenSwarm","swarmOrigin":"copy"}\n',
            encoding="utf-8",
        )
        with (
            patch.object(run_utils, "__file__", str(early / "run_utils.py")),
            patch.object(run_utils.Path, "cwd", lambda: base),
            patch.object(run_utils.sys, "prefix", str(later)),
            patch.object(run_utils.site, "USER_BASE", str(userbase)),
            patch.object(run_utils.shutil, "which", lambda _name: None),
            patch.dict(os.environ, {"OPENSWARM_STATE_ROOT": str(base / "state")}, clear=False),
        ):
            try:
                run_utils._product_env_from_config()
            except RuntimeError as exc:
                if "swarmOrigin must be original, fork, or unknown" not in str(exc):
                    raise
            else:
                raise RuntimeError("OpenSwarm Python fallback accepted malformed marketplace origin")


def smoke_python_openswarm_tui_binary_resolution() -> None:
    sys.path.insert(0, str(ROOT))
    try:
        import run_utils
    finally:
        sys.path.pop(0)

    if run_utils._openswarm_package_names("linux", "x64", musl=True, baseline=True) != [
        "@vrsen/openswarm-cli-linux-x64-baseline-musl",
        "@vrsen/openswarm-cli-linux-x64-musl",
        "@vrsen/openswarm-cli-linux-x64-baseline",
        "@vrsen/openswarm-cli-linux-x64",
    ]:
        raise RuntimeError("OpenSwarm Python path did not prefer linux x64 baseline musl packages")
    if run_utils._openswarm_package_names("linux", "x64", musl=False, baseline=True) != [
        "@vrsen/openswarm-cli-linux-x64-baseline",
        "@vrsen/openswarm-cli-linux-x64",
        "@vrsen/openswarm-cli-linux-x64-baseline-musl",
        "@vrsen/openswarm-cli-linux-x64-musl",
    ]:
        raise RuntimeError("OpenSwarm Python path did not prefer linux x64 baseline glibc packages")
    if run_utils._openswarm_package_names("linux", "arm64", musl=True, baseline=False) != [
        "@vrsen/openswarm-cli-linux-arm64-musl",
        "@vrsen/openswarm-cli-linux-arm64",
    ]:
        raise RuntimeError("OpenSwarm Python path did not include linux arm64 musl package fallback")
    if run_utils._openswarm_package_names("windows", "x64", musl=False, baseline=True) != [
        "@vrsen/openswarm-cli-windows-x64-baseline",
        "@vrsen/openswarm-cli-windows-x64",
    ]:
        raise RuntimeError("OpenSwarm Python path did not prefer windows x64 baseline packages")

    with tempfile.TemporaryDirectory(prefix="openswarm-python-tui-smoke-") as tmp:
        root = Path(tmp).resolve()
        package = root / "node_modules" / "@vrsen" / "openswarm-cli-linux-x64-baseline-musl" / "bin"
        package.mkdir(parents=True)
        binary = package / "agentswarm"
        binary.write_text("#!/bin/sh\n", encoding="utf-8")
        module_dir = root / "site-packages"
        module_dir.mkdir()
        state = root / "state"
        state.mkdir()

        old_bin = os.environ.pop("AGENTSWARM_BIN", None)
        try:
            with (
                patch.object(run_utils, "__file__", str(module_dir / "run_utils.py")),
                patch.object(run_utils.sys, "platform", "linux"),
                patch.object(run_utils.platform_module, "machine", lambda: "x86_64"),
                patch.object(run_utils, "_supports_avx2", lambda _platform, _arch: False),
                patch.object(run_utils, "_is_musl", lambda: True),
                patch.dict(os.environ, {"OPENSWARM_STATE_ROOT": str(state)}, clear=False),
            ):
                run_utils._preload_agentswarm_bin(repo=module_dir)
                if os.environ.get("AGENTSWARM_BIN") != str(binary):
                    raise RuntimeError("OpenSwarm Python path did not preload the npm optional-package TUI binary")
        finally:
            if old_bin is None:
                os.environ.pop("AGENTSWARM_BIN", None)
            else:
                os.environ["AGENTSWARM_BIN"] = old_bin

    with (
        patch.object(run_utils.sys, "platform", "win32"),
        patch.object(run_utils.platform_module, "machine", lambda: "AMD64"),
        patch.object(run_utils, "_supports_avx2", lambda _platform, _arch: False),
        patch.object(run_utils, "_is_musl", lambda: False),
    ):
        specs = run_utils._openswarm_platform_packages()
    if specs[0] != ("@vrsen/openswarm-cli-windows-x64-baseline", "agentswarm.exe"):
        raise RuntimeError(f"OpenSwarm Python path did not use the Windows .exe binary name: {specs}")


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

    with tempfile.TemporaryDirectory(prefix="openswarm-bootstrap-tui-smoke-") as tmp:
        repo = Path(tmp).resolve()
        repo.joinpath("package.json").write_text('{"dependencies":{}}\n', encoding="utf-8")
        state = repo / "state"
        state.mkdir()
        binary = (
            repo
            / "node_modules"
            / "@vrsen"
            / "openswarm-cli-linux-x64-baseline-musl"
            / "bin"
            / "agentswarm"
        )

        def setup_node(repo: Path, npm: str) -> None:
            invoked.append((repo, npm))
            binary.parent.mkdir(parents=True)
            binary.write_text("#!/bin/sh\n", encoding="utf-8")

        old_bin = os.environ.pop("AGENTSWARM_BIN", None)
        invoked.clear()
        try:
            with (
                swapped_modules(replacements),
                patch.object(run_utils, "__file__", str(repo / "run_utils.py")),
                patch.object(run_utils.sys, "platform", "linux"),
                patch.object(run_utils.platform_module, "machine", lambda: "x86_64"),
                patch.object(run_utils, "_supports_avx2", lambda _platform, _arch: False),
                patch.object(run_utils, "_is_musl", lambda: True),
                patch.object(run_utils.shutil, "which", which),
                patch.object(run_utils.subprocess, "check_call", lambda *_args, **_kwargs: None),
                patch.object(run_utils, "_ensure_node_dependencies", setup_node),
                patch.dict(os.environ, {"OPENSWARM_STATE_ROOT": str(state)}, clear=False),
            ):
                run_utils._bootstrap()
                if os.environ.get("AGENTSWARM_BIN") != str(binary):
                    raise RuntimeError("bootstrap did not preload OpenSwarm TUI after npm optional-package setup")
        finally:
            if old_bin is None:
                os.environ.pop("AGENTSWARM_BIN", None)
            else:
                os.environ["AGENTSWARM_BIN"] = old_bin

    if invoked != [(repo, "npm")]:
        raise RuntimeError(f"bootstrap did not run npm setup before post-bootstrap TUI preload: {invoked}")


def main() -> int:
    smoke_swarm_import_skips_bootstrap()
    smoke_swarm_create_agency_configures_product_env()
    smoke_swarm_main_configures_product_env()
    smoke_product_state_root_env()
    smoke_python_openswarm_tui_binary_resolution()
    smoke_bootstrap_node_setup_installs_slides_dependencies()
    print("OpenSwarm import bootstrap smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
