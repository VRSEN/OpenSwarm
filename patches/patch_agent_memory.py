"""
Patch: inject architect memory (dossier + persisted chat) into agency get_response calls.
"""

from __future__ import annotations

_PATCH_APPLIED = False


def apply_agent_memory_patch() -> None:
    global _PATCH_APPLIED
    if _PATCH_APPLIED:
        return
    _PATCH_APPLIED = True
    _patch_response_endpoint()


def _extract_user_id(request) -> str:
    ctx = getattr(request, "user_context", None) or {}
    if isinstance(ctx, dict):
        uid = ctx.get("user_id")
        if uid:
            return str(uid)
    return "default"


def _patch_response_endpoint() -> None:
    from fastapi import Depends

    from agency_swarm.integrations.fastapi_utils import endpoint_handlers as eh

    from backend.database import SessionLocal
    from backend.services.memory_service import (
        build_architect_dossier,
        format_dossier_for_instructions,
        get_chat_history,
        merge_chat_history,
        save_chat_history,
    )

    original_make = eh.make_response_endpoint

    def patched_make_response_endpoint(request_model, agency_factory, verify_token, allowed_local_dirs=None):
        original_handler = original_make(request_model, agency_factory, verify_token, allowed_local_dirs)

        async def handler(request: request_model, token: str = Depends(verify_token)):
            user_id = _extract_user_id(request)
            db = SessionLocal()
            try:
                dossier = build_architect_dossier(db, user_id)
                stored_chat = get_chat_history(db, user_id)

                merged_context = {**(request.user_context or {}), **dossier}
                memory_block = format_dossier_for_instructions(dossier)
                existing_instr = getattr(request, "additional_instructions", None) or ""
                combined_instr = f"{memory_block}\n\n{existing_instr}".strip()

                chat_for_run = request.chat_history
                if not chat_for_run and stored_chat:
                    chat_for_run = stored_chat

                request = request.model_copy(
                    update={
                        "user_context": merged_context,
                        "additional_instructions": combined_instr,
                        "chat_history": chat_for_run,
                    }
                )
            finally:
                db.close()

            result = await original_handler(request, token)

            if isinstance(result, dict) and "error" not in result:
                db = SessionLocal()
                try:
                    prior = get_chat_history(db, user_id)
                    new_msgs = result.get("new_messages") or []
                    merged = merge_chat_history(prior, new_msgs)
                    saved = save_chat_history(db, user_id, merged)
                    result["chat_history"] = saved
                finally:
                    db.close()

            return result

        return handler

    eh.make_response_endpoint = patched_make_response_endpoint
