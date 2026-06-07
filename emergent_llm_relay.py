"""OpenAI-compatible relay backed by the Emergent universal LLM key.

Mounted into the Odysseus FastAPI app so users get a ready-to-use LLM provider
out of the box without configuring an external API key.

Exposes (no /api prefix — Odysseus treats it like any other OpenAI-compatible
endpoint via the model_endpoints table):

  GET  /emergent-llm/v1/models              -> list available models
  POST /emergent-llm/v1/chat/completions    -> chat completion (SSE streaming
                                                or JSON, OpenAI shape)

Auth: this endpoint is mounted on a path that the Odysseus auth middleware
exempts by default? No — we add it to the exempt set in app.py so the model
discovery / chat layer can hit it without a session cookie.
"""
from __future__ import annotations

import json
import os
import time
import uuid
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/emergent-llm/v1", tags=["emergent-llm"])


# ---------------------------------------------------------------------------
# Model catalog. Kept short and current — see emergentintegrations playbook.
# (provider, model_id) tuples; model_id is the public OpenAI-style name we
# expose to Odysseus.
# ---------------------------------------------------------------------------
_MODELS: List[Dict[str, str]] = [
    {"id": "gpt-4o-mini",              "provider": "openai"},
    {"id": "gpt-4o",                   "provider": "openai"},
    {"id": "gpt-4.1-mini",             "provider": "openai"},
    {"id": "gpt-4.1",                  "provider": "openai"},
    {"id": "claude-sonnet-4-6",        "provider": "anthropic"},
    {"id": "claude-haiku-4-5-20251001","provider": "anthropic"},
    {"id": "gemini-3-flash-preview",   "provider": "gemini"},
    {"id": "gemini-3.1-pro-preview",   "provider": "gemini"},
]

_MODEL_INDEX = {m["id"]: m for m in _MODELS}


def _emergent_key() -> str:
    key = os.getenv("EMERGENT_LLM_KEY")
    if not key:
        raise HTTPException(
            status_code=503,
            detail="EMERGENT_LLM_KEY is not set on the server",
        )
    return key


class _Message(BaseModel):
    role: str
    content: Any  # str OR list[{type, text|image_url}] for vision; we coerce to text


class _ChatRequest(BaseModel):
    model: str
    messages: List[_Message]
    stream: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = Field(default=None, alias="max_tokens")

    class Config:
        populate_by_name = True
        extra = "allow"


def _flatten_content(content: Any) -> str:
    """Coerce OpenAI content (str or list of parts) to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text" and isinstance(part.get("text"), str):
                    parts.append(part["text"])
                # image_url / other parts are dropped — emergentintegrations.LlmChat
                # plain text path doesn't support inline vision here.
        return "\n".join(parts)
    return str(content or "")


def _split_messages(messages: List[_Message]) -> tuple[str, str]:
    """Pull out the system prompt and concatenate the rest into one user prompt.

    LlmChat is session-based and expects ONE user message per call. We don't
    persist sessions on the relay (Odysseus handles history itself), so we
    flatten the inbound conversation into a single prompt that preserves roles.
    """
    system_parts: List[str] = []
    convo_parts: List[str] = []
    for m in messages:
        text = _flatten_content(m.content).strip()
        if not text:
            continue
        if m.role == "system":
            system_parts.append(text)
        elif m.role == "assistant":
            convo_parts.append(f"Assistant: {text}")
        else:  # user / tool / function — treat as user-side context
            convo_parts.append(f"User: {text}")

    system_prompt = "\n\n".join(system_parts) or "You are a helpful assistant."
    # If only one user turn and no assistant turns, send it verbatim — keeps the
    # prompt clean for single-shot questions (the common case from Odysseus).
    if len(convo_parts) == 1 and convo_parts[0].startswith("User: "):
        user_prompt = convo_parts[0][len("User: "):]
    else:
        user_prompt = "\n\n".join(convo_parts) or ""
    return system_prompt, user_prompt


@router.get("/models")
async def list_models() -> Dict[str, Any]:
    now = int(time.time())
    return {
        "object": "list",
        "data": [
            {
                "id": m["id"],
                "object": "model",
                "created": now,
                "owned_by": f"emergent/{m['provider']}",
            }
            for m in _MODELS
        ],
    }


def _resolve_model(model_id: str) -> Dict[str, str]:
    if model_id in _MODEL_INDEX:
        return _MODEL_INDEX[model_id]
    # Soft-match by suffix so common variants still resolve
    for m in _MODELS:
        if model_id.endswith(m["id"]) or m["id"].endswith(model_id):
            return m
    raise HTTPException(
        status_code=404,
        detail=f"Unknown model '{model_id}'. See GET /emergent-llm/v1/models.",
    )


def _build_chat(model_id: str, session_id: str, system_prompt: str):
    # Lazy import so a missing emergentintegrations install doesn't break boot
    from emergentintegrations.llm.chat import LlmChat  # type: ignore

    model = _resolve_model(model_id)
    chat = LlmChat(
        api_key=_emergent_key(),
        session_id=session_id,
        system_message=system_prompt,
    ).with_model(model["provider"], model["id"])
    return chat, model


@router.post("/chat/completions")
async def chat_completions(req: Request) -> Any:
    try:
        payload = await req.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    try:
        parsed = _ChatRequest.model_validate(payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid request: {e}")

    system_prompt, user_prompt = _split_messages(parsed.messages)
    if not user_prompt.strip():
        raise HTTPException(status_code=400, detail="No user message provided")

    session_id = f"odysseus-relay-{uuid.uuid4().hex[:12]}"
    chat, model = _build_chat(parsed.model, session_id, system_prompt)

    from emergentintegrations.llm.chat import (  # type: ignore
        UserMessage, TextDelta, StreamDone,
    )

    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())
    user_message = UserMessage(text=user_prompt)

    if not parsed.stream:
        # Aggregate the stream into a single JSON response.
        chunks: List[str] = []
        try:
            async for ev in chat.stream_message(user_message):
                if isinstance(ev, TextDelta):
                    chunks.append(ev.content or "")
                elif isinstance(ev, StreamDone):
                    break
        except Exception as e:
            logger.exception("emergent-llm chat failed")
            raise HTTPException(status_code=502, detail=f"LLM error: {e}")

        text = "".join(chunks)
        return {
            "id": completion_id,
            "object": "chat.completion",
            "created": created,
            "model": model["id"],
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    # Streaming response — OpenAI SSE shape.
    async def event_stream():
        try:
            first = True
            async for ev in chat.stream_message(user_message):
                if isinstance(ev, TextDelta):
                    delta: Dict[str, Any] = {"content": ev.content or ""}
                    if first:
                        delta["role"] = "assistant"
                        first = False
                    chunk = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model["id"],
                        "choices": [
                            {"index": 0, "delta": delta, "finish_reason": None}
                        ],
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"
                elif isinstance(ev, StreamDone):
                    break
            done = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model["id"],
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
            yield f"data: {json.dumps(done)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.exception("emergent-llm stream failed")
            err = {"error": {"message": str(e), "type": "upstream_error"}}
            yield f"data: {json.dumps(err)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
