#!/usr/bin/env python3
"""Live smoke test for the installed OpenSwarm Run-mode path."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import platform
import pty
import re
import select
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time
from collections.abc import Sequence


DEFAULT_PROMPT = "Reply exactly OPEN_SWARM_RUN_SMOKE_OK."
DEFAULT_EXPECT = "OPEN_SWARM_RUN_SMOKE_OK"
HANDOFF_PROMPT = "handoff to the data analyst"
HANDOFF_FOLLOWUP_PROMPT = "Reply exactly OPEN_SWARM_HANDOFF_OK."
HANDOFF_EXPECT = "OPEN_SWARM_HANDOFF_OK"
EXPECTED_AGENCY_NAME = "OpenSwarm"
EXPECTED_ENTRY_AGENT = "Orchestrator"
EXPECTED_SPECIALIST_AGENTS = [
    "General Agent",
    "Slides Agent",
    "Deep Research Agent",
    "Data Analyst",
    "Docs Agent",
    "Video Agent",
    "Image Agent",
]
EXPECTED_AGENT_COUNT = 1 + len(EXPECTED_SPECIALIST_AGENTS)


def run(cmd: Sequence[str], *, cwd: pathlib.Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True, check=True, timeout=600)


def latest_pack_stdout_line(stdout: str) -> str:
    for line in reversed(stdout.splitlines()):
        value = line.strip()
        if value:
            return value
    raise RuntimeError("npm pack did not print a tarball name")


def resolve_local_package(value: str) -> pathlib.Path:
    package = pathlib.Path(value).expanduser()
    if not package.is_absolute():
        package = pathlib.Path.cwd() / package
    package = package.resolve()
    if not package.exists():
        raise RuntimeError(f"local AgentSwarm package does not exist at {package}")
    return package


def resolve_models_fixture(package: pathlib.Path | None) -> pathlib.Path | None:
    if not package or not package.is_dir():
        return None
    fixture = package / "test" / "tool" / "fixtures" / "models-api.json"
    return fixture if fixture.exists() else None


def resolve_local_binary(value: str) -> pathlib.Path:
    binary = pathlib.Path(value).expanduser()
    if not binary.is_absolute():
        binary = pathlib.Path.cwd() / binary
    binary = binary.resolve()
    if not binary.exists():
        raise RuntimeError(f"local OpenSwarm TUI binary does not exist at {binary}")
    if not binary.is_file():
        raise RuntimeError(f"local OpenSwarm TUI binary is not a file at {binary}")
    return binary


def platform_asset_name() -> str:
    machine = platform.machine().lower()
    if machine in {"arm64", "aarch64"}:
        arch = "arm64"
    elif machine in {"x86_64", "amd64"}:
        arch = "x64"
    else:
        arch = None

    if sys.platform == "darwin" and arch:
        return f"agentswarm-darwin-{arch}"
    if sys.platform.startswith("linux") and arch:
        return f"agentswarm-linux-{arch}"
    if sys.platform == "win32" and arch:
        return f"agentswarm-windows-{arch}.exe"
    raise RuntimeError(
        f"unsupported OpenSwarm TUI asset platform: {sys.platform} {platform.machine()}"
    )


def platform_package_name() -> str:
    asset = platform_asset_name()
    if asset.endswith(".exe"):
        asset = asset[:-4]
    return asset.replace("agentswarm-", "@vrsen/openswarm-cli-", 1)


def install_openswarm_tui_binary(package_dir: pathlib.Path, binary: pathlib.Path) -> pathlib.Path:
    executable = "agentswarm.exe" if sys.platform == "win32" else "agentswarm"
    target = package_dir / "node_modules" / pathlib.Path(*platform_package_name().split("/")) / "bin" / executable
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(binary, target)
    if os.name != "nt":
        target.chmod(target.stat().st_mode | 0o111)
    return target


def create_local_openswarm_project(package_dir: pathlib.Path, root: pathlib.Path, name: str = "openswarm") -> pathlib.Path:
    target = root / name
    ignore = shutil.ignore_patterns(
        ".git",
        ".venv",
        "__pycache__",
        "node_modules",
        "agentswarm-*",
        "*.tgz",
    )
    shutil.copytree(package_dir, target, ignore=ignore)
    return target


def install_package(
    repo: pathlib.Path,
    root: pathlib.Path,
    source: str,
    npm_spec: str,
    agentswarm_path: pathlib.Path | None,
    env: dict[str, str],
) -> pathlib.Path:
    run(["npm", "init", "-y"], cwd=root, env=env)
    if source == "local":
        packed = run(["npm", "pack"], cwd=repo, env=env)
        tarball = repo / latest_pack_stdout_line(packed.stdout)
        try:
            run(["npm", "install", str(tarball)], cwd=root, env=env)
        finally:
            tarball.unlink(missing_ok=True)
    else:
        run(["npm", "install", npm_spec], cwd=root, env=env)

    if agentswarm_path:
        run(["npm", "install", str(agentswarm_path)], cwd=root, env=env)

    launcher = root / "node_modules" / ".bin" / "openswarm"
    if not launcher.exists():
        raise RuntimeError(f"openswarm launcher was not installed at {launcher}")
    package_dir = root / "node_modules" / "@vrsen" / "openswarm"
    if not package_dir.exists():
        raise RuntimeError(f"OpenSwarm package directory was not installed at {package_dir}")
    return launcher


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)


def write(fd: int, text: str) -> None:
    os.write(fd, text.encode())


def compact(text: str) -> str:
    return re.sub(r"\s+", "", text)


def is_run_mode_ready(plain: str) -> bool:
    packed = compact(plain).lower()
    has_current_footer = "run·swarmdefault" in packed or "runswarmdefault" in packed
    has_command_ui = "tabagents" in packed and "ctrl+pcommands" in packed
    has_legacy_footer = "agencyswarmdefault" in packed
    return has_command_ui and (has_current_footer or has_legacy_footer)


def terminate(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGINT)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=10)
            return
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                return
            process.wait(timeout=10)


def terminate_processes_under(root: pathlib.Path) -> None:
    match = str(root)
    current = os.getpid()
    try:
        found = subprocess.run(["pgrep", "-f", match], text=True, capture_output=True, check=False)
    except FileNotFoundError:
        return
    pids = [int(line) for line in found.stdout.splitlines() if line.strip().isdigit()]
    for pid in pids:
        if pid != current:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    if pids:
        time.sleep(2)
    for pid in pids:
        if pid != current:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def set_window_size(fd: int, rows: int = 45, columns: int = 180) -> None:
    size = struct.pack("HHHH", rows, columns, 0, 0)
    termios.tcsetwinsize(fd, (rows, columns))
    try:
        import fcntl

        fcntl.ioctl(fd, termios.TIOCSWINSZ, size)
    except Exception:
        pass


def run_tui_smoke(
    launcher: pathlib.Path,
    package_dir: pathlib.Path,
    launcher_cwd: pathlib.Path,
    root: pathlib.Path,
    env: dict[str, str],
    check: str,
    prompt: str,
    expected: str,
    timeout: int,
) -> str:
    master_fd, slave_fd = pty.openpty()
    set_window_size(slave_fd)
    process = subprocess.Popen(
        [str(launcher)],
        cwd=launcher_cwd,
        env=env,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        start_new_session=True,
    )
    os.close(slave_fd)

    raw = ""
    plain = ""
    sent_confirm = False
    sent_agents_command = False
    verified_agents = False
    closed_agents_at: float | None = None
    sent_models_slash = False
    saw_models_slash = False
    cleared_models_probe = False
    sent_models_direct = False
    saw_models_direct = False
    selected_models_command = False
    models_slash_at: float | None = None
    models_clear_at: float | None = None
    models_direct_at: float | None = None
    models_slash_start = 0
    models_direct_start = 0
    models_picker_start = 0
    verified_models = False
    closed_models_at: float | None = None
    sent_prompt = False
    saw_expected = False
    sent_handoff_prompt = False
    saw_handoff = False
    handoff_seen_at: float | None = None
    sent_handoff_followup = False
    deadline = time.monotonic() + timeout
    expected_compact = compact(expected)
    handoff_expected_compact = compact(HANDOFF_EXPECT)
    expected_agent_terms = [EXPECTED_AGENCY_NAME, EXPECTED_ENTRY_AGENT, *EXPECTED_SPECIALIST_AGENTS]
    expected_agent_compact = [compact(term) for term in expected_agent_terms]

    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                break
            ready, _, _ = select.select([master_fd], [], [], 1)
            if ready:
                chunk = os.read(master_fd, 8192)
                if chunk:
                    decoded = chunk.decode(errors="replace")
                    raw += decoded
                    plain = strip_ansi(raw)

            compact_plain = compact(plain)
            lower_compact = compact_plain.lower()

            if "failedtostartresponsestream" in lower_compact or "cannotreachagency-swarmbackend" in lower_compact:
                raise RuntimeError("OpenSwarm backend became unreachable during smoke test")

            if not sent_confirm and (
                "Createalocal`.venv`inthisproject?" in compact_plain
                or "Createanisolatedprojectenvironment?" in compact_plain
            ):
                write(master_fd, "\r")
                sent_confirm = True

            run_mode_ready = is_run_mode_ready(plain)

            if check in {"agents", "all"} and not sent_agents_command and run_mode_ready:
                write(master_fd, "/agents\r")
                sent_agents_command = True

            if sent_agents_command and not verified_agents and (
                "Selectswarm" in compact_plain or "Selectagent" in compact_plain
            ):
                missing = [term for term, packed in zip(expected_agent_terms, expected_agent_compact) if packed not in compact_plain]
                if not missing:
                    verified_agents = True
                    write(master_fd, "\x1b")
                    closed_agents_at = time.monotonic()
                    if check == "agents":
                        return plain

            if check == "prompt" and run_mode_ready:
                verified_agents = True
                closed_agents_at = closed_agents_at or time.monotonic()

            if check == "handoff" and run_mode_ready and not sent_handoff_prompt:
                write(master_fd, HANDOFF_PROMPT + "\r")
                sent_handoff_prompt = True

            if sent_handoff_prompt and not saw_handoff:
                if "transfer_to_Data_Analyst" in plain or "DataAnalyst" in compact_plain:
                    saw_handoff = True
                    handoff_seen_at = time.monotonic()

            if (
                saw_handoff
                and not sent_handoff_followup
                and handoff_seen_at is not None
                and time.monotonic() - handoff_seen_at > 0.5
            ):
                write(master_fd, HANDOFF_FOLLOWUP_PROMPT + "\r")
                sent_handoff_followup = True

            if check == "handoff" and (HANDOFF_EXPECT in plain or handoff_expected_compact in compact_plain):
                return plain

            agents_ready = check not in {"agents", "all"} or verified_agents
            if (
                check in {"models", "all"}
                and agents_ready
                and not sent_models_slash
                and run_mode_ready
                and (closed_agents_at is None or time.monotonic() - closed_agents_at > 0.5)
            ):
                models_slash_start = len(plain)
                write(master_fd, "/")
                sent_models_slash = True
                models_slash_at = time.monotonic()

            if sent_models_slash and not selected_models_command:
                models_slash = compact(plain[models_slash_start:]).lower()
                if not saw_models_slash and "/models" in models_slash:
                    saw_models_slash = True
                if (
                    saw_models_slash
                    and not cleared_models_probe
                    and models_slash_at is not None
                    and time.monotonic() - models_slash_at > 0.5
                ):
                    write(master_fd, "\x7f")
                    cleared_models_probe = True
                    models_clear_at = time.monotonic()
                elif (
                    cleared_models_probe
                    and not sent_models_direct
                    and models_clear_at is not None
                    and time.monotonic() - models_clear_at > 0.2
                ):
                    models_direct_start = len(plain)
                    write(master_fd, "/models")
                    sent_models_direct = True
                    models_direct_at = time.monotonic()
                elif sent_models_direct and not saw_models_direct:
                    models_direct = compact(plain[models_direct_start:]).lower()
                    if "/models" in models_direct and "switchmodel" in models_direct:
                        saw_models_direct = True
                elif (
                    saw_models_direct
                    and models_direct_at is not None
                    and time.monotonic() - models_direct_at > 0.5
                ):
                    models_picker_start = len(plain)
                    write(master_fd, "\r")
                    selected_models_command = True

            if selected_models_command and not verified_models:
                models_picker = compact(plain[models_picker_start:]).lower()
                if "selectmodel" in models_picker and (
                    "swarmdefault" in models_picker
                    or "agencyswarmdefault" in models_picker
                    or "manageproviderauth" in models_picker
                ):
                    verified_models = True
                    write(master_fd, "\x1b")
                    closed_models_at = time.monotonic()
                    if check == "models":
                        return plain

            if check == "prompt":
                verified_models = True
                closed_models_at = closed_models_at or closed_agents_at or time.monotonic()

            models_ready = check not in {"models", "all"} or verified_models
            closed_picker_at = closed_models_at or closed_agents_at
            if (
                check in {"prompt", "all"}
                and verified_agents
                and models_ready
                and not sent_prompt
                and closed_picker_at is not None
                and time.monotonic() - closed_picker_at > 0.5
            ):
                write(master_fd, prompt + "\r")
                sent_prompt = True

            if expected in plain or expected_compact in compact_plain:
                saw_expected = True
                return plain
    finally:
        terminate(process)
        terminate_processes_under(root)
        os.close(master_fd)

    log_path = root / "openswarm-run-mode-smoke.log"
    log_path.write_text(plain or raw, encoding="utf-8")
    raise RuntimeError(
        "OpenSwarm Run-mode smoke test did not reach the expected response. "
        f"sent_confirm={sent_confirm} sent_agents_command={sent_agents_command} "
        f"verified_agents={verified_agents} sent_models_slash={sent_models_slash} "
        f"saw_models_slash={saw_models_slash} cleared_models_probe={cleared_models_probe} "
        f"sent_models_direct={sent_models_direct} saw_models_direct={saw_models_direct} "
        f"selected_models_command={selected_models_command} "
        f"verified_models={verified_models} sent_prompt={sent_prompt} saw_expected={saw_expected} "
        f"sent_handoff_prompt={sent_handoff_prompt} saw_handoff={saw_handoff} "
        f"sent_handoff_followup={sent_handoff_followup} log={log_path}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["local", "npm"], default="local")
    parser.add_argument("--npm-spec")
    parser.add_argument(
        "--agentswarm-package",
        help="Local @vrsen/agentswarm tarball or package directory to install after OpenSwarm for smoke proof.",
    )
    parser.add_argument(
        "--openswarm-tui-binary",
        help="Local OpenSwarm-branded AgentSwarm TUI binary to copy into the installed @vrsen/openswarm package.",
    )
    parser.add_argument("--check", choices=["all", "agents", "models", "prompt", "handoff"], default="all")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--expect", default=DEFAULT_EXPECT)
    parser.add_argument("--timeout", type=int, default=1200)
    parser.add_argument("--keep-root", action="store_true")
    args = parser.parse_args()

    repo = pathlib.Path(__file__).resolve().parents[1]
    package_json = json.loads((repo / "package.json").read_text(encoding="utf-8"))
    npm_spec = args.npm_spec or f"{package_json['name']}@{package_json['version']}"
    agentswarm_path = resolve_local_package(args.agentswarm_package) if args.agentswarm_package else None
    openswarm_tui_binary = resolve_local_binary(args.openswarm_tui_binary) if args.openswarm_tui_binary else None
    models_fixture = resolve_models_fixture(agentswarm_path)
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key and args.check in {"prompt", "handoff"} and os.environ.get("GITHUB_ACTIONS") == "true":
        print("Skipped OpenSwarm live prompt smoke because OPENAI_API_KEY is not configured")
        return 0
    if not api_key and args.check in {"all", "prompt", "handoff"}:
        raise RuntimeError("OPENAI_API_KEY is required for the live prompt smoke test")
    auth_key = api_key or "dummy-openai-key-for-agent-roster-smoke"
    root = pathlib.Path(tempfile.mkdtemp(prefix="openswarm-run-mode-smoke-"))
    state_root = root / "openswarm-state"
    env = os.environ.copy()
    env.update(
        {
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "CI": "1",
            "TERM": "xterm-256color",
            "OPENCODE_AUTH_CONTENT": json.dumps({"openai": {"type": "api", "key": auth_key}}),
            "XDG_DATA_HOME": str(root / "xdg-data"),
            "XDG_CONFIG_HOME": str(root / "xdg-config"),
            "XDG_CACHE_HOME": str(root / "xdg-cache"),
            "XDG_STATE_HOME": str(root / "xdg-state"),
            "OPENSWARM_STATE_ROOT": str(state_root),
            "OPENCODE_DISABLE_AUTOUPDATE": "true",
            "OPENCODE_DISABLE_MODELS_FETCH": "true",
        }
    )
    if models_fixture:
        env["OPENCODE_MODELS_PATH"] = str(models_fixture)

    try:
        launcher = install_package(repo, root, args.source, npm_spec, agentswarm_path, env)
        package_dir = root / "node_modules" / "@vrsen" / "openswarm"
        if openswarm_tui_binary:
            install_openswarm_tui_binary(package_dir, openswarm_tui_binary)
        generic_dir = root / "my-agency"
        generic_dir.mkdir()
        (generic_dir / "agency.py").write_text(
            "\n".join(
                [
                    "from agency_swarm import Agency",
                    "",
                    "def create_agency(load_threads_callback=None):",
                    "    return Agency(name='Generic Agency')",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state_root.mkdir(parents=True, exist_ok=True)
        project_dir = create_local_openswarm_project(package_dir, state_root, "project")
        plain = run_tui_smoke(launcher, package_dir, project_dir, root, env, args.check, args.prompt, args.expect, args.timeout)
        if not is_run_mode_ready(plain):
            raise RuntimeError("Smoke response was seen, but OpenSwarm Run mode and command UI were not detected")
        if args.check in {"agents", "all"}:
            print(f"OpenSwarm /agents smoke passed with {EXPECTED_AGENT_COUNT} agents visible")
        if args.check in {"models", "all"}:
            print("OpenSwarm /models smoke passed")
        if args.check in {"prompt", "all"}:
            print("OpenSwarm live prompt smoke passed")
        if args.check == "handoff":
            print("OpenSwarm handoff smoke passed")
        print(f"OpenSwarm smoke root package: {package_dir}")
        return 0
    finally:
        if args.keep_root:
            print(f"Kept smoke root: {root}")
        else:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"FAILED: {error}", file=sys.stderr)
        raise SystemExit(1)
