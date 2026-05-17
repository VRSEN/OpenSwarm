#!/usr/bin/env python3
"""Live smoke test for the installed OpenSwarm Run-mode path."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
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


def run(cmd: Sequence[str], *, cwd: pathlib.Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True, check=True, timeout=600)


def latest_pack_stdout_line(stdout: str) -> str:
    for line in reversed(stdout.splitlines()):
        value = line.strip()
        if value:
            return value
    raise RuntimeError("npm pack did not print a tarball name")


def install_package(repo: pathlib.Path, root: pathlib.Path, source: str, npm_spec: str, env: dict[str, str]) -> pathlib.Path:
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
        cwd=package_dir,
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
    sent_prompt = False
    saw_expected = False
    deadline = time.monotonic() + timeout
    expected_compact = compact(expected)
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

            if not sent_confirm and "Createalocal`.venv`inthisproject?" in compact_plain:
                write(master_fd, "\r")
                sent_confirm = True

            run_mode_ready = "AgencySwarmDefault" in compact_plain and "ctrl+pcommands" in compact_plain

            if check in {"agents", "all"} and not sent_agents_command and run_mode_ready:
                write(master_fd, "/agents\r")
                sent_agents_command = True

            if sent_agents_command and not verified_agents and "Selectswarm" in compact_plain:
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

            if (
                check in {"prompt", "all"}
                and verified_agents
                and not sent_prompt
                and closed_agents_at is not None
                and time.monotonic() - closed_agents_at > 0.5
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
        f"verified_agents={verified_agents} sent_prompt={sent_prompt} saw_expected={saw_expected} log={log_path}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["local", "npm"], default="local")
    parser.add_argument("--npm-spec")
    parser.add_argument("--check", choices=["all", "agents", "prompt"], default="all")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--expect", default=DEFAULT_EXPECT)
    parser.add_argument("--timeout", type=int, default=1200)
    parser.add_argument("--keep-root", action="store_true")
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for this live OpenSwarm Run-mode smoke test")

    repo = pathlib.Path(__file__).resolve().parents[1]
    package_json = json.loads((repo / "package.json").read_text(encoding="utf-8"))
    npm_spec = args.npm_spec or f"{package_json['name']}@{package_json['version']}"
    root = pathlib.Path(tempfile.mkdtemp(prefix="openswarm-run-mode-smoke-"))
    env = os.environ.copy()
    env.update(
        {
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "TERM": "xterm-256color",
            "OPENCODE_AUTH_CONTENT": json.dumps({"openai": {"type": "api", "key": api_key}}),
            "XDG_DATA_HOME": str(root / "xdg-data"),
            "XDG_CONFIG_HOME": str(root / "xdg-config"),
            "XDG_CACHE_HOME": str(root / "xdg-cache"),
            "XDG_STATE_HOME": str(root / "xdg-state"),
        }
    )

    try:
        launcher = install_package(repo, root, args.source, npm_spec, env)
        package_dir = root / "node_modules" / "@vrsen" / "openswarm"
        plain = run_tui_smoke(launcher, package_dir, root, env, args.check, args.prompt, args.expect, args.timeout)
        if "Agency Swarm Default" not in plain:
            raise RuntimeError("Smoke response was seen, but Agency Swarm Run mode was not detected")
        if args.check in {"agents", "all"}:
            print(f"OpenSwarm /agents smoke passed with {len(EXPECTED_SPECIALIST_AGENTS)} specialists visible")
        if args.check in {"prompt", "all"}:
            print("OpenSwarm live prompt smoke passed")
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
