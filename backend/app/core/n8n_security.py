"""
Security layer for SvontAI <-> n8n communication.

Provides HMAC signature generation and verification for secure
communication between SvontAI and n8n workflow engine.
"""

import hmac
import hashlib
import json
import time
import logging
from typing import Optional, Tuple
from datetime import datetime, timedelta

from fastapi import Request, HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)

# Signature validity window (seconds) - prevents replay attacks
SIGNATURE_VALIDITY_SECONDS = 300  # 5 minutes


def generate_signature(payload: dict | str, secret: str, timestamp: Optional[int] = None) -> Tuple[str, int]:
    """
    Generate HMAC-SHA256 signature for a payload.
    
    Args:
        payload: The payload to sign (dict will be JSON serialized)
        secret: The shared secret for signing
        timestamp: Optional Unix timestamp (uses current time if not provided)
    
    Returns:
        Tuple of (signature, timestamp)
    """
    if timestamp is None:
        timestamp = int(time.time())
    
    # Serialize payload if dict
    if isinstance(payload, dict):
        payload_str = json.dumps(payload, separators=(',', ':'), sort_keys=True)
    else:
        payload_str = payload
    
    # Create message to sign: timestamp.payload
    message = f"{timestamp}.{payload_str}"
    
    # Generate HMAC-SHA256 signature
    signature = hmac.new(
        secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return signature, timestamp


def verify_signature(
    payload: dict | str,
    signature: str,
    timestamp: int,
    secret: str,
    max_age_seconds: int = SIGNATURE_VALIDITY_SECONDS
) -> Tuple[bool, str]:
    """
    Verify HMAC-SHA256 signature for a payload.
    
    Args:
        payload: The payload that was signed
        signature: The signature to verify
        timestamp: The timestamp when signature was generated
        secret: The shared secret for verification
        max_age_seconds: Maximum age of signature in seconds
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check timestamp freshness
    current_time = int(time.time())
    if abs(current_time - timestamp) > max_age_seconds:
        return False, f"Signature expired. Max age: {max_age_seconds}s"
    
    # Regenerate signature
    expected_signature, _ = generate_signature(payload, secret, timestamp)
    
    # Compare signatures (constant-time comparison to prevent timing attacks)
    if not hmac.compare_digest(signature, expected_signature):
        return False, "Invalid signature"
    
    return True, ""


def generate_svontai_to_n8n_headers(payload: dict, tenant_id: str) -> dict:
    """
    Generate headers for SvontAI -> n8n requests.
    
    Args:
        payload: The request payload
        tenant_id: The tenant ID making the request
    
    Returns:
        Dict of headers to include in the request
    """
    signature, timestamp = generate_signature(payload, settings.SVONTAI_TO_N8N_SECRET)
    
    return {
        "X-SvontAI-Signature": signature,
        "X-SvontAI-Timestamp": str(timestamp),
        "X-Tenant-Id": str(tenant_id),
        "X-Request-Source": "svontai",
        "Content-Type": "application/json"
    }


def verify_n8n_to_svontai_request(
    request_body: bytes,
    signature: str,
    timestamp_str: str,
    tenant_id: str
) -> Tuple[bool, str]:
    """
    Verify a request from n8n to SvontAI.
    
    Args:
        request_body: Raw request body bytes
        signature: X-N8N-Signature header value
        timestamp_str: X-N8N-Timestamp header value
        tenant_id: X-Tenant-Id header value
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        timestamp = int(timestamp_str)
    except (ValueError, TypeError):
        return False, "Invalid timestamp format"
    
    if not tenant_id:
        return False, "Missing tenant ID"
    
    try:
        payload = request_body.decode('utf-8')
    except UnicodeDecodeError:
        return False, "Invalid request body encoding"
    
    return verify_signature(
        payload,
        signature,
        timestamp,
        settings.N8N_TO_SVONTAI_SECRET
    )


async def verify_n8n_request_dependency(request: Request) -> dict:
    """
    FastAPI dependency to verify n8n requests.
    
    Raises HTTPException if verification fails.
    Returns dict with tenant_id if successful.
    """
    # Get headers
    signature = request.headers.get("X-N8N-Signature")
    timestamp_str = request.headers.get("X-N8N-Timestamp")
    tenant_id = request.headers.get("X-Tenant-Id")
    
    # Check required headers
    if not signature:
        logger.warning("Missing X-N8N-Signature header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing signature header"
        )
    
    if not timestamp_str:
        logger.warning("Missing X-N8N-Timestamp header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing timestamp header"
        )
    
    if not tenant_id:
        logger.warning("Missing X-Tenant-Id header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing tenant ID header"
        )
    
    # Get raw body
    body = await request.body()
    
    # Verify signature
    is_valid, error_msg = verify_n8n_to_svontai_request(
        body, signature, timestamp_str, tenant_id
    )
    
    if not is_valid:
        logger.warning(f"n8n request verification failed: {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Request verification failed: {error_msg}"
        )
    
    logger.info(f"n8n request verified for tenant {tenant_id}")
    
    return {
        "tenant_id": tenant_id,
        "verified": True
    }


def create_n8n_jwt_token(tenant_id: str, expires_minutes: int = 5) -> str:
    """
    Create a short-lived JWT token for n8n to use when calling back to SvontAI.
    
    This is an alternative to HMAC for simpler n8n workflows.
    
    Args:
        tenant_id: The tenant ID
        expires_minutes: Token validity in minutes
    
    Returns:
        JWT token string
    """
    from jose import jwt
    
    payload = {
        "tenant_id": str(tenant_id),
        "type": "n8n_callback",
        "exp": datetime.utcnow() + timedelta(minutes=expires_minutes),
        "iat": datetime.utcnow()
    }
    
    return jwt.encode(
        payload,
        settings.N8N_TO_SVONTAI_SECRET,
        algorithm="HS256"
    )


def verify_n8n_jwt_token(token: str) -> Tuple[bool, Optional[dict], str]:
    """
    Verify a JWT token from n8n.
    
    Args:
        token: The JWT token to verify
    
    Returns:
        Tuple of (is_valid, payload, error_message)
    """
    from jose import jwt, JWTError
    
    try:
        payload = jwt.decode(
            token,
            settings.N8N_TO_SVONTAI_SECRET,
            algorithms=["HS256"]
        )
        
        if payload.get("type") != "n8n_callback":
            return False, None, "Invalid token type"
        
        return True, payload, ""
    
    except JWTError as e:
        return False, None, str(e)


async def verify_n8n_bearer_token(request: Request) -> dict:
    """
    FastAPI dependency to verify n8n Bearer token requests.
    
    Alternative to HMAC verification for simpler n8n workflows.
    """
    auth_header = request.headers.get("Authorization")
    tenant_id = request.headers.get("X-Tenant-Id")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header"
        )
    
    token = auth_header.replace("Bearer ", "")
    
    is_valid, payload, error_msg = verify_n8n_jwt_token(token)
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {error_msg}"
        )
    
    # Verify tenant_id matches if provided in header
    if tenant_id and payload.get("tenant_id") != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant ID mismatch"
        )
    
    return {
        "tenant_id": payload.get("tenant_id"),
        "verified": True
    }
