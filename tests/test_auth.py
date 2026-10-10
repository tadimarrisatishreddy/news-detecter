import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from models import EmailVerificationToken, PasswordResetToken, RevokedToken, User
from auth.dependencies import get_db
from auth.jwt import create_access_token, create_refresh_token
from auth.password import hash_password
from main import app

# In-memory SQLite with StaticPool so all connections share the same in-memory DB
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    """Create all tables before each test and drop them afterwards."""
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.clear()


def create_test_user(
    email: str = "john.doe@example.com",
    full_name: str = "John Doe",
    password: str = "StrongPass123!",
    role: str = "user",
    is_active: bool = True,
    is_verified: bool = False,
) -> User:
    """Helper to insert a user into the test database."""
    db = TestingSessionLocal()
    user = User(
        full_name=full_name,
        email=email.lower().strip(),
        hashed_password=hash_password(password),
        role=role,
        is_active=is_active,
        is_verified=is_verified,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


# =============================================================================
# 1. Registration Tests
# =============================================================================

def test_successful_registration():
    """Valid user registration returns 201 and safe user profile."""
    payload = {
        "full_name": "Alice Smith",
        "email": "alice@example.com",
        "password": "ValidPassword123!",
        "confirm_password": "ValidPassword123!",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["full_name"] == "Alice Smith"
    assert data["email"] == "alice@example.com"
    assert data["role"] == "user"
    assert data["is_active"] is True
    assert data["is_verified"] is False
    assert "id" in data
    assert "created_at" in data
    # Ensure no passwords leaked
    assert "password" not in data
    assert "hashed_password" not in data

def test_successful_registration_with_password_confirm_alias():
    """Registration works when client sends password_confirm field name."""
    payload = {
        "full_name": "Bob Alias",
        "email": "bob.alias@example.com",
        "password": "ValidPassword123!",
        "password_confirm": "ValidPassword123!",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "bob.alias@example.com"


def test_duplicate_email_registration_rejected():
    """Duplicate email registration must return 400 Bad Request."""
    create_test_user(email="alice@example.com")
    payload = {
        "full_name": "Alice Duplicate",
        "email": "alice@example.com",
        "password": "ValidPassword123!",
        "confirm_password": "ValidPassword123!",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()


def test_invalid_email_registration_rejected():
    """Malformed email must be rejected with 422 Unprocessable Entity."""
    payload = {
        "full_name": "Bad Email",
        "email": "not-an-email",
        "password": "ValidPassword123!",
        "confirm_password": "ValidPassword123!",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 422


@pytest.mark.parametrize(
    "weak_password,expected_error",
    [
        ("short1!", "8 characters"),
        ("lowercase123!", "uppercase letter"),
        ("UPPERCASE123!", "lowercase letter"),
        ("NoNumbersHere!", "number"),
        ("NoSpecialChar123", "special character"),
    ],
)
def test_weak_password_registration_rejected(weak_password, expected_error):
    """Weak passwords that violate complexity requirements are rejected with 422."""
    payload = {
        "full_name": "Weak Pass User",
        "email": "weak@example.com",
        "password": weak_password,
        "confirm_password": weak_password,
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 422
    assert expected_error.lower() in str(response.json()).lower()


def test_password_confirmation_mismatch_rejected():
    """Mismatched confirm_password must be rejected with 422."""
    payload = {
        "full_name": "Mismatch User",
        "email": "mismatch@example.com",
        "password": "ValidPassword123!",
        "confirm_password": "DifferentPassword123!",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 422
    assert "Passwords do not match" in str(response.json())


# =============================================================================
# 2. Login Tests
# =============================================================================

def test_successful_login():
    """Valid credentials return JWT access token, refresh token, and metadata."""
    create_test_user(email="bob@example.com", password="StrongPassword123!")
    response = client.post(
        "/auth/login",
        json={"email": "bob@example.com", "password": "StrongPassword123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0
    # No credentials leaked
    assert "password" not in data
    assert "hashed_password" not in data


def test_invalid_login_wrong_password():
    """Wrong password returns 401 Unauthorized with generic message."""
    create_test_user(email="bob@example.com", password="StrongPassword123!")
    response = client.post(
        "/auth/login",
        json={"email": "bob@example.com", "password": "WrongPassword123!"},
    )
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]


def test_invalid_login_nonexistent_email():
    """Non-existing email returns 401 Unauthorized with same generic message."""
    response = client.post(
        "/auth/login",
        json={"email": "unknown@example.com", "password": "AnyPassword123!"},
    )
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]


def test_inactive_user_login_rejected():
    """Inactive account login is rejected with 403 Forbidden."""
    create_test_user(
        email="inactive@example.com",
        password="StrongPassword123!",
        is_active=False,
    )
    response = client.post(
        "/auth/login",
        json={"email": "inactive@example.com", "password": "StrongPassword123!"},
    )
    assert response.status_code == 403
    assert "inactive" in response.json()["detail"].lower()


# =============================================================================
# 3. Protected Route & GET /auth/me Tests
# =============================================================================

def test_get_me_unauthenticated():
    """GET /auth/me without Bearer token returns 401."""
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_get_me_invalid_token():
    """GET /auth/me with invalid Bearer token returns 401."""
    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid.jwt.token"},
    )
    assert response.status_code == 401


def test_get_me_success():
    """GET /auth/me with valid Bearer token returns user's safe profile."""
    user = create_test_user(email="me@example.com", full_name="Me User")
    token, _, _ = create_access_token(user_id=user.id, role=user.role)

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user.id
    assert data["full_name"] == "Me User"
    assert data["email"] == "me@example.com"
    assert data["role"] == "user"
    assert data["is_active"] is True
    assert data["is_verified"] is False
    assert "created_at" in data
    assert "password" not in data
    assert "hashed_password" not in data


# =============================================================================
# 4. Token Refresh Tests
# =============================================================================

def test_refresh_token_success():
    """Valid refresh token generates a new access token."""
    user = create_test_user(email="refresh@example.com")
    refresh_token, _, _ = create_refresh_token(user_id=user.id)

    response = client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0

    # Verify that the new access token can access /auth/me
    me_resp = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert me_resp.status_code == 200


def test_access_token_rejected_as_refresh_token():
    """An access token cannot be used in place of a refresh token."""
    user = create_test_user(email="refresh_bad@example.com")
    access_token, _, _ = create_access_token(user_id=user.id)

    response = client.post(
        "/auth/refresh",
        json={"refresh_token": access_token},
    )
    assert response.status_code == 401


def test_invalid_refresh_token():
    """Invalid string as refresh token returns 401."""
    response = client.post(
        "/auth/refresh",
        json={"refresh_token": "not-a-valid-token"},
    )
    assert response.status_code == 401


# =============================================================================
# 5. Logout & Token Blacklist Tests
# =============================================================================

def test_logout_revokes_token():
    """Logging out revokes the access token so it can no longer be used."""
    user = create_test_user(email="logout@example.com")
    access_token, _, _ = create_access_token(user_id=user.id)

    # Confirm token is currently valid
    check_before = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert check_before.status_code == 200

    # Logout
    logout_resp = client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert logout_resp.status_code == 200

    # Access token must now be rejected
    check_after = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert check_after.status_code == 401
    assert "revoked" in check_after.json()["detail"].lower()


# =============================================================================
# 6. Forgot & Reset Password Tests
# =============================================================================

def test_forgot_password_generic_response():
    """POST /auth/forgot-password returns generic message for both existing & non-existing emails."""
    create_test_user(email="exists@example.com")

    resp1 = client.post(
        "/auth/forgot-password",
        json={"email": "exists@example.com"},
    )
    assert resp1.status_code == 200
    assert "If this email is registered" in resp1.json()["message"]

    resp2 = client.post(
        "/auth/forgot-password",
        json={"email": "notexists@example.com"},
    )
    assert resp2.status_code == 200
    assert resp1.json()["message"] == resp2.json()["message"]


def test_reset_password_success():
    """Valid reset token allows changing password and logging in with new password."""
    user = create_test_user(email="resetpass@example.com", password="OldPassword123!")

    # Request forgot password to generate token
    client.post(
        "/auth/forgot-password",
        json={"email": "resetpass@example.com"},
    )

    db = TestingSessionLocal()
    token_record = db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).first()
    reset_token = token_record.token
    db.close()

    # Reset password
    reset_resp = client.post(
        "/auth/reset-password",
        json={
            "token": reset_token,
            "new_password": "NewStrongPassword456!",
            "confirm_password": "NewStrongPassword456!",
        },
    )
    assert reset_resp.status_code == 200

    # Login with old password fails
    old_login = client.post(
        "/auth/login",
        json={"email": "resetpass@example.com", "password": "OldPassword123!"},
    )
    assert old_login.status_code == 401

    # Login with new password succeeds
    new_login = client.post(
        "/auth/login",
        json={"email": "resetpass@example.com", "password": "NewStrongPassword456!"},
    )
    assert new_login.status_code == 200


def test_reset_password_invalid_or_used_token():
    """Used or invalid reset token is rejected with 400."""
    response = client.post(
        "/auth/reset-password",
        json={
            "token": "invalid-reset-token",
            "new_password": "NewStrongPassword456!",
            "confirm_password": "NewStrongPassword456!",
        },
    )
    assert response.status_code == 400
    assert "Invalid or expired" in response.json()["detail"]


# =============================================================================
# 7. Change Password Tests
# =============================================================================

def test_change_password_success():
    """Authenticated user can change password with correct current password."""
    user = create_test_user(email="change@example.com", password="InitialPassword123!")
    token, _, _ = create_access_token(user_id=user.id)

    response = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "InitialPassword123!",
            "new_password": "BrandNewPassword789!",
            "confirm_password": "BrandNewPassword789!",
        },
    )
    assert response.status_code == 200

    # Verify login works with new password
    login_resp = client.post(
        "/auth/login",
        json={"email": "change@example.com", "password": "BrandNewPassword789!"},
    )
    assert login_resp.status_code == 200


def test_change_password_incorrect_current():
    """Incorrect current password returns 400 Bad Request."""
    user = create_test_user(email="change_bad@example.com", password="InitialPassword123!")
    token, _, _ = create_access_token(user_id=user.id)

    response = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "WrongCurrentPassword123!",
            "new_password": "BrandNewPassword789!",
            "confirm_password": "BrandNewPassword789!",
        },
    )
    assert response.status_code == 400
    assert "Incorrect current password" in response.json()["detail"]


# =============================================================================
# 8. Email Verification Tests
# =============================================================================

def test_request_email_verification_and_verify_success():
    """User can request email verification token and verify their account."""
    user = create_test_user(email="verify@example.com", is_verified=False)

    # Request verification
    req_resp = client.post(
        "/auth/request-email-verification",
        json={"email": "verify@example.com"},
    )
    assert req_resp.status_code == 200

    # Retrieve verification token from test DB
    db = TestingSessionLocal()
    token_record = db.query(EmailVerificationToken).filter(EmailVerificationToken.user_id == user.id).first()
    verify_token = token_record.token
    db.close()

    # Verify email
    ver_resp = client.post(
        "/auth/verify-email",
        json={"token": verify_token},
    )
    assert ver_resp.status_code == 200
    assert "successfully verified" in ver_resp.json()["message"]

    # Check updated user
    db = TestingSessionLocal()
    updated_user = db.query(User).filter(User.id == user.id).first()
    assert updated_user.is_verified is True
    db.close()


def test_verify_email_invalid_token():
    """Invalid verification token is rejected with 400."""
    response = client.post(
        "/auth/verify-email",
        json={"token": "invalid-token-12345"},
    )
    assert response.status_code == 400
    assert "Invalid or expired" in response.json()["detail"]

