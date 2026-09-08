import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS,
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES,
)
from database import SessionLocal
from models import (
    EmailVerificationToken,
    PasswordResetToken,
    RevokedToken,
    User,
)
from auth.dependencies import (
    get_current_active_user,
    get_current_user,
    get_db,
    security_bearer,
)
from auth.email_service import get_email_service
from auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
    is_token_revoked,
    revoke_token,
)
from auth.password import hash_password, verify_password
from auth.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    MessageResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    RequestEmailVerificationRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
    VerifyEmailRequest,
)

router = APIRouter(
    prefix="/auth",
    tags=["User Authentication"],
)


# -----------------------------------------------------------------------------
# 1. Registration Endpoint
# -----------------------------------------------------------------------------
@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
def register(
    data: UserRegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Registers a new user:
    - Validates email and strong password
    - Ensures email is unique
    - Hashes password securely
    - Sets role to 'user' by default
    - Returns safe user representation
    """
    existing_user = db.query(User).filter(User.email == data.email.lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered",
        )

    new_user = User(
        full_name=data.full_name.strip(),
        email=data.email.lower().strip(),
        hashed_password=hash_password(data.password),
        role="user",
        is_active=True,
        is_verified=False,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


# -----------------------------------------------------------------------------
# 2. Login Endpoint
# -----------------------------------------------------------------------------
@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in and obtain JWT access & refresh tokens",
)
def login(
    data: UserLoginRequest,
    db: Session = Depends(get_db),
):
    """
    Authenticates user with email and password:
    - Constant-time/secure password verification
    - Generic error response to prevent user enumeration
    - Rejects inactive accounts
    - Returns JWT access token and refresh token
    """
    user = db.query(User).filter(User.email == data.email.lower().strip()).first()

    if user is None or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account. Please contact support.",
        )

    access_token, _, access_expires_in = create_access_token(
        user_id=user.id,
        role=user.role,
    )
    refresh_token, _, _ = create_refresh_token(user_id=user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=access_expires_in,
    )


# -----------------------------------------------------------------------------
# 3. Current Logged-in User Profile
# -----------------------------------------------------------------------------
@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get safe profile of the currently logged-in user",
)
def get_me(
    current_user: User = Depends(get_current_active_user),
):
    """
    Returns the authenticated user's safe profile details.
    Password and internal secrets are excluded.
    """
    return current_user


# -----------------------------------------------------------------------------
# 4. Token Refresh Endpoint
# -----------------------------------------------------------------------------
@router.post(
    "/refresh",
    response_model=RefreshTokenResponse,
    summary="Generate a new access token using a valid refresh token",
)
def refresh_token_endpoint(
    data: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    """
    Validates a JWT refresh token and returns a fresh access token.
    Rejects access tokens, expired tokens, or revoked tokens.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid, expired, or revoked refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_token(data.refresh_token)
    if payload is None:
        raise credentials_exception

    if payload.get("type") != "refresh":
        raise credentials_exception

    jti = payload.get("jti")
    if jti and is_token_revoked(db, jti):
        raise credentials_exception

    user_id = payload.get("user_id") or payload.get("sub")
    if user_id is None:
        raise credentials_exception

    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id_int).first()
    if user is None or not user.is_active:
        raise credentials_exception

    new_access_token, _, access_expires_in = create_access_token(
        user_id=user.id,
        role=user.role,
    )

    return RefreshTokenResponse(
        access_token=new_access_token,
        token_type="bearer",
        expires_in=access_expires_in,
    )


