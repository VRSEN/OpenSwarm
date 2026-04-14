import os
import sys
import subprocess
import shutil
import tempfile
from pathlib import Path

# ── Bootstrap: create venv + install deps automatically on first run ─────────
# Only stdlib imports above. _bootstrap() is called explicitly — either from
# swarm.py (via `from run import _bootstrap; _bootstrap()`) or from the
# __main__ guard below — never at module level, so `from run import _bootstrap`
# is safe to call from outside the venv.
def _bootstrap() -> None:
    _repo = Path(__file__).resolve().parent
    _venv = _repo / ".venv"
    _venv_python = _venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")

    # If not running inside the repo venv, set it up and re-launch into it.
    if Path(sys.executable).resolve() != _venv_python.resolve():
        if not _venv_python.exists():
            print("Setting up virtual environment…")
            subprocess.check_call([sys.executable, "-m", "venv", str(_venv)])
            print("Installing dependencies, please wait…\n")
            subprocess.check_call([str(_venv_python), "-m", "pip", "install", "-e", str(_repo)])
            print("\nDone.\n")
        # Use subprocess.run instead of os.execv — on Windows, os.execv hands off
        # the ConPTY pipe in a broken state which causes the TUI to receive mouse
        # movements as text input. subprocess.run keeps the parent alive as the
        # terminal owner and gives the child clean handle inheritance.
        sys.exit(subprocess.run([str(_venv_python)] + sys.argv).returncode)

    # Running inside the venv — ensure deps are present (handles missing/corrupt install).
    try:
        import dotenv        # noqa: F401
        import rich          # noqa: F401
        import questionary   # noqa: F401
        import agency_swarm  # noqa: F401
    except ImportError:
        print("Installing dependencies, please wait…\n")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", str(_repo)])
        print("\nDone.\n")
        sys.exit(subprocess.run([sys.executable] + sys.argv).returncode)

    # Ensure the Playwright browser binary for the installed playwright version
    # is present. playwright install is idempotent — it exits quickly if the
    # right revision is already downloaded.
    try:
        subprocess.check_call(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass

    # Install LibreOffice and Poppler if missing (used by Slides Agent).
    # Auto-installs when a known package manager is available; silently skips otherwise.
    _soffice = "soffice.com" if sys.platform == "win32" else "soffice"
    if not shutil.which(_soffice):
        if sys.platform == "darwin" and shutil.which("brew"):
            print("Installing LibreOffice (required for Slides Agent), please wait…\n")
            subprocess.check_call(["brew", "install", "--cask", "libreoffice"])
            print("\nDone.\n")
        elif sys.platform.startswith("linux") and shutil.which("apt-get"):
            print("Installing LibreOffice (required for Slides Agent), please wait…\n")
            subprocess.check_call(["sudo", "apt-get", "install", "-y", "libreoffice-impress"])
            print("\nDone.\n")
        elif sys.platform == "win32" and shutil.which("winget"):
            print("Installing LibreOffice (required for Slides Agent), please wait…\n")
            subprocess.check_call(["winget", "install", "--id", "TheDocumentFoundation.LibreOffice", "-e", "--silent"])
            print("\nDone.\n")
        else:
            print(
                "Warning: LibreOffice not found — Slides Agent thumbnail and export features "
                "will be unavailable.\n"
                "  Install it from: https://www.libreoffice.org/download/download-libreoffice/\n"
            )

    if not shutil.which("pdftoppm"):
        if sys.platform == "darwin" and shutil.which("brew"):
            print("Installing Poppler (required for Slides Agent), please wait…\n")
            subprocess.check_call(["brew", "install", "poppler"])
            print("\nDone.\n")
        elif sys.platform.startswith("linux") and shutil.which("apt-get"):
            print("Installing Poppler (required for Slides Agent), please wait…\n")
            subprocess.check_call(["sudo", "apt-get", "install", "-y", "poppler-utils"])
            print("\nDone.\n")
        elif sys.platform == "win32" and shutil.which("winget"):
            print("Installing Poppler (required for Slides Agent), please wait…\n")
            subprocess.check_call(["winget", "install", "--id", "oschwartz10612.Poppler", "-e", "--silent"])
            print("\nDone.\n")
        else:
            print(
                "Warning: Poppler (pdftoppm) not found — Slides Agent thumbnail and export "
                "features will be unavailable.\n"
                "  Install it from: https://poppler.freedesktop.org\n"
            )

    # Install Node.js dependencies if node_modules is missing or outdated.
    _npm = shutil.which("npm")
    if _npm and (_repo / "package.json").exists():
        _node_modules = _repo / "node_modules"
        _pkg_lock = _repo / "package-lock.json"
        _npm_marker = _node_modules / ".package-lock.json"
        _need_npm = (
            not _node_modules.exists()
            or not _npm_marker.exists()
            or (_pkg_lock.exists() and _pkg_lock.stat().st_mtime > _npm_marker.stat().st_mtime)
        )
        if _need_npm:
            print("Installing Node.js dependencies, please wait…\n")
            subprocess.check_call([_npm, "install"], cwd=str(_repo))
            print("\nDone.\n")

    # Download the OpenSwarm TUI binary from GitHub Releases if missing.
    _bin_name = "agency.exe" if sys.platform == "win32" else "agency"
    _bin_path = _repo / _bin_name
    if not _bin_path.exists():
        import urllib.request
        _bin_url = f"https://github.com/VRSEN/OpenSwarm/releases/latest/download/{_bin_name}"
        print("Downloading OpenSwarm TUI, please wait…\n")
        try:
            urllib.request.urlretrieve(_bin_url, str(_bin_path))
            if sys.platform != "win32":
                _bin_path.chmod(0o755)
            print("\nDone.\n")
        except Exception:
            print("Warning: Could not download OpenSwarm TUI. The terminal UI will use the default.\n")
# ─────────────────────────────────────────────────────────────────────────────


_OPTIONAL_INTEGRATIONS = [
    ("Composio (10,000+ external integrations)", ["COMPOSIO_API_KEY", "COMPOSIO_USER_ID"]),
    ("Anthropic / Claude models", ["ANTHROPIC_API_KEY"]),
    ("Search", ["SEARCH_API_KEY"]),
    ("Fal.ai (video & audio generation)", ["FAL_KEY"]),
    ("Google AI / Gemini", ["GOOGLE_API_KEY"]),
    ("Pexels (stock images)", ["PEXELS_API_KEY"]),
    ("Pixabay (stock images)", ["PIXABAY_API_KEY"]),
    ("Unsplash (stock images)", ["UNSPLASH_ACCESS_KEY"]),
]


def build_integration_summary() -> str:
    lines = ["Optional integrations:"]
    for name, keys in _OPTIONAL_INTEGRATIONS:
        active = [k for k in keys if os.getenv(k)]
        if active:
            lines.append(f"  ✓  {name}")
        else:
            lines.append(f"  ✗  {name}  (missing: {', '.join(keys)})")
    return "\n".join(lines)


def _configure_demo_console() -> None:
    """
    Terminal demo runs can stream stdout/stderr into a UI that expects structured output.
    Some third-party libs emit warnings that can corrupt that stream, so we suppress the
    known noisy ones here and apply the recommended Windows event-loop policy for pyzmq.
    """
    import warnings

    # By default, silence *all* console output for demo runs.
    # Opt out by setting OPENSWARM_DEMO_SILENCE_CONSOLE=0 / false / off.
    silence_env = os.getenv("OPENSWARM_DEMO_SILENCE_CONSOLE", "").strip().lower()
    silence_console = silence_env not in {"0", "false", "no", "off"}

    if silence_console:
        try:
            import logging
            devnull = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
            sys.stdout = devnull  # type: ignore[assignment]
            sys.stderr = devnull  # type: ignore[assignment]
            logging.disable(logging.CRITICAL)
        except Exception:
            pass
        return

    # Keep this opt-in so developers can still see warnings when needed.
    if os.getenv("OPENSWARM_DEMO_SHOW_WARNINGS", "").strip().lower() in {"1", "true", "yes", "on"}:
        return

    # pyzmq RuntimeWarning on Windows ProactorEventLoop (common with Python 3.8+ / 3.12)
    warnings.filterwarnings(
        "ignore",
        message=r".*Proactor event loop does not implement add_reader.*",
        category=RuntimeWarning,
    )

    # Pydantic v2 serializer warnings can be very noisy for streamed/typed objects.
    warnings.filterwarnings(
        "ignore",
        message=r"^Pydantic serializer warnings:.*",
        category=UserWarning,
    )

    # Prefer preventing the pyzmq warning entirely on Windows.
    if os.name == "nt":
        try:
            import asyncio
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass


def patch_terminal_title_binary() -> None:
    """
    Overwrite Agency Swarm's cached TUI executable with the repo-local `agency.exe`.

    The "AGENTSWARM" banner/title is rendered by that external executable, not by Python.
    """
    local_exe = Path(__file__).resolve().parent / "agency.exe"
    if not local_exe.exists():
        return

    try:
        from agency_swarm.ui.demos import agentswarm_cli as cli
        cached_exe = Path(cli._command()[0])
    except Exception:
        return

    try:
        cached_exe.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_exe, cached_exe)
    except Exception:
        return


