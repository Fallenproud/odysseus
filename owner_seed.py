"""Seed the permanent owner+admin user (amarax.tm@gmail.com).

Idempotent: only creates the user if it doesn't already exist. Once the user
logs in and changes their password, this seeder will leave them alone — it
never overwrites an existing record. Runs once at boot from server.py.
"""
from __future__ import annotations

import json
import logging
import os
import time

logger = logging.getLogger(__name__)

OWNER_USERNAME = "amarax.tm@gmail.com"
OWNER_INITIAL_PASSWORD = "admin123"
AUTH_FILE = "/app/data/auth.json"


def _hash_password(password: str) -> str:
    import bcrypt
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def seed_owner_user() -> None:
    if not os.path.exists(AUTH_FILE):
        logger.warning("seed_owner_user: auth.json not present at %s — skipping.", AUTH_FILE)
        return

    try:
        with open(AUTH_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.warning("seed_owner_user: could not read auth.json: %s", e)
        return

    users = data.setdefault("users", {})
    key = OWNER_USERNAME.strip().lower()

    if key in users:
        # Already exists — never overwrite (user may have changed their
        # password already; we don't want to reseed it on every boot).
        logger.info("Owner user %s already exists — leaving untouched.", key)
        return

    try:
        # Mirror the privilege shape created by AuthManager.create_user so
        # downstream code (privilege checks, settings, etc.) doesn't trip on
        # a missing field.
        from core.auth import ADMIN_PRIVILEGES  # type: ignore
        privileges = dict(ADMIN_PRIVILEGES)
    except Exception:
        privileges = {}

    users[key] = {
        "password_hash": _hash_password(OWNER_INITIAL_PASSWORD),
        "created": time.time(),
        "is_admin": True,
        "is_owner": True,  # informational marker; consumed by /api/auth/status downstream if needed
        "must_change_password": True,
        "privileges": privileges,
    }

    try:
        with open(AUTH_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(
            "Seeded permanent owner user %s (must change password on first login).",
            key,
        )
    except Exception as e:
        logger.warning("seed_owner_user: could not write auth.json: %s", e)
