"""Offline request-boundary checks using the repository's actual SDK dependencies."""

import asyncio
import json
from unittest.mock import AsyncMock
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from agency_swarm import ModelSettings, ModelTracing


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    for key in (
        "DEFAULT_MODEL",
        "MINIMAX_REGION",
        "MINIMAX_API_BASE",
        "MINIMAX_ANTHROPIC_BASE",
        "MINIMAX_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("MINIMAX_API_KEY", "offline-placeholder")


@pytest.mark.parametrize(
    "region,host", [("global", "api.minimax.io"), ("cn", "api.minimaxi.com")]
)
@pytest.mark.parametrize("provider", ["minimax", "anthropic"])
@pytest.mark.parametrize(
    "model_id", ["MiniMax-M3.1-Flash", "MiniMax-M3", "MiniMax-M2.7"]
)
@pytest.mark.parametrize("custom", [False, True])
def test_default_model_serializes_at_http_boundary(
    monkeypatch, region, host, provider, model_id, custom
):
    monkeypatch.setenv("DEFAULT_MODEL", f"litellm/{provider}/{model_id}")
    monkeypatch.setenv("MINIMAX_REGION", region)
    if custom:
        key = (
            "MINIMAX_ANTHROPIC_BASE" if provider == "anthropic" else "MINIMAX_API_BASE"
        )
        monkeypatch.setenv(
            key,
            (
                "https://proxy.example/anthropic"
                if provider == "anthropic"
                else "https://proxy.example/v1"
            ),
        )
        host = "proxy.example"
    requests = []

    async def send(client, request, **kwargs):
        requests.append(request)
        if provider == "anthropic":
            body = {
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": model_id,
                "content": [{"type": "text", "text": "ok"}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 2, "output_tokens": 1},
            }
        else:
            body = {
                "id": "chat_test",
                "object": "chat.completion",
                "created": 1,
                "model": model_id,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 2,
                    "completion_tokens": 1,
                    "total_tokens": 3,
                },
            }
        return httpx.Response(200, json=body, request=request)

    def reject_sync(*args, **kwargs):
        raise AssertionError("Unexpected synchronous HTTP request")

    monkeypatch.setattr(httpx.AsyncClient, "send", send)
    monkeypatch.setattr(httpx.Client, "send", reject_sync)
    model = config.get_default_model()
    assert model.model == f"{provider}/{model_id}"
    assert not config.is_openai_provider()
    response = asyncio.run(
        model.get_response(
            system_instructions="Answer briefly.",
            input="Hello",
            model_settings=ModelSettings(),
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=ModelTracing.DISABLED,
        )
    )
    assert response.output
    assert len(requests) == 1
    request = requests[0]
    assert request.url.host == host
    assert request.url.path == (
        "/anthropic/v1/messages" if provider == "anthropic" else "/v1/chat/completions"
    )
    body = json.loads(request.content)
    assert body["model"] == model_id
    assert body["messages"][-1]["content"] == (
        [{"type": "text", "text": "Hello"}] if provider == "anthropic" else "Hello"
    )
    assert "service_tier" not in body
    assert "reasoning_split" not in body
    assert body.get("thinking", {}).get("type") != "disabled"
    assert body.get("reasoning_effort") != "none"
    assert "offline-placeholder" in str(dict(request.headers))


@pytest.mark.parametrize("provider", ["minimax", "anthropic"])
def test_sdk_preserves_image_and_tool_history(monkeypatch, provider):
    import litellm

    monkeypatch.setenv("DEFAULT_MODEL", f"{provider}/MiniMax-M3.1-Flash")
    completion = AsyncMock(
        return_value=litellm.ModelResponse(
            model="MiniMax-M3.1-Flash",
            choices=[
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "ok"},
                    "finish_reason": "stop",
                }
            ],
            usage={"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
        )
    )
    monkeypatch.setattr(litellm, "acompletion", completion)
    history = [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": "Inspect this image."},
                {
                    "type": "input_image",
                    "image_url": "https://example.test/image.png",
                    "detail": "auto",
                },
            ],
        },
        {
            "type": "function_call",
            "call_id": "call_test",
            "name": "inspect",
            "arguments": "{}",
        },
        {
            "type": "function_call_output",
            "call_id": "call_test",
            "output": "Image inspected.",
        },
    ]
    asyncio.run(
        config.get_default_model().get_response(
            system_instructions=None,
            input=history,
            model_settings=ModelSettings(),
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=ModelTracing.DISABLED,
        )
    )
    payload = completion.call_args.kwargs
    assert payload["model"] == f"{provider}/MiniMax-M3.1-Flash"
    assert payload["reasoning_effort"] is None
    messages = payload["messages"]
    assert (
        messages[0]["content"][1]["image_url"]["url"]
        == "https://example.test/image.png"
    )
    assert messages[1]["tool_calls"][0]["id"] == "call_test"
    assert messages[2] == {
        "role": "tool",
        "tool_call_id": "call_test",
        "content": "Image inspected.",
    }
