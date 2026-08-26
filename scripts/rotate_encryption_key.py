#!/usr/bin/env python3
"""Rotate all application ciphertext to the configured primary Fernet key.

Run only while ENCRYPTION_KEY_LEGACY_JWT_FALLBACK=true. The command is
transactional: one unreadable ciphertext aborts the complete rotation.
"""

from __future__ import annotations

import argparse
import copy
import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from cryptography.fernet import Fernet, InvalidToken  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.encryption import encryption_service  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.google_oauth_token import GoogleOAuthToken  # noqa: E402
from app.models.real_estate import (  # noqa: E402
    RealEstateConversationState,
    RealEstateGoogleCalendarIntegration,
    RealEstatePackSettings,
)
from app.models.user import User  # noqa: E402
from app.models.whatsapp_account import WhatsAppAccount  # noqa: E402


def _rotate_value(value: str | None, primary: Fernet) -> tuple[str | None, bool]:
    if not value:
        return value, False
    plaintext = encryption_service.decrypt(value)
    if plaintext is None:
        raise ValueError("unreadable ciphertext encountered")
    rotated = primary.encrypt(plaintext.encode()).decode()
    try:
        primary.decrypt(rotated.encode())
    except InvalidToken as exc:  # pragma: no cover - cryptography invariant
        raise ValueError("rotated ciphertext verification failed") from exc
    return rotated, True


def _rotate_json(value: object, primary: Fernet) -> tuple[object, int]:
    if isinstance(value, dict):
        changed = copy.deepcopy(value)
        count = 0
        for key, item in value.items():
            if key.endswith("_encrypted") and isinstance(item, str) and item:
                changed[key], did_rotate = _rotate_value(item, primary)
                count += int(did_rotate)
            else:
                changed[key], nested_count = _rotate_json(item, primary)
                count += nested_count
        return changed, count
    if isinstance(value, list):
        changed_list: list[object] = []
        count = 0
        for item in value:
            changed, nested_count = _rotate_json(item, primary)
            changed_list.append(changed)
            count += nested_count
        return changed_list, count
    return value, 0


def _rotate_column_rows(
    rows: list[object],
    columns: tuple[str, ...],
    primary: Fernet,
) -> int:
    count = 0
    for row in rows:
        for column in columns:
            rotated, did_rotate = _rotate_value(getattr(row, column), primary)
            if did_rotate:
                setattr(row, column, rotated)
                count += 1
    return count


def rotate(*, apply: bool, session_factory: Callable = SessionLocal) -> dict[str, int]:
    if not settings.ENCRYPTION_KEY_LEGACY_JWT_FALLBACK:
        raise RuntimeError("ENCRYPTION_KEY_LEGACY_JWT_FALLBACK=true is required")
    primary = Fernet(settings.ENCRYPTION_KEY.strip().encode())
    counts: dict[str, int] = {}

    with session_factory() as db:
        try:
            specs = (
                ("users", User, ("two_factor_secret_encrypted",)),
                ("whatsapp_accounts", WhatsAppAccount, ("access_token_encrypted",)),
                (
                    "google_oauth_tokens",
                    GoogleOAuthToken,
                    ("access_token_encrypted", "refresh_token_encrypted"),
                ),
                (
                    "real_estate_google_calendar_integrations",
                    RealEstateGoogleCalendarIntegration,
                    ("access_token_encrypted", "refresh_token_encrypted"),
                ),
                (
                    "real_estate_conversation_states",
                    RealEstateConversationState,
                    ("pii_snapshot_encrypted",),
                ),
            )
            for label, model, columns in specs:
                rows = list(db.scalars(select(model)).all())
                counts[label] = _rotate_column_rows(rows, columns, primary)

            json_count = 0
            settings_rows = list(db.scalars(select(RealEstatePackSettings)).all())
            for row in settings_rows:
                rotated_json, row_count = _rotate_json(row.listings_source or {}, primary)
                if row_count:
                    row.listings_source = rotated_json
                    json_count += row_count
            counts["real_estate_pack_settings"] = json_count

            if apply:
                db.commit()
            else:
                db.rollback()
        except Exception:
            db.rollback()
            raise

    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    try:
        counts = rotate(apply=args.apply)
    except Exception as exc:
        print(f"rotation_failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    total = sum(counts.values())
    print(f"mode={'apply' if args.apply else 'dry-run'} rotated={total}")
    for label, count in sorted(counts.items()):
        print(f"{label}={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
