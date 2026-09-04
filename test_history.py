"""Tests for role-based access control and the /history endpoint."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models import DetectionHistory, User
from auth import hash_password
from main import app, get_db, create_access_token

# --------------- test database setup ---------------

SQLALCHEMY_TEST_URL = "sqlite:///./test_history.db"

test_engine = create_engine(
    SQLALCHEMY_TEST_URL,
    connect_args={"check_same_thread": False},
)

TestSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


# --------------- fixtures ---------------


@pytest.fixture(autouse=True)
def setup_db():
    """Create tables before each test, drop them after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


def _create_user(username, email, role="user"):
    """Helper: insert a user and return (user, token)."""
    db = TestSessionLocal()
    user = User(
        full_name=f"{username} name",
        username=username,
        email=email,
        password=hash_password("password123"),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.username)
    db.close()
    return user, token


@pytest.fixture()
def regular_user():
    return _create_user("testuser", "test@example.com", role="user")


@pytest.fixture()
def admin_user():
    return _create_user("adminuser", "admin@example.com", role="admin")


@pytest.fixture()
def seed_detections(regular_user):
    """Insert detection history rows for the regular user."""
    user, token = regular_user
    db = TestSessionLocal()
    for i in range(5):
        db.add(
            DetectionHistory(
                claim=f"Test claim {i}",
                verdict="LIKELY_FAKE",
                confidence=90 + i,
                explanation=f"Explanation {i}",
                user_id=user.id,
            )
        )
    db.commit()
    db.close()
    return user, token


# =============================================
# HISTORY ENDPOINT TESTS
# =============================================


def test_history_requires_auth():
    """GET /history without a token should return 401."""
    response = client.get("/history")
    assert response.status_code == 401


def test_history_empty(regular_user):
    """Authenticated user with no detections gets an empty list."""
    _user, token = regular_user
    response = client.get(
        "/history",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json() == []


def test_history_returns_detections(seed_detections):
    """Authenticated user sees their detection history, newest first."""
    user, token = seed_detections
    response = client.get(
        "/history",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 5
    assert data[0]["claim"] == "Test claim 4"
    assert data[-1]["claim"] == "Test claim 0"


def test_history_limit(seed_detections):
    """?limit=2 returns only 2 records."""
    _user, token = seed_detections
    response = client.get(
        "/history?limit=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_history_isolation(seed_detections):
    """A different user should not see another user's history."""
    _other, other_token = _create_user(
        "otheruser", "other@example.com", role="user"
    )
    response = client.get(
        "/history",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert response.status_code == 200
    assert response.json() == []


# =============================================
# PROFILE ENDPOINT TESTS
# =============================================


def test_profile_returns_role(regular_user):
    """Profile response includes the user's role."""
    _user, token = regular_user
    response = client.get(
        "/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["role"] == "user"


def test_profile_admin(admin_user):
    """Admin can also access /profile."""
    _user, token = admin_user
    response = client.get(
        "/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


# =============================================
# RBAC TESTS — ADMIN ENDPOINTS
# =============================================


def test_admin_users_forbidden_for_regular_user(regular_user):
    """Regular user cannot access /admin/users."""
    _user, token = regular_user
    response = client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert "permission" in response.json()["detail"].lower()


def test_admin_users_allowed_for_admin(admin_user):
    """Admin can list all users."""
    _user, token = admin_user
    response = client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(u["username"] == "adminuser" for u in data)


def test_admin_detections_forbidden_for_regular_user(regular_user):
    """Regular user cannot access /admin/detections."""
    _user, token = regular_user
    response = client.get(
        "/admin/detections",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_admin_detections_allowed_for_admin(admin_user, seed_detections):
    """Admin can see all detections across users."""
    _admin, admin_token = admin_user
    response = client.get(
        "/admin/detections",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 5


def test_admin_endpoints_require_auth():
    """Admin endpoints return 401 without a token."""
    assert client.get("/admin/users").status_code == 401
    assert client.get("/admin/detections").status_code == 401