def main() -> None:
    from dotenv import load_dotenv
    load_dotenv()

    if not os.getenv("AGENTSWARM_BIN"):
        _repo = Path(__file__).resolve().parent
        # Prefer locally built dev binary when present (third_party/agentswarm-cli build output).
        import platform as _platform
        _machine = _platform.machine().lower()
        _is_arm = _machine in ("aarch64", "arm64")
        if sys.platform == "win32":
            _os_name = "windows"
            _bin_name = "agentswarm.exe"
        elif sys.platform == "darwin":
            _os_name = "darwin"
            _bin_name = "agentswarm"
        else:
            _os_name = "linux"
            _bin_name = "agentswarm"
        # Try standard x64 first; fall back to baseline for older CPUs.
        if _is_arm:
            _arches = ["arm64"]
        else:
            _arches = ["x64", "x64-baseline"]
        _dev_exe = None
        for _arch in _arches:
            _candidate = _repo / f"third_party/agentswarm-cli/packages/opencode/dist/agentswarm-cli-{_os_name}-{_arch}/bin/{_bin_name}"
            if _candidate.exists():
                _dev_exe = _candidate
                break
        if _dev_exe is not None:
            os.environ["AGENTSWARM_BIN"] = str(_dev_exe)
        else:
            local_exe = _repo / "agency.exe"
            if local_exe.exists():
                os.environ["AGENTSWARM_BIN"] = str(local_exe)

    # Disable OpenAI Agents SDK tracing for terminal demo runs.
    try:
        from agents import set_tracing_disabled
        set_tracing_disabled(True)
    except Exception:
        pass

    from swarm import create_agency

    onboard_flag = Path(tempfile.gettempdir()) / "_openswarm_onboard.flag"
    os.environ["OPENSWARM_ONBOARD_FLAG"] = str(onboard_flag)
    onboard_flag.unlink(missing_ok=True)

    while True:
        import logging
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        logging.disable(logging.NOTSET)
        print("\nStarting OpenSwarm… this may take a few seconds.")
        _configure_demo_console()

        # Suppress OS-level stderr (fd 2) to prevent GLib/GIO UWP-app
        # warnings from appearing in the terminal during startup and TUI.
        _saved_stderr_fd = None
        try:
            _saved_stderr_fd = os.dup(2)
            _dn = os.open(os.devnull, os.O_WRONLY)
            os.dup2(_dn, 2)
            os.close(_dn)
        except OSError:
            pass

        print(build_integration_summary())
        print()

        agency = create_agency()
        agency.terminal_demo(reload=False)

        if _saved_stderr_fd is not None:
            try:
                os.dup2(_saved_stderr_fd, 2)
                os.close(_saved_stderr_fd)
            except OSError:
                pass

        if onboard_flag.exists():
            onboard_flag.unlink(missing_ok=True)
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__
            logging.disable(logging.NOTSET)
            print("\nLaunching setup wizard…")
            from onboard import run_onboarding
            run_onboarding()
            load_dotenv(override=True)
        else:
            break


if __name__ == "__main__":
    _bootstrap()
    main()
