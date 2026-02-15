"""
API key generation and verification helpers.
"""

from __future__ import annotations

import hashlib
import secrets

from app.core.config import settings


class ApiKeyService:
    PREFIX = "svk_"

    @staticmethod
    def generate_secret() -> str:
        # URL-safe, high entropy. Prefix helps identify secrets in logs.
        return f"{ApiKeyService.PREFIX}{secrets.token_urlsafe(32)}"

    @staticmethod
    def last4(secret: str) -> str:
        value = (secret or "").strip()
        return value[-4:] if len(value) >= 4 else value

    @staticmethod
    def hash_secret(secret: str) -> str:
        """
        Server-salted SHA-256 hash.

        We intentionally use a server secret (JWT_SECRET_KEY) as salt so two
        identical API keys would still be hashed the same (not ideal, but they
        are randomly generated so collisions are effectively impossible). This
        keeps verification simple and avoids storing per-key salts.
        """
        normalized = (secret or "").strip()
        salt = (settings.JWT_SECRET_KEY or "").strip()
        return hashlib.sha256(f"{normalized}:{salt}".encode()).hexdigest()

