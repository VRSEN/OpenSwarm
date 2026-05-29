import os
import sys
import subprocess
import shutil
import tempfile
from pathlib import Path

_PRODUCT_TUI_LOGO_LEFT = (
    '["                                    ",'
    '" ██████╗ ██████╗ ███████╗███╗   ██╗",'
    '"██╔═══██╗██╔══██╗██╔════╝████╗  ██║",'
    '"██║   ██║██████╔╝█████╗  ██╔██╗ ██║",'
    '"██║   ██║██╔═══╝ ██╔══╝  ██║╚██╗██║",'
    '"╚██████╔╝██║     ███████╗██║ ╚████║",'
    '" ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═══╝"]'
)
_PRODUCT_TUI_LOGO_RIGHT = (
    '["",'
    '"███████╗██╗    ██╗ █████╗ ██████╗ ███╗   ███╗",'
    '"██╔════╝██║    ██║██╔══██╗██╔══██╗████╗ ████║",'
    '"███████╗██║ █╗ ██║███████║██████╔╝██╔████╔██║",'
    '"╚════██║██║███╗██║██╔══██║██╔══██╗██║╚██╔╝██║",'
    '"███████║╚███╔███╔╝██║  ██║██║  ██║██║ ╚═╝ ██║",'
    '"╚══════╝ ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝"]'
)
_PRODUCT_WORDMARK_LINES = (
    '["",'
    '" ██████╗ ██████╗ ███████╗███╗   ██╗ ███████╗██╗    ██╗ █████╗ ██████╗ ███╗   ███╗",'
    '"██╔═══██╗██╔══██╗██╔════╝████╗  ██║ ██╔════╝██║    ██║██╔══██╗██╔══██╗████╗ ████║",'
    '"██║   ██║██████╔╝█████╗  ██╔██╗ ██║ ███████╗██║ █╗ ██║███████║██████╔╝██╔████╔██║",'
    '"██║   ██║██╔═══╝ ██╔══╝  ██║╚██╗██║ ╚════██║██║███╗██║██╔══██╗██╔══██╗██║╚██╔╝██║",'
    '"╚██████╔╝██║     ███████╗██║ ╚████║ ███████║╚███╔███╔╝██║  ██║██║  ██║██║ ╚═╝ ██║",'
    '" ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═══╝ ╚══════╝ ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝"]'
)
_PRODUCT_ADDONS = (
    '[{"id":"search","title":"Web Search","keys":["SEARCH_API_KEY"]},'
    '{"id":"anthropic","title":"Anthropic Claude","keys":["ANTHROPIC_API_KEY"],"excludeProviders":["anthropic"]},'
    '{"id":"composio","title":"Composio","keys":["COMPOSIO_API_KEY","COMPOSIO_USER_ID"]},'
    '{"id":"google","title":"Google Gemini","keys":["GOOGLE_API_KEY"],"excludeProviders":["google"]},'
    '{"id":"fal","title":"Fal.ai","keys":["FAL_KEY"]},'
    '{"id":"pexels","title":"Pexels","keys":["PEXELS_API_KEY"]},'
    '{"id":"pixabay","title":"Pixabay","keys":["PIXABAY_API_KEY"]},'
    '{"id":"unsplash","title":"Unsplash","keys":["UNSPLASH_ACCESS_KEY"]}]'
)


