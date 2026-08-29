"""
Authentication router for login, register, and token refresh.
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.config import settings
from app.core.legal import KVKK_NOTICE_VERSION, PRIVACY_NOTICE_VERSION, TERMS_VERSION
from app.core.encryption import decrypt_token, encrypt_token
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    create_temporary_token,
    decode_token,
    hash_token
)
from app.core.rate_limit import (
    client_ip,
    email_confirm_rate_limiter,
    email_verification_rate_limiter,
    login_account_rate_limiter,
    login_rate_limiter,
    password_reset_rate_limiter,
    rate_limit_key,
    refresh_rate_limiter,
    register_rate_limiter,
    require_rate_limit,
    subject_rate_limit_key,
)
from app.core.time import utc_now_naive
from app.core.totp import generate_secret, provisioning_uri, verify_code
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.session import UserSession
from app.models.password_reset import PasswordResetCode
from app.models.email_verification import EmailVerificationCode
from app.models.onboarding import AuditLog
from app.schemas.auth import (
    ChangePasswordRequest,
    AdminTwoFactorEnableRequest,
    LoginRequest,
    TwoFactorDisableRequest,
    TwoFactorEnableRequest,
    TwoFactorSetupRequest,
    TwoFactorSetupResponse,
    TwoFactorStatusResponse,
    AccessTokenResponse,
)
from app.schemas.user import UserCreate, UserResponse
from app.schemas.password_reset import (
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    PasswordResetResponse
)
from app.schemas.email_verification import (
    EmailVerificationConfirmRequest,
    EmailVerificationRequest,
    EmailVerificationResponse
)
from app.services.session_service import SessionService
from app.services.email_service import EmailService
from app.services.system_event_service import SystemEventService

router = APIRouter(prefix="/auth", tags=["Authentication"])

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
REFRESH_COOKIE_NAME = "smartwa_refresh_token"


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=settings.ENVIRONMENT == "prod",
        samesite="lax",
        path="/",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        httponly=True,
        secure=settings.ENVIRONMENT == "prod",
        samesite="lax",
        path="/",
    )


def _require_allowed_refresh_origin(request: Request) -> None:
    """Block cross-site browser refresh attempts while allowing non-browser clients."""
    origin = (request.headers.get("Origin") or "").strip().rstrip("/")
    if origin and origin != settings.FRONTEND_URL.strip().rstrip("/"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="İstek kaynağına izin verilmiyor",
        )


def _hash_reset_code(email: str, code: str) -> str:
    normalized = email.strip().lower()
    return hashlib.sha256(f"{normalized}:{code}:{settings.JWT_SECRET_KEY}".encode()).hexdigest()


def _hash_email_verification_code(email: str, code: str) -> str:
    normalized = email.strip().lower()
    return hashlib.sha256(f"verify:{normalized}:{code}:{settings.JWT_SECRET_KEY}".encode()).hexdigest()


def _get_user_by_email(db: Session, email: str) -> User | None:
    normalized = email.strip().lower()
    return db.query(User).filter(func.lower(User.email) == normalized).first()


def _issue_email_verification_code(db: Session, user: User) -> tuple[str, datetime]:
    now = utc_now_naive()
    normalized_email = user.email.strip().lower()
    db.query(EmailVerificationCode).filter(
        EmailVerificationCode.user_id == user.id,
        EmailVerificationCode.used_at.is_(None)
    ).update(
        {"used_at": now},
        synchronize_session=False
    )

    code = str(secrets.randbelow(900000) + 100000)
    verification_record = EmailVerificationCode(
        user_id=user.id,
        email=normalized_email,
        code_hash=_hash_email_verification_code(normalized_email, code),
        expires_at=now + timedelta(minutes=settings.EMAIL_VERIFICATION_CODE_EXPIRE_MINUTES)
    )
    db.add(verification_record)
    db.commit()
    return code, now


def _require_valid_two_factor_code(user: User, incoming_code: str | None) -> None:
    secret_encrypted = (user.two_factor_secret_encrypted or "").strip()
    if not secret_encrypted:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="2FA yapılandırması eksik. Lütfen güvenlik ayarlarından yeniden kurun."
        )

    secret = decrypt_token(secret_encrypted)
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="2FA doğrulama sırrı çözülemedi."
        )

    if not incoming_code:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "TWO_FACTOR_REQUIRED", "message": "İki faktörlü doğrulama kodu gerekli."},
        )

    if not verify_code(secret, incoming_code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "TWO_FACTOR_INVALID", "message": "İki faktör doğrulama kodu geçersiz."},
        )


def _validate_super_admin_login(user: User, credentials: LoginRequest) -> str | None:
    if credentials.portal != "super_admin":
        return None

    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ADMIN_PORTAL_FORBIDDEN", "message": "Süper admin giriş yetkiniz bulunmuyor."}
        )

    session_note = (credentials.admin_session_note or "").strip()
    if len(session_note) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "ADMIN_SESSION_NOTE_REQUIRED",
                "message": "Süper admin girişi için en az 8 karakterlik oturum notu zorunludur."
            }
        )

    return session_note


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """
    Register a new user.
    
    Args:
        user_data: User registration data.
        db: Database session.
    
    Returns:
        The created user.
    """
    normalized_email = user_data.email.strip().lower()
    require_rate_limit(
        register_rate_limiter,
        rate_limit_key(request, "register", normalized_email),
        "Çok fazla kayıt denemesi yaptınız. Lütfen daha sonra tekrar deneyin.",
    )
    # Check if email already exists
    existing_user = _get_user_by_email(db, normalized_email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu e-posta adresi zaten kayıtlı"
        )
    
    if len(user_data.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Şifre en az 8 karakter olmalıdır"
        )

    # Create new user
    user = User(
        email=normalized_email,
        password_hash=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        email_verified=False
    )
    
    db.add(user)
    db.flush()
    db.add(AuditLog(
        user_id=user.id,
        action="legal.registration.accepted",
        resource_type="legal_bundle",
        resource_id=TERMS_VERSION,
        payload_json={
            "terms_accepted": True,
            "privacy_notice_acknowledged": True,
            "terms_version": TERMS_VERSION,
            "privacy_version": PRIVACY_NOTICE_VERSION,
            "kvkk_notice_version": KVKK_NOTICE_VERSION,
        },
        ip_address=client_ip(request),
        user_agent=(request.headers.get("user-agent") or "")[:500] or None,
    ))
    db.commit()
    db.refresh(user)

    code, now = _issue_email_verification_code(db, user)
    sent = EmailService.send_email_verification_code(
        user.email,
        user.full_name,
        code,
        settings.EMAIL_VERIFICATION_CODE_EXPIRE_MINUTES
    )
    if not sent:
        if settings.ENVIRONMENT == "dev":
            return user
        db.query(EmailVerificationCode).filter(
            EmailVerificationCode.user_id == user.id,
            EmailVerificationCode.used_at.is_(None)
        ).update({"used_at": now}, synchronize_session=False)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Doğrulama kodu e-postası gönderilemedi. Lütfen tekrar deneyin."
        )
    
    return user


@router.post("/login", response_model=AccessTokenResponse)
async def login(
    credentials: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
) -> AccessTokenResponse:
    """
    Login and return a short-lived access token. Refresh stays in an HttpOnly cookie.
    
    Args:
        credentials: Login credentials.
        db: Database session.
    
    Returns:
        Access token.
    """
    normalized_email = credentials.email.strip().lower()
    require_rate_limit(
        login_rate_limiter,
        rate_limit_key(request, "login", normalized_email),
        "Çok fazla deneme yaptınız. Lütfen daha sonra tekrar deneyin.",
    )
    require_rate_limit(
        login_account_rate_limiter,
        subject_rate_limit_key("login-account", normalized_email),
        "Bu hesap için çok fazla giriş denemesi yapıldı. Lütfen daha sonra tekrar deneyin.",
    )

    # Find user by email
    user = _get_user_by_email(db, normalized_email)

    if user and user.locked_until and user.locked_until > utc_now_naive():
        SystemEventService(db).log(
            tenant_id=None,
            source="auth",
            level="warn",
            code="AUTH_ACCOUNT_LOCKED",
            message="Login attempt for locked account",
            meta_json={"email": normalized_email, "ip": client_ip(request)},
            correlation_id=None
        )
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Hesabınız geçici olarak kilitlendi. Lütfen daha sonra tekrar deneyin."
        )
    
    if user is None or not verify_password(credentials.password, user.password_hash):
        if user:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
                user.locked_until = utc_now_naive() + timedelta(minutes=LOCKOUT_MINUTES)
            db.commit()
        SystemEventService(db).log(
            tenant_id=None,
            source="auth",
            level="warn",
            code="AUTH_LOGIN_FAILED",
            message="Invalid login attempt",
            meta_json={"email": normalized_email, "ip": client_ip(request)},
            correlation_id=None
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-posta veya şifre hatalı",
            headers={"WWW-Authenticate": "Bearer"}
        )
    if not user.is_active:
        SystemEventService(db).log(
            tenant_id=None,
            source="auth",
            level="warn",
            code="AUTH_USER_DISABLED",
            message="Login attempt for disabled user",
            meta_json={"email": normalized_email, "ip": client_ip(request)},
            correlation_id=None
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hesabınız devre dışı bırakıldı"
        )

    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "EMAIL_VERIFICATION_REQUIRED",
                "message": "E-posta adresinizi doğrulayın. Doğrulama kodu ekranına yönlendiriliyorsunuz.",
                "email": normalized_email,
            },
        )

    if (
        user.is_admin
        and settings.SUPER_ADMIN_REQUIRE_2FA
        and not user.two_factor_enabled
        and credentials.portal != "super_admin"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "SUPER_ADMIN_2FA_SETUP_REQUIRED",
                "message": "Önce süper admin giriş ekranından 2FA kurulumunu tamamlayın.",
            },
        )

    admin_session_note = _validate_super_admin_login(user, credentials)

    if credentials.portal == "super_admin" and settings.SUPER_ADMIN_REQUIRE_2FA and not user.two_factor_enabled:
        secret = generate_secret()
        user.two_factor_secret_encrypted = encrypt_token(secret)
        user.two_factor_enabled = False
        user.failed_login_attempts = 0
        user.locked_until = None
        setup_token = create_temporary_token(
            {"sub": str(user.id), "portal": "super_admin"},
            token_type="admin_2fa_setup",
            expires_minutes=10,
        )
        db.add(
            AuditLog(
                tenant_id=None,
                user_id=user.id,
                action="super_admin_2fa_enrollment_started",
                resource_type="auth",
                resource_id=str(user.id),
                payload_json={"session_note": admin_session_note},
                ip_address=client_ip(request),
                user_agent=request.headers.get("User-Agent"),
            )
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "SUPER_ADMIN_2FA_SETUP_REQUIRED",
                "message": "Süper admin girişi için Authenticator doğrulamasını tamamlayın.",
                "setup_token": setup_token,
                "secret": secret,
                "otpauth_uri": provisioning_uri(secret, user.email),
            },
        )

    if user.failed_login_attempts or user.locked_until:
        user.failed_login_attempts = 0
        user.locked_until = None

    if user.two_factor_enabled:
        _require_valid_two_factor_code(user, credentials.two_factor_code)
    
    # Create tokens + session
    portal_value = credentials.portal or "tenant"
    refresh_token = create_refresh_token(data={"sub": str(user.id), "portal": portal_value, "mfa": bool(user.two_factor_enabled)})
    session_service = SessionService(db)
    session = session_service.create_session(
        user_id=user.id,
        refresh_token=refresh_token,
        ip_address=client_ip(request),
        user_agent=request.headers.get("User-Agent")
    )
    refresh_token = create_refresh_token(
        data={"sub": str(user.id), "portal": portal_value, "mfa": bool(user.two_factor_enabled)},
        session_id=str(session.id),
    )
    session_service.rotate_session(session, refresh_token)
    access_token = create_access_token(
        data={"sub": str(user.id), "portal": portal_value, "sid": str(session.id), "mfa": bool(user.two_factor_enabled)}
    )

    if credentials.portal == "super_admin":
        db.add(
            AuditLog(
                tenant_id=None,
                user_id=user.id,
                action="super_admin_login",
                resource_type="auth",
                resource_id=str(user.id),
                payload_json={
                    "portal": credentials.portal,
                    "session_note": admin_session_note,
                    "session_id": str(session.id),
                    "two_factor_enabled": user.two_factor_enabled,
                    "super_admin_2fa_enforced": settings.SUPER_ADMIN_REQUIRE_2FA
                },
                ip_address=client_ip(request),
                user_agent=request.headers.get("User-Agent")
            )
        )

    user.last_login = utc_now_naive()
    db.commit()
    _set_refresh_cookie(response, refresh_token)
    
    return AccessTokenResponse(access_token=access_token)


@router.post("/admin/2fa/enable")
async def enable_super_admin_two_factor(
    payload: AdminTwoFactorEnableRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    """Complete mandatory super-admin 2FA enrollment without issuing a broad session."""
    require_rate_limit(
        login_rate_limiter,
        rate_limit_key(request, "admin-2fa-enable"),
        "Çok fazla doğrulama denemesi yaptınız. Lütfen daha sonra tekrar deneyin.",
    )
    token_payload = decode_token(payload.setup_token)
    if (
        not token_payload
        or token_payload.get("type") != "admin_2fa_setup"
        or token_payload.get("portal") != "super_admin"
        or not token_payload.get("sub")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="2FA kurulum oturumu geçersiz veya süresi dolmuş.",
        )

    try:
        user_id = UUID(str(token_payload["sub"]))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="2FA kurulum oturumu geçersiz.",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_admin or not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Süper admin yetkisi gerekli.")
    if user.two_factor_enabled:
        return {"enabled": True}

    secret_encrypted = (user.two_factor_secret_encrypted or "").strip()
    secret = decrypt_token(secret_encrypted) if secret_encrypted else ""
    if not secret or not verify_code(secret, payload.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Doğrulama kodu geçersiz.")

    user.two_factor_enabled = True
    db.add(
        AuditLog(
            tenant_id=None,
            user_id=user.id,
            action="super_admin_2fa_enabled",
            resource_type="auth",
            resource_id=str(user.id),
            payload_json={"mandatory": settings.SUPER_ADMIN_REQUIRE_2FA},
            ip_address=client_ip(request),
            user_agent=request.headers.get("User-Agent"),
        )
    )
    db.commit()
    return {"enabled": True}


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
    cookie_refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
    db: Session = Depends(get_db)
) -> AccessTokenResponse:
    """
    Refresh access token using refresh token.
    
    Args:
        db: Database session.
    
    Returns:
        New access token.
    """
    require_rate_limit(
        refresh_rate_limiter,
        rate_limit_key(request, "refresh"),
        "Çok fazla token yenileme denemesi. Lütfen daha sonra tekrar deneyin.",
    )
    _require_allowed_refresh_origin(request)
    incoming_refresh_token = cookie_refresh_token
    if not incoming_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token bulunamadı",
            headers={"WWW-Authenticate": "Bearer"}
        )

    payload = decode_token(incoming_refresh_token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token geçersiz veya süresi dolmuş",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Check token type
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz token türü",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token'da kullanıcı bilgisi bulunamadı"
        )

    # Verify user still exists
    try:
        user_uuid = UUID(str(user_id))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token'da kullanıcı bilgisi bulunamadı"
        )

    user = db.query(User).filter(User.id == user_uuid).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı bulunamadı"
        )
    
    session_service = SessionService(db)
    refresh_token_value = incoming_refresh_token
    session_id = payload.get("sid")
    portal_value = (payload.get("portal") or "tenant").strip()
    mfa_value = bool(payload.get("mfa"))

    if session_id:
        try:
            session_uuid = UUID(str(session_id))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Oturum geçersiz"
            )

        session = db.query(UserSession).filter(
            UserSession.id == session_uuid,
            UserSession.user_id == user.id
        ).first()
        if session is None or session.revoked_at is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Oturum geçersiz"
            )
        if session.refresh_token_hash != hash_token(refresh_token_value):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token geçersiz"
            )
        refresh_token_value = create_refresh_token(
            data={"sub": str(user.id), "portal": portal_value, "mfa": mfa_value},
            session_id=str(session.id),
        )
        session_service.rotate_session(session, refresh_token_value)
    else:
        session = session_service.create_session(
            user_id=user.id,
            refresh_token=refresh_token_value
        )
        refresh_token_value = create_refresh_token(
            data={"sub": str(user.id), "portal": portal_value, "mfa": mfa_value},
            session_id=str(session.id),
        )
        session_service.rotate_session(session, refresh_token_value)

    # Create new access token
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "portal": portal_value,
            "sid": str(session.id),
            "mfa": mfa_value,
        }
    )
    
    _set_refresh_cookie(response, refresh_token_value)
    return AccessTokenResponse(access_token=access_token)


@router.post("/logout")
async def logout(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now = utc_now_naive()
    db.query(UserSession).filter(
        UserSession.user_id == current_user.id,
        UserSession.revoked_at.is_(None)
    ).update({"revoked_at": now}, synchronize_session=False)
    db.commit()
    _clear_refresh_cookie(response)
    return {"success": True}


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mevcut şifre hatalı"
        )
    if verify_password(payload.new_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Yeni şifre mevcut şifre ile aynı olamaz"
        )

    current_user.password_hash = get_password_hash(payload.new_password)
    current_user.updated_at = utc_now_naive()
    db.query(UserSession).filter(
        UserSession.user_id == current_user.id,
        UserSession.revoked_at.is_(None)
    ).update({"revoked_at": utc_now_naive()}, synchronize_session=False)
    db.commit()

    EmailService.send_password_changed_confirmation(current_user.email, current_user.full_name)
    return {"success": True, "message": "Şifre güncellendi. Lütfen tekrar giriş yapın."}


@router.get("/2fa/status", response_model=TwoFactorStatusResponse)
async def get_two_factor_status(
    current_user: User = Depends(get_current_user),
) -> TwoFactorStatusResponse:
    return TwoFactorStatusResponse(enabled=bool(current_user.two_factor_enabled))


@router.post("/2fa/setup", response_model=TwoFactorSetupResponse)
async def setup_two_factor(
    payload: TwoFactorSetupRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TwoFactorSetupResponse:
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Şifre doğrulaması başarısız"
        )

    secret = generate_secret()
    current_user.two_factor_secret_encrypted = encrypt_token(secret)
    current_user.two_factor_enabled = False
    current_user.updated_at = utc_now_naive()
    db.commit()

    return TwoFactorSetupResponse(
        secret=secret,
        otpauth_uri=provisioning_uri(secret=secret, account_name=current_user.email, issuer="SvontAI")
    )


@router.post("/2fa/enable")
async def enable_two_factor(
    payload: TwoFactorEnableRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    secret_encrypted = (current_user.two_factor_secret_encrypted or "").strip()
    if not secret_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Önce 2FA kurulumu başlatılmalı"
        )

    secret = decrypt_token(secret_encrypted)
    if not secret or not verify_code(secret, payload.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Doğrulama kodu geçersiz"
        )

    current_user.two_factor_enabled = True
    current_user.updated_at = utc_now_naive()
    db.commit()
    return {"success": True, "enabled": True}


@router.post("/2fa/disable")
async def disable_two_factor(
    payload: TwoFactorDisableRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.two_factor_enabled:
        return {"success": True, "enabled": False}

    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Şifre doğrulaması başarısız"
        )

    _require_valid_two_factor_code(current_user, payload.code)
    current_user.two_factor_enabled = False
    current_user.two_factor_secret_encrypted = None
    current_user.updated_at = utc_now_naive()
    db.commit()
    return {"success": True, "enabled": False}


@router.post("/password-reset/request", response_model=PasswordResetResponse)
async def request_password_reset_code(
    payload: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db)
) -> PasswordResetResponse:
    message = "E-posta kayıtlıysa doğrulama kodu gönderildi."
    normalized_email = payload.email.strip().lower()
    require_rate_limit(
        password_reset_rate_limiter,
        rate_limit_key(request, "password-reset", normalized_email),
        "Çok fazla şifre sıfırlama isteği. Lütfen daha sonra tekrar deneyin.",
    )
    user = _get_user_by_email(db, normalized_email)
    if not user or not user.is_active:
        return PasswordResetResponse(success=True, message=message)

    now = utc_now_naive()
    db.query(PasswordResetCode).filter(
        PasswordResetCode.user_id == user.id,
        PasswordResetCode.used_at.is_(None)
    ).update(
        {"used_at": now},
        synchronize_session=False
    )

    code = str(secrets.randbelow(900000) + 100000)
    reset_record = PasswordResetCode(
        user_id=user.id,
        email=normalized_email,
        code_hash=_hash_reset_code(user.email, code),
        expires_at=now + timedelta(minutes=settings.PASSWORD_RESET_CODE_EXPIRE_MINUTES)
    )
    db.add(reset_record)
    db.commit()

    sent = EmailService.send_password_reset_code(
        user.email,
        user.full_name,
        code,
        settings.PASSWORD_RESET_CODE_EXPIRE_MINUTES
    )
    if sent:
        return PasswordResetResponse(success=True, message=message)

    if settings.ENVIRONMENT == "dev":
        return PasswordResetResponse(
            success=True,
            message=f"Mail gönderimi başarısız, geliştirme kodu: {code}"
        )

    reset_record.used_at = now
    db.commit()
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Doğrulama kodu e-postası gönderilemedi. Lütfen tekrar deneyin."
    )


@router.post("/email-verification/request", response_model=EmailVerificationResponse)
async def request_email_verification_code(
    payload: EmailVerificationRequest,
    request: Request,
    db: Session = Depends(get_db)
) -> EmailVerificationResponse:
    message = "E-posta kayıtlıysa doğrulama kodu gönderildi."
    normalized_email = payload.email.strip().lower()
    require_rate_limit(
        email_verification_rate_limiter,
        rate_limit_key(request, "email-verification", normalized_email),
        "Çok fazla doğrulama kodu isteği. Lütfen daha sonra tekrar deneyin.",
    )
    user = _get_user_by_email(db, normalized_email)

    if not user or not user.is_active:
        return EmailVerificationResponse(success=True, message=message)
    if user.email_verified:
        return EmailVerificationResponse(
            success=True,
            message="E-posta adresiniz zaten doğrulandı.",
            verified=True,
        )

    code, now = _issue_email_verification_code(db, user)
    sent = EmailService.send_email_verification_code(
        user.email,
        user.full_name,
        code,
        settings.EMAIL_VERIFICATION_CODE_EXPIRE_MINUTES
    )
    if sent:
        return EmailVerificationResponse(success=True, message=message)

    if settings.ENVIRONMENT == "dev":
        return EmailVerificationResponse(
            success=True,
            message=f"Mail gönderimi başarısız, geliştirme kodu: {code}"
        )

    db.query(EmailVerificationCode).filter(
        EmailVerificationCode.user_id == user.id,
        EmailVerificationCode.used_at.is_(None)
    ).update({"used_at": now}, synchronize_session=False)
    db.commit()
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Doğrulama kodu e-postası gönderilemedi. Lütfen tekrar deneyin."
    )


@router.post("/email-verification/confirm", response_model=EmailVerificationResponse)
async def confirm_email_verification(
    payload: EmailVerificationConfirmRequest,
    request: Request,
    db: Session = Depends(get_db)
) -> EmailVerificationResponse:
    normalized_email = payload.email.strip().lower()
    require_rate_limit(
        email_confirm_rate_limiter,
        rate_limit_key(request, "email-confirm", normalized_email),
        "Çok fazla kod doğrulama denemesi. Lütfen daha sonra tekrar deneyin.",
    )
    user = _get_user_by_email(db, normalized_email)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kod geçersiz veya süresi dolmuş"
        )

    if user.email_verified:
        return EmailVerificationResponse(
            success=True,
            message="E-posta adresiniz zaten doğrulandı.",
            verified=True,
        )

    verification_record = db.query(EmailVerificationCode).filter(
        EmailVerificationCode.email == normalized_email,
        EmailVerificationCode.used_at.is_(None)
    ).order_by(EmailVerificationCode.created_at.desc()).first()

    now = utc_now_naive()
    if not verification_record or verification_record.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kod geçersiz veya süresi dolmuş"
        )

    if verification_record.attempt_count >= settings.EMAIL_VERIFICATION_MAX_ATTEMPTS:
        verification_record.used_at = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Çok fazla hatalı deneme yapıldı, yeni kod isteyin"
        )

    incoming_hash = _hash_email_verification_code(normalized_email, payload.code.strip())
    if not secrets.compare_digest(incoming_hash, verification_record.code_hash):
        verification_record.attempt_count += 1
        if verification_record.attempt_count >= settings.EMAIL_VERIFICATION_MAX_ATTEMPTS:
            verification_record.used_at = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kod geçersiz veya süresi dolmuş"
        )

    verification_record.used_at = now
    user.email_verified = True
    db.commit()
    EmailService.send_welcome_email(user.email, user.full_name)
    return EmailVerificationResponse(
        success=True,
        message="E-posta adresiniz başarıyla doğrulandı",
        verified=True,
    )


@router.post("/password-reset/confirm", response_model=PasswordResetResponse)
async def confirm_password_reset(
    payload: PasswordResetConfirmRequest,
    request: Request,
    db: Session = Depends(get_db)
) -> PasswordResetResponse:
    normalized_email = payload.email.strip().lower()
    require_rate_limit(
        password_reset_rate_limiter,
        rate_limit_key(request, "password-reset-confirm", normalized_email),
        "Çok fazla şifre sıfırlama denemesi. Lütfen daha sonra tekrar deneyin.",
    )
    user = _get_user_by_email(db, normalized_email)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kod geçersiz veya süresi dolmuş"
        )

    reset_record = db.query(PasswordResetCode).filter(
        PasswordResetCode.email == normalized_email,
        PasswordResetCode.used_at.is_(None)
    ).order_by(PasswordResetCode.created_at.desc()).first()

    now = utc_now_naive()
    if not reset_record or reset_record.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kod geçersiz veya süresi dolmuş"
        )

    if reset_record.attempt_count >= settings.PASSWORD_RESET_MAX_ATTEMPTS:
        reset_record.used_at = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Çok fazla hatalı deneme yapıldı, yeni kod isteyin"
        )

    incoming_hash = _hash_reset_code(normalized_email, payload.code.strip())
    if not secrets.compare_digest(incoming_hash, reset_record.code_hash):
        reset_record.attempt_count += 1
        if reset_record.attempt_count >= settings.PASSWORD_RESET_MAX_ATTEMPTS:
            reset_record.used_at = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kod geçersiz veya süresi dolmuş"
        )

    user.password_hash = get_password_hash(payload.new_password)
    reset_record.used_at = now
    db.query(UserSession).filter(
        UserSession.user_id == user.id,
        UserSession.revoked_at.is_(None)
    ).update({"revoked_at": now}, synchronize_session=False)
    db.commit()

    EmailService.send_password_changed_confirmation(user.email, user.full_name)
    return PasswordResetResponse(
        success=True,
        message="Şifreniz başarıyla güncellendi"
    )
