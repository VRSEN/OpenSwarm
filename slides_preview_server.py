"""Lightweight live-preview server for slides_agent HTML files.

Architecture
------------
* FastAPI server in a background daemon thread.
* ModifySlide calls _ensure_server() + open_browser_once() via asyncio.to_thread()
  before streaming starts, so the browser is already open when the first delta arrives.
* push_slide_delta() / push_slide_complete() forward events through a thread-safe hub
  to all connected SSE clients.
* watchfiles provides a fallback for slides written outside ModifySlide (e.g. blank
  placeholders from InsertNewSlides).
"""

from __future__ import annotations

import asyncio
import json
import queue as _queue
import re
import socket
import threading
import urllib.request
import webbrowser
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse

_TEMPLATES = Path(__file__).parent / "templates"

def _tmpl(name: str) -> str:
    return (_TEMPLATES / name).read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# Thread-safe pub/sub hub
# ---------------------------------------------------------------------------

class _SlideStreamHub:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._queues: list[_queue.Queue] = []

    def subscribe(self) -> _queue.Queue:
        q: _queue.Queue = _queue.Queue(maxsize=2000)
        with self._lock:
            self._queues.append(q)
        return q

    def unsubscribe(self, q: _queue.Queue) -> None:
        with self._lock:
            try:
                self._queues.remove(q)
            except ValueError:
                pass

    def publish(self, event: dict) -> None:
        with self._lock:
            queues = list(self._queues)
        for q in queues:
            try:
                q.put_nowait(event)
            except _queue.Full:
                pass


_hub = _SlideStreamHub()
_server_url: str | None = None
_server_lock = threading.Lock()

# Server-side streaming buffer — stores partial HTML per slide while generating
_live_buffers: dict[str, str] = {}
_live_buffers_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Public API called by ModifySlide
# ---------------------------------------------------------------------------

def _ensure_server() -> str | None:
    """Start the preview server if not already running. Thread-safe. Returns URL or None."""
    global _server_url
    with _server_lock:
        if _server_url is None:
            start_preview_server()
    return _server_url


_browser_lock = threading.Lock()
_browser_last_open: float = 0.0  # monotonic timestamp of last webbrowser.open call


def open_browser_once(url: str | None = None) -> None:
    """Open the browser unless a tab is already connected or was opened recently.

    The 5-second recency guard prevents parallel ModifySlide calls from each
    opening a tab before any of them has had time to connect via SSE.
    """
    import time
    target = url or _server_url
    if not target:
        return
    now = time.monotonic()
    with _browser_lock:
        with _hub._lock:
            tab_open = len(_hub._queues) > 0
        if tab_open:
            return
        global _browser_last_open
        if now - _browser_last_open < 5.0:
            return
        _browser_last_open = now
    webbrowser.open(target)


def push_slide_delta(*, rel_path: str, name: str, delta: str) -> None:
    """Forward one streaming HTML token to all connected preview clients."""
    with _live_buffers_lock:
        _live_buffers[rel_path] = _live_buffers.get(rel_path, "") + delta
    _hub.publish({"type": "slide_delta", "rel_path": rel_path, "name": name, "delta": delta})


def push_slide_complete(*, rel_path: str, name: str) -> None:
    """Signal that the slide file has been fully written to disk."""
    with _live_buffers_lock:
        _live_buffers.pop(rel_path, None)
    _hub.publish({"type": "slide_complete", "rel_path": rel_path, "name": name})



app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


def _mnt_dir() -> Path:
    from slides_agent.tools.slide_file_utils import get_mnt_dir
    return get_mnt_dir()


@app.get("/")
async def preview_page() -> HTMLResponse:
    return HTMLResponse(_tmpl("preview.html"))


