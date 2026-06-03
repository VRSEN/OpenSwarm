#!/usr/bin/env python3
"""Smoke checks for OpenSwarm wheel data-files bootstrap roots."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import tomllib
import types
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
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


def import_run_utils() -> types.ModuleType:
    sys.path.insert(0, str(ROOT))
    try:
        import run_utils
    finally:
        sys.path.pop(0)
    return run_utils


def wheel_paths(root: Path) -> tuple[Path, Path, Path, Path, Path]:
    module_dir = root / "site-packages"
    prefix = root / "prefix"
    userbase = root / "user-base"
    state = root / "state"
    for path in (module_dir, prefix, userbase, state):
        path.mkdir()
    (prefix / "package.json").write_text('{"version":"9.8.7-wheel"}\n', encoding="utf-8")
    (prefix / "openswarm.product-env.json").write_text("{}\n", encoding="utf-8")
    binary = prefix / "node_modules" / "@vrsen" / "openswarm-cli-linux-x64-baseline-musl" / "bin" / "agentswarm"
    return module_dir, prefix, userbase, state, binary


def import_build_pptx() -> types.ModuleType:
    replacements = {
        "agency_swarm": module("agency_swarm"),
        "agency_swarm.tools": module("agency_swarm.tools", BaseTool=object),
        "slides_agent": module("slides_agent", __path__=[str(ROOT / "slides_agent")]),
        "slides_agent.tools": module("slides_agent.tools", __path__=[str(ROOT / "slides_agent" / "tools")]),
    }
    name = "slides_agent.tools.BuildPptxFromHtmlSlides"
    sys.modules.pop(name, None)
    with swapped_modules(replacements):
        spec = importlib.util.spec_from_file_location(name, ROOT / "slides_agent" / "tools" / "BuildPptxFromHtmlSlides.py")
        if not spec or not spec.loader:
            raise RuntimeError("could not load BuildPptxFromHtmlSlides.py import spec")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return mod


@contextmanager
def patched_wheel(run_utils: types.ModuleType, module_dir: Path, prefix: Path, userbase: Path, state: Path) -> Iterator[None]:
    patches = (
        patch.object(run_utils, "__file__", str(module_dir / "run_utils.py")),
        patch.object(run_utils.sys, "prefix", str(prefix)),
        patch.object(run_utils.site, "USER_BASE", str(userbase)),
        patch.object(run_utils.sys, "platform", "linux"),
        patch.object(run_utils.platform_module, "machine", lambda: "x86_64"),
        patch.object(run_utils, "_supports_avx2", lambda _platform, _arch: False),
        patch.object(run_utils, "_is_musl", lambda: True),
        patch.dict(os.environ, {"OPENSWARM_STATE_ROOT": str(state)}, clear=False),
    )
    with ExitStack() as stack:
        for item in patches:
            stack.enter_context(item)
        yield


def smoke_preload_uses_wheel_metadata_root() -> None:
    run_utils = import_run_utils()
    with tempfile.TemporaryDirectory(prefix="openswarm-wheel-preload-") as tmp:
        module_dir, prefix, userbase, state, binary = wheel_paths(Path(tmp).resolve())
        binary.parent.mkdir(parents=True)
        binary.write_text("#!/bin/sh\n", encoding="utf-8")

        old_bin = os.environ.pop("AGENTSWARM_BIN", None)
        try:
            with patched_wheel(run_utils, module_dir, prefix, userbase, state):
                run_utils._preload_agentswarm_bin()
                if os.environ.get("AGENTSWARM_BIN") != str(binary):
                    raise RuntimeError("preload did not resolve the TUI binary from the wheel metadata root")
        finally:
            if old_bin is None:
                os.environ.pop("AGENTSWARM_BIN", None)
            else:
                os.environ["AGENTSWARM_BIN"] = old_bin


def smoke_bootstrap_installs_wheel_metadata_root() -> None:
    run_utils = import_run_utils()
    replacements = {name: module(name) for name in ("dotenv", "rich", "questionary", "agency_swarm")}

    def which(name: str) -> str | None:
        if name == "npm":
            return "npm"
        if name in {"soffice", "soffice.com", "pdftoppm"}:
            return f"/usr/bin/{name}"
        return None

    with tempfile.TemporaryDirectory(prefix="openswarm-wheel-bootstrap-") as tmp:
        module_dir, prefix, userbase, state, binary = wheel_paths(Path(tmp).resolve())
        calls: list[tuple[Path, str]] = []

        def setup(repo: Path, npm: str) -> None:
            calls.append((repo, npm))
            binary.parent.mkdir(parents=True)
            binary.write_text("#!/bin/sh\n", encoding="utf-8")

        old_bin = os.environ.pop("AGENTSWARM_BIN", None)
        try:
            with (
                swapped_modules(replacements),
                patched_wheel(run_utils, module_dir, prefix, userbase, state),
                patch.object(run_utils.shutil, "which", which),
                patch.object(run_utils.subprocess, "check_call", lambda *_args, **_kwargs: None),
                patch.object(run_utils, "_ensure_node_dependencies", setup),
            ):
                run_utils._bootstrap()
                if calls != [(prefix, "npm")]:
                    raise RuntimeError(f"bootstrap installed npm dependencies from the wrong root: {calls}")
                if os.environ.get("AGENTSWARM_BIN") != str(binary):
                    raise RuntimeError("bootstrap did not preload the TUI binary from the wheel metadata root")
        finally:
            if old_bin is None:
                os.environ.pop("AGENTSWARM_BIN", None)
            else:
                os.environ["AGENTSWARM_BIN"] = old_bin


def smoke_slides_python_uses_wheel_metadata_root() -> None:
    run_utils = import_run_utils()
    mod = import_build_pptx()

    with tempfile.TemporaryDirectory(prefix="openswarm-wheel-slides-") as tmp:
        module_dir, prefix, userbase, state, _binary = wheel_paths(Path(tmp).resolve())
        (prefix / "node_modules").mkdir()
        project = Path(tmp).resolve() / "presentations"
        project.mkdir()
        (project / "slide_01.html").write_text("<html><body>slide</body></html>\n", encoding="utf-8")
        calls: list[dict[str, object]] = []

        def run(cmd: list[str], **kwargs: object) -> types.SimpleNamespace:
            if cmd == ["node", "--version"]:
                return types.SimpleNamespace(returncode=0, stdout="", stderr="")
            calls.append({"cmd": cmd, **kwargs})
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")

        tool = mod.BuildPptxFromHtmlSlides.__new__(mod.BuildPptxFromHtmlSlides)
        tool.project_name = "deck"
        tool.slide_names = ["slide_01"]
        tool.output_filename = "deck"
        tool.layout = "LAYOUT_16x9_1280"
        tool.tmp_dir = str(Path(tmp) / "tmp")

        with (
            patched_wheel(run_utils, module_dir, prefix, userbase, state),
            patch.object(mod, "get_project_dir", lambda _name: project),
            patch.object(mod.subprocess, "run", run),
        ):
            result = tool.run()

        if not result.startswith("Presentation saved to:"):
            raise RuntimeError(f"Slides export did not pass with wheel-root node_modules: {result}")
        if len(calls) != 1:
            raise RuntimeError(f"Slides export ran unexpected subprocess calls: {calls}")
        call = calls[0]
        if call.get("cwd") != str(prefix):
            raise RuntimeError(f"Slides export used wrong cwd: {call.get('cwd')}")
        env = call.get("env")
        if not isinstance(env, dict) or env.get("OPENSWARM_PRODUCT_ROOT") != str(prefix):
            raise RuntimeError(f"Slides export did not pass the wheel product root to Node: {env}")


def smoke_slides_runner_uses_wheel_metadata_root() -> None:
    with tempfile.TemporaryDirectory(prefix="openswarm-wheel-runner-") as tmp:
        module_dir, prefix, _userbase, _state, _binary = wheel_paths(Path(tmp).resolve())
        bundle = prefix / "node_modules" / "dom-to-pptx" / "dist" / "dom-to-pptx.bundle.js"
        bundle.parent.mkdir(parents=True)
        bundle.write_text(
            "pptx.layout = 'LAYOUT_16x9';\nconst PPTX_WIDTH_IN = 10; const PPTX_HEIGHT_IN = 5.625;\n",
            encoding="utf-8",
        )
        playwright = prefix / "node_modules" / "playwright"
        playwright.mkdir(parents=True)
        playwright.joinpath("index.js").write_text(
            "exports.chromium={launch:async()=>{console.log('fake-playwright-from-product-root');process.exit(0)}}\n",
            encoding="utf-8",
        )
        slide = Path(tmp).resolve() / "slide.html"
        slide.write_text("<html><body>slide</body></html>\n", encoding="utf-8")
        result = subprocess.run(
            [
                "node",
                str(ROOT / "slides_agent" / "tools" / "html2pptx_runner.js"),
                "--output",
                str(Path(tmp) / "out.pptx"),
                "--layout",
                "LAYOUT_16x9_1280",
                "--tmp-dir",
                str(Path(tmp) / "runner-tmp"),
                "--",
                str(slide),
            ],
            cwd=str(module_dir),
            env={**os.environ, "OPENSWARM_PRODUCT_ROOT": str(prefix)},
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Slides runner failed with wheel-root node_modules: {result.stderr}")
        if "fake-playwright-from-product-root" not in result.stdout:
            raise RuntimeError(f"Slides runner did not load Playwright from the wheel product root: {result.stdout}")


def smoke_pyproject_packages_npm_patch_support() -> None:
    patch = "patches/dom-to-pptx+1.1.5.patch"
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    files = data["tool"]["setuptools"]["data-files"].get("patches", [])
    if patch not in files:
        raise RuntimeError(f"wheel data-files do not install npm patch support: {files}")
    if not (ROOT / patch).is_file():
        raise RuntimeError(f"npm patch support file is missing: {patch}")


def main() -> int:
    smoke_pyproject_packages_npm_patch_support()
    smoke_preload_uses_wheel_metadata_root()
    smoke_bootstrap_installs_wheel_metadata_root()
    smoke_slides_python_uses_wheel_metadata_root()
    smoke_slides_runner_uses_wheel_metadata_root()
    print("OpenSwarm wheel bootstrap smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