# -----------------------------------------------------------------------------
# 5. Logout Endpoint
# -----------------------------------------------------------------------------
@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Log out by revoking current JWT access and/or refresh token",
)
def logout(
    refresh_body: Optional[RefreshTokenRequest] = None,
    current_user: User = Depends(get_current_user),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Logs out the user by blacklisting the current access token's JTI.
    Optionally revokes the provided refresh token as well.
    """
    # Revoke access token from Authorization header if present
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        payload = decode_token(token)
        if payload and payload.get("jti"):
            exp = payload.get("exp")
            expires_at = (
                datetime.fromtimestamp(exp, tz=timezone.utc)
                if exp
                else None
            )
            revoke_token(
                db=db,
                jti=payload["jti"],
                token_type=payload.get("type", "access"),
                user_id=current_user.id,
                expires_at=expires_at,
            )

    # Revoke optional refresh token from request body
    if refresh_body and refresh_body.refresh_token:
        refresh_payload = decode_token(refresh_body.refresh_token)
        if refresh_payload and refresh_payload.get("jti"):
            exp = refresh_payload.get("exp")
            expires_at = (
                datetime.fromtimestamp(exp, tz=timezone.utc)
                if exp
                else None
            )
            revoke_token(
                db=db,
                jti=refresh_payload["jti"],
                token_type="refresh",
                user_id=current_user.id,
                expires_at=expires_at,
            )

    return MessageResponse(
        message="Successfully logged out and tokens revoked.",
    )


# -----------------------------------------------------------------------------
# 6. Forgot Password Endpoint
# -----------------------------------------------------------------------------
@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request a password reset link/token",
)
def forgot_password(
    data: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    """
    Initiates password reset process:
    - Generates short-lived reset token if email exists
    - Dispatches email instruction
    - Returns generic success response always to prevent email enumeration
    """
    user = db.query(User).filter(User.email == data.email.lower().strip()).first()
    if user and user.is_active:
        reset_token_str = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
        )

        reset_record = PasswordResetToken(
            user_id=user.id,
            token=reset_token_str,
            expires_at=expires_at,
            used=False,
        )
        db.add(reset_record)
        db.commit()

        email_svc = get_email_service()
        email_svc.send_password_reset_email(user.email, reset_token_str)

    return MessageResponse(
        message="If this email is registered, password reset instructions have been sent.",
    )


# -----------------------------------------------------------------------------
# 7. Reset Password Endpoint
# -----------------------------------------------------------------------------
@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password using a valid reset token",
)
def reset_password(
    data: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """
    Resets user password:
    - Verifies token validity and expiration
    - Enforces strong password rules
    - Hashes new password and marks token as used
    """
    now = datetime.now(timezone.utc)
    token_record = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token == data.token,
            PasswordResetToken.used.is_(False),
            PasswordResetToken.expires_at > now,
        )
        .first()
    )

    if token_record is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token",
        )

    user = db.query(User).filter(User.id == token_record.user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found",
        )

    user.hashed_password = hash_password(data.new_password)
    token_record.used = True
    db.commit()

    return MessageResponse(
        message="Password has been successfully reset. You may now log in with your new password.",
    )


# -----------------------------------------------------------------------------
# 8. Change Password Endpoint
# -----------------------------------------------------------------------------
@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="Change password for the currently authenticated user",
)
def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Allows authenticated user to change their password:
    - Verifies existing password
    - Validates new password complexity
    - Updates stored password hash
    """
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password",
        )

    current_user.hashed_password = hash_password(data.new_password)
    db.commit()

    return MessageResponse(
        message="Password updated successfully.",
    )


# -----------------------------------------------------------------------------
# 9. Request Email Verification Endpoint
# -----------------------------------------------------------------------------
@router.post(
    "/request-email-verification",
    response_model=MessageResponse,
    summary="Request a new email verification link/token",
)
def request_email_verification(
    data: RequestEmailVerificationRequest,
    db: Session = Depends(get_db),
):
    """
    Generates an email verification token if the email exists and is unverified.
    Always returns generic response to prevent email enumeration.
    """
    user = db.query(User).filter(User.email == data.email.lower().strip()).first()
    if user and not user.is_verified:
        verify_token_str = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(
            hours=EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS
        )

        verify_record = EmailVerificationToken(
            user_id=user.id,
            token=verify_token_str,
            expires_at=expires_at,
            used=False,
        )
        db.add(verify_record)
        db.commit()

        email_svc = get_email_service()
        email_svc.send_verification_email(user.email, verify_token_str)

    return MessageResponse(
        message="If this email is registered and unverified, verification instructions have been sent.",
    )


# -----------------------------------------------------------------------------
# 10. Verify Email Endpoint
# -----------------------------------------------------------------------------
@router.post(
    "/verify-email",
    response_model=MessageResponse,
    summary="Verify user email address using verification token",
)
def verify_email(
    data: VerifyEmailRequest,
    db: Session = Depends(get_db),
):
    """
    Marks user account as verified if the token is valid and unexpired.
    """
    now = datetime.now(timezone.utc)
    token_record = (
        db.query(EmailVerificationToken)
        .filter(
            EmailVerificationToken.token == data.token,
            EmailVerificationToken.used.is_(False),
            EmailVerificationToken.expires_at > now,
        )
        .first()
    )

    if token_record is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired email verification token",
        )

    user = db.query(User).filter(User.id == token_record.user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found",
        )

    user.is_verified = True
    token_record.used = True
    db.commit()

    return MessageResponse(
        message="Email successfully verified.",
    )

