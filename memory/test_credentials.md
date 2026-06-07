# Test Credentials — Sophie's · Odysseus

## Default admin (unchanged)
- **URL**: https://44dd8b43-4843-4459-95b5-0cdc96ab7a32.preview.emergentagent.com/login
- **Username**: `admin`
- **Password**: `admin123`

## Permanent owner (`amarax.tm@gmail.com`)
- **Username**: `amarax.tm@gmail.com`
- **Initial password**: `admin123` (same as admin, as requested)
- `is_admin: true`, `is_owner: true`, `must_change_password: true`
- On first login the UI **forces a password change** before letting the user
  into the app. After the change, the flag flips off and never reseeds —
  your new password persists across restarts.
- If you ever want to reissue the temporary password, restart with the
  user removed from `/app/data/auth.json` — the seeder in
  `/app/owner_seed.py` will recreate it.

## Built-in LLM provider
- Endpoint: `Emergent LLM (built-in)` — auto-seeded, ready to use in
  Settings → Model Endpoints.
- Available models (verified): `gpt-4o-mini`, `gpt-4o`, `gpt-4.1-mini`,
  `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`, `gemini-3-flash-preview`.
