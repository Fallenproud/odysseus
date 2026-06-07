"""Seed a ModelEndpoint row pointing at the in-process Emergent LLM relay.

Idempotent — safe to re-run. Run once at boot from server.py.
"""
from __future__ import annotations

import json
import logging
import uuid

logger = logging.getLogger(__name__)

ENDPOINT_ID = "emergent-llm-builtin"
ENDPOINT_NAME = "Emergent LLM (built-in)"
# The relay is mounted on the same FastAPI process — we hit it through
# loopback so the request never leaves the container.
BASE_URL = "http://127.0.0.1:8001/emergent-llm/v1"
PINNED_MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4.1-mini",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
    "gemini-3-flash-preview",
]


def seed_emergent_endpoint() -> None:
    try:
        from core.database import SessionLocal, ModelEndpoint
    except Exception as e:
        logger.warning("seed_emergent_endpoint: DB not ready: %s", e)
        return

    db = SessionLocal()
    try:
        existing = db.query(ModelEndpoint).filter(ModelEndpoint.id == ENDPOINT_ID).one_or_none()
        if existing is not None:
            # Refresh URL & pinned models in case they drift; keep is_enabled as-is.
            existing.base_url = BASE_URL
            existing.pinned_models = json.dumps(PINNED_MODELS)
            existing.cached_models = json.dumps(PINNED_MODELS)
            existing.endpoint_kind = "api"
            existing.model_refresh_mode = "manual"
            existing.supports_tools = False
            db.commit()
            logger.info("emergent-llm endpoint already seeded (id=%s) — refreshed.", ENDPOINT_ID)
            return

        ep = ModelEndpoint(
            id=ENDPOINT_ID,
            name=ENDPOINT_NAME,
            base_url=BASE_URL,
            api_key=None,  # auth-exempt on the relay, no key needed
            is_enabled=True,
            hidden_models=None,
            cached_models=json.dumps(PINNED_MODELS),
            pinned_models=json.dumps(PINNED_MODELS),
            model_type="llm",
            endpoint_kind="api",
            model_refresh_mode="manual",
            supports_tools=False,
            owner=None,  # shared / visible to every user
        )
        db.add(ep)
        db.commit()
        logger.info("Seeded Emergent LLM model endpoint (id=%s).", ENDPOINT_ID)
    except Exception as e:
        db.rollback()
        logger.warning("seed_emergent_endpoint failed: %s", e)
    finally:
        db.close()