@app.get("/api/slides")
async def list_slides() -> list[dict]:
    mnt = _mnt_dir()
    slides: list[dict] = []
    if not mnt.exists():
        return slides

    # Group slide files by their presentations/ directory
    project_dirs: dict[Path, list[Path]] = {}
    for html_file in mnt.rglob("slide_*.html"):
        pdir = html_file.parent
        project_dirs.setdefault(pdir, []).append(html_file)

    # Sort projects by creation time — newest first (st_ctime = creation time on Windows)
    sorted_dirs = sorted(project_dirs, key=lambda p: p.stat().st_ctime, reverse=True)

    for pdir in sorted_dirs:
        for html_file in sorted(project_dirs[pdir], key=lambda p: p.name):
            try:
                rel = html_file.relative_to(mnt)
                slides.append({"name": html_file.name, "rel_path": str(rel).replace("\\", "/")})
            except ValueError:
                pass
    return slides


@app.get("/files/{path:path}")
async def serve_file(path: str) -> FileResponse:
    mnt = _mnt_dir()
    file_path = (mnt / path).resolve()
    try:
        file_path.relative_to(mnt.resolve())
    except ValueError:
        raise HTTPException(status_code=403)
    if not file_path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(file_path)


@app.get("/project/{name}")
async def project_page(name: str) -> HTMLResponse:
    return HTMLResponse(_tmpl("project.html").replace("__PROJECT_NAME__", name))


@app.get("/view/{path:path}")
async def view_slide(path: str) -> HTMLResponse:
    rel_path = path.replace("\\", "/")
    return HTMLResponse(_tmpl("viewer.html").replace("__REL_PATH__", rel_path))


@app.get("/api/buffer/{path:path}")
async def get_buffer(path: str) -> HTMLResponse:
    rel_path = path.replace("\\", "/").split("?")[0]  # strip cache-buster if any
    with _live_buffers_lock:
        content = _live_buffers.get(rel_path)
    if content:
        return HTMLResponse(content)
    return HTMLResponse("", status_code=204)  # 204 = not currently streaming


@app.get("/api/events")
async def sse_events(request: Request) -> StreamingResponse:
    async def _generator():
        yield f"data: {json.dumps({'type': 'connected'})}\n\n"

        mnt = _mnt_dir()
        mnt.mkdir(parents=True, exist_ok=True)

        hub_q = _hub.subscribe()
        aio_q: asyncio.Queue = asyncio.Queue()

        async def _watch_fs() -> None:
            from watchfiles import awatch
            try:
                async for changes in awatch(str(mnt)):
                    for _, path_str in changes:
                        path = Path(path_str)
                        if path.suffix == ".html" and re.search(r"slide_\d+", path.name, re.IGNORECASE):
                            try:
                                rel = path.relative_to(mnt)
                                await aio_q.put({
                                    "type": "slide_changed",
                                    "rel_path": str(rel).replace("\\", "/"),
                                    "name": path.name,
                                })
                            except ValueError:
                                pass
            except asyncio.CancelledError:
                pass

        fs_task = asyncio.create_task(_watch_fs())

        try:
            while True:
                # Drain hub queue (streaming deltas — highest priority)
                while True:
                    try:
                        yield f"data: {json.dumps(hub_q.get_nowait())}\n\n"
                    except _queue.Empty:
                        break

                # Wait briefly for a filesystem event
                try:
                    event = await asyncio.wait_for(aio_q.get(), timeout=0.05)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    pass

                if await request.is_disconnected():
                    break
        except asyncio.CancelledError:
            pass
        finally:
            fs_task.cancel()
            _hub.unsubscribe(hub_q)

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Server startup
# ---------------------------------------------------------------------------

def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def start_preview_server() -> int | None:
    """Start the server in a background daemon thread. Returns port or None on failure."""
    global _server_url
    try:
        import uvicorn
        import time

        port = _find_free_port()

        def _run() -> None:
            uvicorn.run(app, host="127.0.0.1", port=port, log_level="error")

        threading.Thread(target=_run, daemon=True, name="slides-preview").start()

        url = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            try:
                urllib.request.urlopen(url, timeout=0.3)
                break
            except Exception:
                time.sleep(0.1)

        _server_url = url
        print(f"\n  Slides preview: {url}\n")
        return port

    except Exception as exc:
        print(f"\n  [slides-preview] Failed to start: {exc}\n")
        return None


if __name__ == "__main__":
    import time
    start_preview_server()
    open_browser_once()
    print("  Press Ctrl+C to stop.\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
