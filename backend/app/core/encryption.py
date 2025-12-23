"""
Encryption utilities for secure storage of sensitive data.
Uses Fernet symmetric encryption (AES-128-CBC with HMAC).
"""

import base64
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import settings


class EncryptionService:
    """Service for encrypting and decrypting sensitive data."""
    
    def __init__(self, key: Optional[str] = None):
        """
        Initialize the encryption service.
        
        Args:
            key: Base64-encoded 32-byte key. If not provided, uses ENCRYPTION_KEY from settings.
        """
        encryption_key = key or getattr(settings, 'ENCRYPTION_KEY', None)
        
        if not encryption_key:
            # Generate a key from SECRET_KEY if ENCRYPTION_KEY not set
            encryption_key = self._derive_key_from_secret(settings.JWT_SECRET_KEY)
        
        # Ensure key is valid Fernet key (32 bytes, base64 encoded)
        try:
            self.fernet = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
        except (ValueError, TypeError):
            # If key is not a valid Fernet key, derive one
            derived_key = self._derive_key_from_secret(encryption_key)
            self.fernet = Fernet(derived_key)
    
    def _derive_key_from_secret(self, secret: str) -> bytes:
        """
        Derive a Fernet-compatible key from an arbitrary secret.
        
        Args:
            secret: The secret string to derive key from.
            
        Returns:
            Base64-encoded 32-byte key.
        """
        # Use a fixed salt for deterministic key derivation
        # In production, consider using a per-tenant salt stored separately
        salt = b"svontai_encryption_salt_v1"
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(secret.encode()))
        return key
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string.
        
        Args:
            plaintext: The string to encrypt.
            
        Returns:
            Base64-encoded encrypted string.
        """
        if not plaintext:
            return ""
        
        encrypted = self.fernet.encrypt(plaintext.encode())
        return encrypted.decode()
    
    def decrypt(self, ciphertext: str) -> Optional[str]:
        """
        Decrypt an encrypted string.
        
        Args:
            ciphertext: The base64-encoded encrypted string.
            
        Returns:
            The decrypted plaintext string, or None if decryption fails.
        """
        if not ciphertext:
            return None
        
        try:
            decrypted = self.fernet.decrypt(ciphertext.encode())
            return decrypted.decode()
        except InvalidToken:
            return None
    
    def rotate_encryption(self, ciphertext: str, new_key: str) -> Optional[str]:
        """
        Re-encrypt data with a new key.
        
        Args:
            ciphertext: The currently encrypted data.
            new_key: The new encryption key.
            
        Returns:
            Data encrypted with the new key, or None if re-encryption fails.
        """
        plaintext = self.decrypt(ciphertext)
        if plaintext is None:
            return None
        
        new_service = EncryptionService(new_key)
        return new_service.encrypt(plaintext)


# Singleton instance
encryption_service = EncryptionService()


def encrypt_token(token: str) -> str:
    """Convenience function to encrypt a token."""
    return encryption_service.encrypt(token)


def decrypt_token(encrypted_token: str) -> Optional[str]:
    """Convenience function to decrypt a token."""
    return encryption_service.decrypt(encrypted_token)


def generate_encryption_key() -> str:
    """
    Generate a new Fernet-compatible encryption key.
    
    Returns:
        Base64-encoded 32-byte key as string.
    """
    return Fernet.generate_key().decode()

