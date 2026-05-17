"""Integration test for MiniMax provider via LiteLLM OpenAI-compatible API.

Requires MINIMAX_API_KEY to be set. Skipped automatically when the key is absent.
"""

from __future__ import annotations

import os

import pytest

# Load API key from ~/.env.local if present
try:
    from dotenv import load_dotenv
    from pathlib import Path
    _env_local = Path.home() / ".env.local"
    if _env_local.exists():
        load_dotenv(_env_local)
except ImportError:
    pass

_API_KEY = os.getenv("MINIMAX_API_KEY")

pytestmark = pytest.mark.skipif(not _API_KEY, reason="MINIMAX_API_KEY not set")


@pytest.mark.timeout(30)
def test_minimax_chat_completion():
    """Send a basic chat message via the MiniMax OpenAI-compatible API."""
    import httpx

    response = httpx.post(
        "https://api.minimax.io/v1/chat/completions",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_API_KEY}",
        },
        json={
            "model": "MiniMax-M2.7",
            "messages": [{"role": "user", "content": 'Say "test passed"'}],
            "max_tokens": 20,
            "temperature": 1.0,
        },
        timeout=30.0,
    )
    assert response.status_code == 200, f"API returned {response.status_code}: {response.text}"
    data = response.json()
    assert data["choices"][0]["message"]["content"], "Response content must not be empty"


@pytest.mark.timeout(30)
def test_minimax_streaming():
    """Verify streaming works via the MiniMax OpenAI-compatible API."""
    import httpx

    with httpx.stream(
        "POST",
        "https://api.minimax.io/v1/chat/completions",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_API_KEY}",
        },
        json={
            "model": "MiniMax-M2.7",
            "messages": [{"role": "user", "content": "Say hello"}],
            "max_tokens": 20,
            "temperature": 1.0,
            "stream": True,
        },
        timeout=30.0,
    ) as response:
        assert response.status_code == 200
        chunks = list(response.iter_lines())
        assert len(chunks) > 0, "Must receive at least one streaming chunk"
