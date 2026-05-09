"""
Patch: inject attachment file references into the user message.
"""

import asyncio

_PATCH_APPLIED = False


def apply_file_attachment_reference_patch() -> None:
    global _PATCH_APPLIED
    if _PATCH_APPLIED:
        return
    _PATCH_APPLIED = True
    _patch_endpoint_handler_factories()


def _build_attachment_note(file_urls: dict[str, str]) -> str:
    lines = [
        "\n\n[SYSTEM NOTE] The user attached the following files.",
        "Use ONLY the URLs below as file references in your tools (e.g. as `input_image_ref`).",
        "Any /mnt/data/ paths you see are internal OpenAI server paths — they are NOT real local paths and must NOT be used or shown to the user:",
    ]
    for filename, ref in file_urls.items():
        lines.append(f"  - {filename}: {ref}")
    return "\n".join(lines)


def _patch_endpoint_handler_factories() -> None:
    from fastapi import Depends
    from fastapi import Request as FastAPIRequest
    from agency_swarm.integrations.fastapi_utils import endpoint_handlers as eh

    _original_make_response = eh.make_response_endpoint
    _original_make_stream = eh.make_stream_endpoint
    _original_make_agui = eh.make_agui_chat_endpoint

    def patched_make_response_endpoint(request_model, agency_factory, verify_token, allowed_local_dirs=None):
        original_handler = _original_make_response(request_model, agency_factory, verify_token, allowed_local_dirs)

        async def handler(request: request_model, token: str = Depends(verify_token)):
            if getattr(request, "file_urls", None):
                note = _build_attachment_note(request.file_urls)
                existing = getattr(request, "additional_instructions", None) or ""
                request = request.model_copy(update={"additional_instructions": (existing + "\n\n" + note).strip()})
            return await original_handler(request, token)

        return handler

    def patched_make_stream_endpoint(request_model, agency_factory, verify_token, run_registry, allowed_local_dirs=None):
        original_handler = _original_make_stream(request_model, agency_factory, verify_token, run_registry, allowed_local_dirs)

        async def handler(http_request: FastAPIRequest, request: request_model, token: str = Depends(verify_token)):
            if getattr(request, "file_urls", None):
                note = _build_attachment_note(request.file_urls)
                existing = getattr(request, "additional_instructions", None) or ""
                request = request.model_copy(update={"additional_instructions": (existing + "\n\n" + note).strip()})
            response = await original_handler(http_request, request, token)
            # Disabled custom SSE body_iterator wrapping because it can interfere
            # with downstream event consumption and may surface duplicated text in
            # the client UI. Keep the original response stream untouched.
            return response

        return handler

    def patched_make_agui_endpoint(request_model, agency_factory, verify_token, allowed_local_dirs=None):
        original_handler = _original_make_agui(request_model, agency_factory, verify_token, allowed_local_dirs)

        async def handler(request: request_model, token: str = Depends(verify_token)):
            if getattr(request, "file_urls", None):
                note = _build_attachment_note(request.file_urls)
                existing = getattr(request, "additional_instructions", None) or ""
                request = request.model_copy(update={"additional_instructions": (existing + "\n\n" + note).strip()})
            return await original_handler(request, token)

        return handler

    eh.make_response_endpoint = patched_make_response_endpoint
    eh.make_stream_endpoint = patched_make_stream_endpoint
    eh.make_agui_chat_endpoint = patched_make_agui_endpoint


async def _with_sse_heartbeats(body_iterator, interval_seconds: float = 10.0):
    queue: asyncio.Queue = asyncio.Queue()
    sentinel = object()

    async def produce() -> None:
        try:
            async for chunk in body_iterator:
                await queue.put(chunk)
        except BaseException as exc:
            await queue.put(exc)
        finally:
            await queue.put(sentinel)

    producer = asyncio.create_task(produce())
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=interval_seconds)
            except TimeoutError:
                yield b": openswarm heartbeat\n\n"
                continue
            if item is sentinel:
                break
            if isinstance(item, BaseException):
                raise item
            yield item
    finally:
        if not producer.done():
            producer.cancel()
            try:
                await producer
            except asyncio.CancelledError:
                pass
