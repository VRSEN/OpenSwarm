import os
import sys
import subprocess
import shutil
import tempfile
from pathlib import Path

def _resolve_bin_name() -> str:
    """Return the platform+arch-specific TUI binary filename."""
    import platform
    machine = platform.machine().lower()
    arch = "arm64" if machine in ("arm64", "aarch64") else "x64"
    if sys.platform == "win32":
        return f"agentswarm-windows-{arch}.exe"
    if sys.platform == "darwin":
        return f"agentswarm-darwin-{arch}"
    return f"agentswarm-linux-{arch}"


# ── Bootstrap: create venv + install deps automatically on first run ─────────
# Only stdlib imports above. _bootstrap() is called explicitly — either from
# swarm.py (via `from run import _bootstrap; _bootstrap()`) or from the
# __main__ guard below — never at module level, so `from run import _bootstrap`
# is safe to call from outside the venv.
def _bootstrap() -> None:
    _repo = Path(__file__).resolve().parent
    # Ensure deps are present.
    try:
        import dotenv        # noqa: F401
        import rich          # noqa: F401
        import questionary   # noqa: F401
        import agency_swarm  # noqa: F401
    except ImportError:
        print("Installing dependencies, please wait…\n")
        if not shutil.which("uv"):
            subprocess.check_call([sys.executable, "-m", "pip", "install", "uv"])
        uv_cmd = ["uv", "pip", "install", "--system", "--python", sys.executable, str(_repo)]
        if sys.platform != "win32":
            uv_cmd.append("--break-system-packages")
        subprocess.check_call(uv_cmd)
        print("\nDone.\n")

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

    # Use a bundled OpenSwarm TUI binary when it is already present.
    _bin_name = _resolve_bin_name()
    _bin_path = _repo / _bin_name
    if _bin_path.exists() and sys.platform != "win32":
        try:
            _bin_path.chmod(0o755)
        except Exception:
            pass
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


def main() -> None:
    from dotenv import load_dotenv
    load_dotenv()

    if not os.getenv("AGENTSWARM_BIN"):
        _repo = Path(__file__).resolve().parent
        local_exe = _repo / _resolve_bin_name()
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
        agency.tui(show_reasoning=True, reload=False)

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
