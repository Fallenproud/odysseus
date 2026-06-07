# Odysseus — Emergent Preview PRD

## Original problem statement
> Clone this project and start frontend and backend for me.

User confirmed:
- Run FastAPI on port 8001, thin Node proxy on port 3000 (preview URL).
- SQLite (Odysseus default), not MongoDB.
- Pre-seeded admin: `admin / admin123`.
- LLM providers unconfigured externally **but** wire up the Emergent LLM
  key as a ready-to-use provider out of the box.

## Project
Odysseus — self-hosted AI workspace (FastAPI single-process app that
serves both APIs and its static UI). Repo cloned from
`https://github.com/Fallenproud/odysseus.git`.

## Architecture in this environment
- `/app/app.py` — original FastAPI app (port 7000 upstream default).
- `/app/backend/server.py` — thin shim that imports `app` and re-exports it
  for `uvicorn server:app --port 8001` (Emergent supervisor convention).
  Also runs `emergent_llm_seed.seed_emergent_endpoint()` at import time.
- `/app/frontend/proxy.js` — Node `http-proxy` forwarder bound to
  `0.0.0.0:3000`, proxies every request (including WebSocket upgrades and
  long SSE streams) to `127.0.0.1:8001`. Emergent ingress sends non-`/api`
  traffic to 3000; Odysseus serves its own UI from the same FastAPI
  process, so we pass everything through.
- SQLite database at `/app/data/app.db` (created by `setup.py`).
- `/app/.env` carries Odysseus runtime config (auth on, sqlite path,
  EMERGENT_LLM_KEY, in-process pollers off).
- `/app/backend/.env` carries the protected `MONGO_URL` / `DB_NAME` keys
  required by the Emergent platform — Odysseus does not use them.

## Emergent LLM integration
- `/app/emergent_llm_relay.py` — OpenAI-compatible router mounted at
  `/emergent-llm/v1/*` on the Odysseus app. Backed by
  `emergentintegrations.llm.chat.LlmChat` and the `EMERGENT_LLM_KEY`.
  Supports `GET /models`, `POST /chat/completions` (both `stream=true`
  SSE and non-streaming JSON).
- `/app/emergent_llm_seed.py` — idempotent seed of a `ModelEndpoint`
  row named "Emergent LLM (built-in)" so the provider shows up in the
  Settings → Model Endpoints UI on first boot.
- Auth bypass: `/emergent-llm/` is in `AUTH_EXEMPT_PREFIXES` (modified
  in `/app/app.py`) so the loopback model probe/chat call from Odysseus
  itself doesn't need a session cookie.
- Verified models (round-trip tested): `gpt-4o-mini`, `gpt-4o`,
  `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`,
  `gemini-3-flash-preview`.

## What's been implemented (2026-06-07)
- [x] Installed Python deps from `requirements.txt`.
- [x] Created `/app/backend/server.py` + `/app/backend/.env`.
- [x] Created `/app/frontend/` Node proxy + `/app/frontend/.env`.
- [x] Initialized SQLite DB via `python setup.py`, seeded admin
      `admin/admin123`.
- [x] Mounted Emergent LLM relay (`/emergent-llm/v1/*`) + seeded
      model endpoint.
- [x] Verified login, model endpoint listing, and live LLM round-trip.

## Backlog / Next Action Items
- P1: Wire up local LLM hosts (Ollama / vLLM / llama.cpp) from inside
      Settings if the user wants on-prem models.
- P2: Optionally bring up ChromaDB so the Vector RAG + Memory features
      come online (currently degrade to keyword fallback).
- P2: Enable in-process email pollers / task scheduler (currently off).
- P3: Configure SearXNG for web search.

## Known degradations (non-blocking)
- ChromaDB not running → Vector RAG / semantic memory unavailable
  (keyword fallback still works).
- `python-magic` not installed → falls back to basic mime detection.
- In-process email pollers and task scheduler intentionally disabled
  via `ODYSSEUS_INPROCESS_POLLERS=0` / `ODYSSEUS_INPROCESS_TASKS=0`.
