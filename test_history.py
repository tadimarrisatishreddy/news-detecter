"""Tests for role-based access control and the /history endpoint."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models import Analysis, DetectionHistory, User
from auth import hash_password
from main import app, get_db, create_access_token

from sqlalchemy.pool import StaticPool

# --------------- test database setup ---------------

SQLALCHEMY_TEST_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_TEST_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
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


client = TestClient(app)


# --------------- fixtures ---------------


@pytest.fixture(autouse=True)
def setup_db():
    """Create tables before each test, drop them after."""
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.clear()


def _create_user(username, email, role="user"):
    """Helper: insert a user and return (user, token)."""
    db = TestSessionLocal()
    user = User(
        full_name=f"{username} name",
        username=username,
        email=email,
        hashed_password=hash_password("password123"),
        role=role,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user_id=user.id, role=user.role)
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


# =============================================
# ANALYSIS ENDPOINT TESTS
# =============================================

VALID_INPUT = "This is a test news claim that is long enough to pass the twenty character minimum."


def test_create_analysis_requires_auth():
    """POST /analyses without a token returns 401."""
    response = client.post("/analyses", json={"input_text": VALID_INPUT})
    assert response.status_code == 401


def test_create_analysis_success(regular_user):
    """Authenticated user can create an analysis, gets 201 with all fields."""
    _user, token = regular_user
    response = client.post(
        "/analyses",
        json={"input_text": VALID_INPUT},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["input_text"] == VALID_INPUT
    assert data["source_url"] is None
    assert data["status"] == "completed"
    assert data["verdict"] is not None
    assert data["confidence"] is not None
    assert data["explanation"] is not None
    assert data["error_message"] is None
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_analysis_short_text(regular_user):
    """Input text shorter than 20 chars is rejected with 422."""
    _user, token = regular_user
    response = client.post(
        "/analyses",
        json={"input_text": "Too short"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


def test_create_analysis_with_source_url(regular_user):
    """source_url is stored and returned when provided."""
    _user, token = regular_user
    response = client.post(
        "/analyses",
        json={
            "input_text": VALID_INPUT,
            "source_url": "https://example.com/article",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    assert response.json()["source_url"] == "https://example.com/article"


def test_create_analysis_without_source_url(regular_user):
    """source_url defaults to null when omitted."""
    _user, token = regular_user
    response = client.post(
        "/analyses",
        json={"input_text": VALID_INPUT},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    assert response.json()["source_url"] is None


def test_list_analyses_empty(regular_user):
    """User with no analyses gets an empty list."""
    _user, token = regular_user
    response = client.get(
        "/analyses",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json() == []


def test_list_analyses_returns_own(regular_user):
    """User sees their own analyses."""
    _user, token = regular_user
    # Create two analyses
    for _ in range(2):
        client.post(
            "/analyses",
            json={"input_text": VALID_INPUT},
            headers={"Authorization": f"Bearer {token}"},
        )
    response = client.get(
        "/analyses",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_analyses_isolation(regular_user):
    """User B cannot see User A's analyses."""
    _user_a, token_a = regular_user
    client.post(
        "/analyses",
        json={"input_text": VALID_INPUT},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    _user_b, token_b = _create_user("userb", "b@example.com", role="user")
    response = client.get(
        "/analyses",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 200
    assert response.json() == []


def test_list_analyses_limit(regular_user):
    """?limit=1 returns only 1 record."""
    _user, token = regular_user
    for _ in range(3):
        client.post(
            "/analyses",
            json={"input_text": VALID_INPUT},
            headers={"Authorization": f"Bearer {token}"},
        )
    response = client.get(
        "/analyses?limit=1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_get_analysis_by_id(regular_user):
    """GET /analyses/{id} returns the correct analysis."""
    _user, token = regular_user
    create_resp = client.post(
        "/analyses",
        json={"input_text": VALID_INPUT},
        headers={"Authorization": f"Bearer {token}"},
    )
    analysis_id = create_resp.json()["id"]

    response = client.get(
        f"/analyses/{analysis_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["id"] == analysis_id
    assert response.json()["input_text"] == VALID_INPUT


def test_get_analysis_not_found(regular_user):
    """GET /analyses/99999 returns 404."""
    _user, token = regular_user
    response = client.get(
        "/analyses/99999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def test_get_analysis_forbidden_for_other_user(regular_user):
    """User B gets 404 (not 403) for User A's analysis."""
    _user_a, token_a = regular_user
    create_resp = client.post(
        "/analyses",
        json={"input_text": VALID_INPUT},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    analysis_id = create_resp.json()["id"]

    _user_b, token_b = _create_user("userc", "c@example.com", role="user")
    response = client.get(
        f"/analyses/{analysis_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 404


def test_admin_can_see_any_analysis(regular_user, admin_user):
    """Admin can view any user's analysis by ID."""
    _user, user_token = regular_user
    create_resp = client.post(
        "/analyses",
        json={"input_text": VALID_INPUT},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    analysis_id = create_resp.json()["id"]

    _admin, admin_token = admin_user
    response = client.get(
        f"/analyses/{analysis_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert response.json()["id"] == analysis_id


def test_admin_list_all_analyses(regular_user, admin_user):
    """GET /admin/analyses returns analyses from all users."""
    _user, user_token = regular_user
    client.post(
        "/analyses",
        json={"input_text": VALID_INPUT},
        headers={"Authorization": f"Bearer {user_token}"},
    )

    _admin, admin_token = admin_user
    client.post(
        "/analyses",
        json={"input_text": VALID_INPUT},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    response = client.get(
        "/admin/analyses",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # Admin endpoint includes user_id
    assert "user_id" in data[0]