def _openswarm_state_root() -> Path:
    override = os.getenv("OPENSWARM_STATE_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "win32":
        return Path(os.getenv("APPDATA") or (Path.home() / "AppData" / "Roaming")) / "OpenSwarm"
    return Path.home() / ".openswarm"


def _load_openswarm_dotenv(*, override: bool = False) -> bool:
    from dotenv import load_dotenv
    return bool(load_dotenv(dotenv_path=_openswarm_state_root() / ".env", override=override))


def _configure_product_env() -> None:
    os.environ.setdefault("AGENTSWARM_PRODUCT_SKIP_POST_AUTH_MODEL_SELECTION", "true")
    os.environ.setdefault("AGENTSWARM_PRODUCT_TUI_LOGO_LEFT", _PRODUCT_TUI_LOGO_LEFT)
    os.environ.setdefault("AGENTSWARM_PRODUCT_TUI_LOGO_RIGHT", _PRODUCT_TUI_LOGO_RIGHT)
    os.environ.setdefault("AGENTSWARM_PRODUCT_WORDMARK_LINES", _PRODUCT_WORDMARK_LINES)
    os.environ.setdefault("AGENTSWARM_PRODUCT_ADDONS", _PRODUCT_ADDONS)
    os.environ["AGENTSWARM_PRODUCT_STATE_ROOT"] = str(_openswarm_state_root())


def _preload_agentswarm_bin(repo: Path | None = None) -> None:
    # Bootstrap may install python-dotenv, so preserve this one override with stdlib.
    if "AGENTSWARM_BIN" in os.environ:
        return

    roots = [_openswarm_state_root()]
    seen: set[Path] = set()

    for root in roots:
        if root is None:
            continue
        path = root.resolve() / ".env"
        if path in seen:
            continue
        seen.add(path)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue

        for line in lines:
            value = line.strip()
            if not value or value.startswith("#"):
                continue
            if value.startswith("export "):
                value = value.removeprefix("export ").lstrip()

            key, sep, raw = value.partition("=")
            if sep != "=" or key.strip() != "AGENTSWARM_BIN":
                continue

            raw = raw.strip()
            if raw[:1] in {"'", '"'}:
                quote = raw[0]
                end = raw.find(quote, 1)
                raw = raw[1:end] if end != -1 else raw[1:]
            else:
                raw = raw.split(" #", 1)[0].strip()
            os.environ["AGENTSWARM_BIN"] = raw
            return


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


def _resolve_bin_names() -> list[str]:
    name = _resolve_bin_name()
    names = [name]
    stem, suffix = (name[:-4], ".exe") if name.endswith(".exe") else (name, "")
    if stem.endswith("-x64"):
        names.append(f"{stem}-baseline{suffix}")
    return names


def _is_tui_binary_runnable(path: Path) -> bool:
    try:
        stat = path.stat()
        if not stat.st_size:
            return False
        if sys.platform != "win32" and not os.access(path, os.X_OK):
            path.chmod(0o755)
        result = subprocess.run(
            [str(path), "--version"],
            env={**os.environ, "AGENTSWARM_LAUNCHER": "0"},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
        )
    except Exception:
        return False
    return result.returncode == 0


def _download_tui_binary(repo: Path, name: str) -> Path | None:
    import urllib.request

    path = repo / name
    url = f"https://github.com/VRSEN/OpenSwarm/releases/latest/download/{name}"
    print("Downloading OpenSwarm TUI, please wait…\n")
    try:
        urllib.request.urlretrieve(url, str(path))
        if sys.platform != "win32":
            path.chmod(0o755)
        print("\nDone.\n")
    except Exception:
        path.unlink(missing_ok=True)
        return None
    return path


def _resolve_tui_binary(repo: Path, download: bool) -> Path | None:
    for name in _resolve_bin_names():
        path = repo / name
        if not path.exists() and download:
            path = _download_tui_binary(repo, name) or path
        if path.exists() and _is_tui_binary_runnable(path):
            return path
    return None


_REQUIRED_SLIDES_NODE_PACKAGES = (
    "dom-to-pptx",
    "playwright",
    "pptxgenjs",
    "react",
    "react-dom",
    "react-icons",
    "sharp",
)


def _warn_slides_setup(message: str) -> None:
    print(
        f"Warning: {message}\n"
        "  OpenSwarm will continue, but Slides Agent export features may be unavailable.\n"
    )


def _run_optional_node_command(
    cmd: list[str],
    repo: Path,
    label: str,
    env: dict[str, str] | None = None,
) -> bool:
    try:
        result = subprocess.run(cmd, cwd=str(repo), env=env)
    except Exception as exc:
        _warn_slides_setup(f"{label} failed: {exc}")
        return False
    if result.returncode != 0:
        _warn_slides_setup(f"{label} exited with code {result.returncode}")
        return False
    return True


def _ensure_node_playwright_browsers(repo: Path) -> bool:
    """Install Node Playwright browsers where the HTML-to-PPTX runner looks for them."""
    npx = shutil.which("npx")
    if not npx:
        _warn_slides_setup(
            "npm is available but npx was not found; cannot install Node Playwright browsers"
        )
        return False

    env = os.environ.copy()
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(repo / ".playwright-browsers")
    return _run_optional_node_command(
        [npx, "-y", "playwright", "install", "chromium", "chromium-headless-shell"],
        repo,
        "Node Playwright browser install",
        env=env,
    )


def _ensure_node_dependencies(repo: Path, npm: str) -> bool:
    _node_modules = repo / "node_modules"
    _pkg_lock = repo / "package-lock.json"
    _npm_marker = _node_modules / ".package-lock.json"
    _need_npm = (
        not _node_modules.exists()
        or not _npm_marker.exists()
        or (_pkg_lock.exists() and _pkg_lock.stat().st_mtime > _npm_marker.stat().st_mtime)
        or any(not (_node_modules / name).exists() for name in _REQUIRED_SLIDES_NODE_PACKAGES)
    )
    _npm_ok = True
    if _need_npm:
        print("Installing Node.js dependencies, please wait…\n")
        _npm_ok = _run_optional_node_command(
            [npm, "install", "--legacy-peer-deps"],
            repo,
            "Node.js dependency install",
        )
        if _npm_ok:
            print("\nDone.\n")
    _browsers_ok = _ensure_node_playwright_browsers(repo)
    return _npm_ok and _browsers_ok


def _uv_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("UV_LINK_MODE", "copy")
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


# ── Bootstrap: create venv + install deps automatically on first run ─────────
# Only stdlib imports above. _bootstrap() is called explicitly — either from
# swarm.py (via `from run_utils import _bootstrap; _bootstrap()`) or from the
# __main__ guard below — never at module level, so `from run_utils import _bootstrap`
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
        subprocess.check_call(uv_cmd, env=_uv_env())
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

    # Install Node.js dependencies if node_modules is missing, incomplete, or outdated.
    _npm = shutil.which("npm")
    if _npm and (_repo / "package.json").exists():
        _ensure_node_dependencies(_repo, _npm)
    elif (_repo / "package.json").exists():
        _warn_slides_setup(
            "npm was not found; cannot install Slides Agent Node.js dependencies"
        )

    # Download the OpenSwarm TUI binary from GitHub Releases if missing.
    if not os.getenv("AGENTSWARM_BIN"):
        _bin_path = _resolve_tui_binary(_repo, download=True)
        if _bin_path:
            os.environ["AGENTSWARM_BIN"] = str(_bin_path)
        else:
            print("Warning: Could not download a runnable OpenSwarm TUI. The terminal UI will use the default.\n")
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
    _preload_agentswarm_bin()
    _bootstrap()

    _load_openswarm_dotenv()

    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    _configure_product_env()

    if not os.getenv("AGENTSWARM_BIN"):
        _repo = Path(__file__).resolve().parent
        local_exe = _resolve_tui_binary(_repo, download=True)
        if local_exe:
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
            _load_openswarm_dotenv(override=True)
        else:
            break


if __name__ == "__main__":
    main()
