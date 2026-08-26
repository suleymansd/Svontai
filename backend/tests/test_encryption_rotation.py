from __future__ import annotations

from cryptography.fernet import Fernet

from app.core.encryption import EncryptionService


def _derived_key(secret: str) -> bytes:
    service = EncryptionService.__new__(EncryptionService)
    return service._derive_key_from_secret(secret)


def test_encryption_service_can_read_legacy_jwt_ciphertext(monkeypatch):
    legacy_secret = "legacy-jwt-secret-that-is-long-enough"
    primary = Fernet.generate_key().decode()
    ciphertext = Fernet(_derived_key(legacy_secret)).encrypt(b"secret-value").decode()

    monkeypatch.setattr("app.core.encryption.settings.JWT_SECRET_KEY", legacy_secret)
    monkeypatch.setattr(
        "app.core.encryption.settings.ENCRYPTION_KEY_LEGACY_JWT_FALLBACK",
        True,
    )

    service = EncryptionService(primary)

    assert service.decrypt(ciphertext) == "secret-value"
    assert Fernet(primary.encode()).decrypt(service.encrypt("new-value").encode()) == b"new-value"


def test_encryption_service_rejects_legacy_ciphertext_when_fallback_disabled(monkeypatch):
    legacy_secret = "legacy-jwt-secret-that-is-long-enough"
    ciphertext = Fernet(_derived_key(legacy_secret)).encrypt(b"secret-value").decode()

    monkeypatch.setattr("app.core.encryption.settings.JWT_SECRET_KEY", legacy_secret)
    monkeypatch.setattr(
        "app.core.encryption.settings.ENCRYPTION_KEY_LEGACY_JWT_FALLBACK",
        False,
    )

    assert EncryptionService(Fernet.generate_key().decode()).decrypt(ciphertext) is None
