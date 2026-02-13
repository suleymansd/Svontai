"""
Authentication router for login, register, and token refresh.
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.config import settings
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_token
)
from app.core.rate_limit import login_rate_limiter, register_rate_limiter, refresh_rate_limiter
from app.models.user import User
from app.models.session import UserSession
from app.models.password_reset import PasswordResetCode
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest
)
from app.schemas.user import UserCreate, UserResponse
from app.schemas.password_reset import (
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    PasswordResetResponse
)
from app.services.session_service import SessionService
from app.services.email_service import EmailService
from app.services.system_event_service import SystemEventService

router = APIRouter(prefix="/auth", tags=["Authentication"])

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def _hash_reset_code(email: str, code: str) -> str:
    normalized = email.strip().lower()
    return hashlib.sha256(f"{normalized}:{code}:{settings.JWT_SECRET_KEY}".encode()).hexdigest()


def _get_user_by_email(db: Session, email: str) -> User | None:
    normalized = email.strip().lower()
    return db.query(User).filter(func.lower(User.email) == normalized).first()


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
    rate_key = f"{request.client.host}:{normalized_email}".lower()
    if not register_rate_limiter.allow(rate_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Çok fazla kayıt denemesi yaptınız. Lütfen daha sonra tekrar deneyin."
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
        full_name=user_data.full_name
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)

    EmailService.send_welcome_email(user.email, user.full_name)
    
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    request: Request,
    db: Session = Depends(get_db)
) -> TokenResponse:
    """
    Login and get access/refresh tokens.
    
    Args:
        credentials: Login credentials.
        db: Database session.
    
    Returns:
        Access and refresh tokens.
    """
    normalized_email = credentials.email.strip().lower()
    rate_key = f"{request.client.host}:{normalized_email}".lower()
    if not login_rate_limiter.allow(rate_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Çok fazla deneme yaptınız. Lütfen daha sonra tekrar deneyin."
        )

    # Find user by email
    user = _get_user_by_email(db, normalized_email)

    if user and user.locked_until and user.locked_until > datetime.utcnow():
        SystemEventService(db).log(
            tenant_id=None,
            source="auth",
            level="warn",
            code="AUTH_ACCOUNT_LOCKED",
            message="Login attempt for locked account",
            meta_json={"email": normalized_email, "ip": request.client.host if request.client else None},
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
                user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
            db.commit()
        SystemEventService(db).log(
            tenant_id=None,
            source="auth",
            level="warn",
            code="AUTH_LOGIN_FAILED",
            message="Invalid login attempt",
            meta_json={"email": normalized_email, "ip": request.client.host if request.client else None},
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
            meta_json={"email": normalized_email, "ip": request.client.host if request.client else None},
            correlation_id=None
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hesabınız devre dışı bırakıldı"
        )

    if user.failed_login_attempts or user.locked_until:
        user.failed_login_attempts = 0
        user.locked_until = None
    
    # Create tokens + session
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    session_service = SessionService(db)
    session = session_service.create_session(
        user_id=user.id,
        refresh_token=refresh_token,
        ip_address=request.client.host,
        user_agent=request.headers.get("User-Agent")
    )
    refresh_token = create_refresh_token(data={"sub": str(user.id)}, session_id=str(session.id))
    session_service.rotate_session(session, refresh_token)

    user.last_login = datetime.utcnow()
    db.commit()
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    token_data: RefreshTokenRequest,
    request: Request,
    db: Session = Depends(get_db)
) -> TokenResponse:
    """
    Refresh access token using refresh token.
    
    Args:
        token_data: Refresh token request.
        db: Database session.
    
    Returns:
        New access token.
    """
    rate_key = request.client.host if request.client else "unknown"
    if not refresh_rate_limiter.allow(rate_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Çok fazla token yenileme denemesi. Lütfen daha sonra tekrar deneyin."
        )
    payload = decode_token(token_data.refresh_token)
    
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
    refresh_token_value = token_data.refresh_token
    session_id = payload.get("sid")

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
        refresh_token_value = create_refresh_token(data={"sub": str(user.id)}, session_id=str(session.id))
        session_service.rotate_session(session, refresh_token_value)
    else:
        session = session_service.create_session(
            user_id=user.id,
            refresh_token=refresh_token_value
        )
        refresh_token_value = create_refresh_token(data={"sub": str(user.id)}, session_id=str(session.id))
        session_service.rotate_session(session, refresh_token_value)

    # Create new access token
    access_token = create_access_token(data={"sub": str(user.id)})
    
    return TokenResponse(access_token=access_token, refresh_token=refresh_token_value)


@router.post("/password-reset/request", response_model=PasswordResetResponse)
async def request_password_reset_code(
    payload: PasswordResetRequest,
    db: Session = Depends(get_db)
) -> PasswordResetResponse:
    message = "E-posta kayıtlıysa doğrulama kodu gönderildi."
    normalized_email = payload.email.strip().lower()
    user = _get_user_by_email(db, normalized_email)
    if not user or not user.is_active:
        return PasswordResetResponse(success=True, message=message)

    now = datetime.utcnow()
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


@router.post("/password-reset/confirm", response_model=PasswordResetResponse)
async def confirm_password_reset(
    payload: PasswordResetConfirmRequest,
    db: Session = Depends(get_db)
) -> PasswordResetResponse:
    normalized_email = payload.email.strip().lower()
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

    now = datetime.utcnow()
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
