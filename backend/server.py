# Emergent-environment wrapper for the Odysseus FastAPI app.
# Supervisor runs `uvicorn server:app` from /app/backend on port 8001.
# The real app lives at /app/app.py — we just re-export it here.

import os
import sys

# Make the Odysseus project root importable.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Work from the project root so relative paths (data/, static/, …) resolve.
os.chdir(ROOT)

from app import app  # noqa: F401, E402  (re-exported for uvicorn)

# One-time seed of the built-in Emergent LLM model endpoint, after the DB
# (initialized inside app.py) is ready.
try:
    from emergent_llm_seed import seed_emergent_endpoint
    seed_emergent_endpoint()
except Exception as _e:  # pragma: no cover — non-fatal
    import logging
    logging.getLogger(__name__).warning("Emergent LLM seed skipped: %s", _e)

# Seed the permanent owner+admin user (amarax.tm@gmail.com). Idempotent —
# never overwrites an existing record, so once the user changes their
# password it stays changed across restarts.
try:
    from owner_seed import seed_owner_user
    seed_owner_user()
except Exception as _e:  # pragma: no cover — non-fatal
    import logging
    logging.getLogger(__name__).warning("Owner seed skipped: %s", _e)
