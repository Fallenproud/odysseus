# Test Credentials — Odysseus

## Admin
- **URL**: https://44dd8b43-4843-4459-95b5-0cdc96ab7a32.preview.emergentagent.com/login
- **Username**: `admin`
- **Password**: `admin123`

Created via `setup.py` with `ODYSSEUS_ADMIN_USER` / `ODYSSEUS_ADMIN_PASSWORD` env vars.
Stored at `/app/data/auth.json` (bcrypt hashed).
Change it from Settings → Account after first login.

## Built-in LLM provider
- Endpoint name: `Emergent LLM (built-in)`
- Base URL: `http://127.0.0.1:8001/emergent-llm/v1`
- Backed by `EMERGENT_LLM_KEY` in `/app/.env`
- Auto-seeded into the `model_endpoints` table on boot.
- Available models: `gpt-4o-mini`, `gpt-4o`, `gpt-4.1-mini`, `gpt-4.1`,
  `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`,
  `gemini-3-flash-preview`, `gemini-3.1-pro-preview`.
