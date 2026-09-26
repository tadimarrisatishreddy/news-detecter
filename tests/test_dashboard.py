"""
tests/test_dashboard.py
=======================
Module 5 – Dashboard & Reports test suite.

Covers:
- User dashboard  (GET /dashboard/me)
- User report     (GET /dashboard/me/report)
- Admin dashboard (GET /dashboard/admin)
- Admin report    (GET /dashboard/admin/report)
- Admin users     (GET /dashboard/admin/users)
- Auth & role guards on every endpoint
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from main import app, create_access_token
from auth import get_db
from models import DetectionHistory, FactCheckRecord, NewsSubmission, User
from auth.password import hash_password


# ---------------------------------------------------------------------------
# In-memory database fixture
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite://"

engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers – create seeded users and data
# ---------------------------------------------------------------------------

def _make_user(db, email: str, role: str = "user", full_name: str = "Test User") -> User:
    user = User(
        full_name=full_name,
        username=email.split("@")[0],
        email=email,
        hashed_password=hash_password("Password1!"),
        role=role,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _seed_detections(db, user: User, count: int = 3):
    verdicts = ["LIKELY_FAKE", "LIKELY_REAL", "UNCERTAIN"]
    for i in range(count):
        db.add(DetectionHistory(
            user_id=user.id,
            claim=f"Test claim number {i}",
            verdict=verdicts[i % len(verdicts)],
            confidence=round(0.6 + i * 0.1, 2),
            explanation="Test explanation",
        ))
    db.commit()


def _seed_fact_checks(db, user: User, count: int = 2):
    statuses = ["VERIFIED", "REFUTED"]
    for i in range(count):
        db.add(FactCheckRecord(
            user_id=user.id,
            claim=f"Fact check claim {i}",
            status=statuses[i % len(statuses)],
            verdict="TRUE" if statuses[i % len(statuses)] == "VERIFIED" else "FALSE",
            trust_score=75.0 - i * 10,
            summary="Test summary",
        ))
    db.commit()


def _seed_submissions(db, user: User, count: int = 2):
    for i in range(count):
        db.add(NewsSubmission(
            user_id=user.id,
            title=f"News article {i}",
            raw_text="Some raw text content here.",
            cleaned_text="cleaned text",
            word_count=50 + i * 10,
            char_count=300,
            sentence_count=5,
            reading_ease_score=60.0,
            sensationalism_score=round(0.2 + i * 0.1, 2),
            lexical_diversity=0.75,
        ))
    db.commit()


# ---------------------------------------------------------------------------
# Test: User Dashboard (GET /dashboard/me)
# ---------------------------------------------------------------------------

class TestUserDashboard:
    def test_unauthenticated_rejected(self, client):
        resp = client.get("/dashboard/me")
        assert resp.status_code == 401

    def test_empty_dashboard_for_new_user(self, client, db):
        user = _make_user(db, "dash_empty@example.com")
        token = create_access_token(user.id, role="user")

        resp = client.get("/dashboard/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

        data = resp.json()
        assert data["user_id"] == user.id
        assert data["total_detections"] == 0
        assert data["total_fact_checks"] == 0
        assert data["total_submissions"] == 0
        assert data["avg_detection_confidence"] == 0.0
        assert data["avg_trust_score"] == 0.0
        assert data["recent_detections"] == []

    def test_dashboard_with_data(self, client, db):
        user = _make_user(db, "dash_data@example.com")
        _seed_detections(db, user, count=3)
        _seed_fact_checks(db, user, count=2)
        _seed_submissions(db, user, count=2)

        token = create_access_token(user.id, role="user")
        resp = client.get("/dashboard/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

        data = resp.json()
        assert data["total_detections"] == 3
        assert data["total_fact_checks"] == 2
        assert data["total_submissions"] == 2
        assert 0.0 <= data["avg_detection_confidence"] <= 1.0
        assert 0.0 <= data["avg_trust_score"] <= 100.0

    def test_verdict_breakdown_structure(self, client, db):
        user = _make_user(db, "dash_verdict@example.com")
        _seed_detections(db, user, count=3)

        token = create_access_token(user.id, role="user")
        resp = client.get("/dashboard/me", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()

        breakdown = data["verdict_breakdown"]
        assert "LIKELY_FAKE" in breakdown
        assert "LIKELY_REAL" in breakdown
        assert "UNCERTAIN" in breakdown
        # 3 detections across 3 verdict types → each should be 1
        total = sum(breakdown.values())
        assert total == 3

    def test_fact_check_breakdown_structure(self, client, db):
        user = _make_user(db, "dash_fc@example.com")
        _seed_fact_checks(db, user, count=2)

        token = create_access_token(user.id, role="user")
        resp = client.get("/dashboard/me", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()

        breakdown = data["fact_check_breakdown"]
        assert "VERIFIED" in breakdown
        assert "REFUTED" in breakdown
        assert breakdown["VERIFIED"] + breakdown["REFUTED"] == 2

    def test_recent_activity_capped_at_five(self, client, db):
        user = _make_user(db, "dash_recent@example.com")
        _seed_detections(db, user, count=8)

        token = create_access_token(user.id, role="user")
        resp = client.get("/dashboard/me", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()

        # Should return at most 5 recent detections
        assert len(data["recent_detections"]) <= 5

    def test_dashboard_data_isolated_between_users(self, client, db):
        user_a = _make_user(db, "dash_iso_a@example.com")
        user_b = _make_user(db, "dash_iso_b@example.com")
        _seed_detections(db, user_a, count=5)

        token_b = create_access_token(user_b.id, role="user")
        resp = client.get("/dashboard/me", headers={"Authorization": f"Bearer {token_b}"})
        data = resp.json()
        assert data["total_detections"] == 0  # user_b sees only their own


# ---------------------------------------------------------------------------
# Test: User Report (GET /dashboard/me/report)
# ---------------------------------------------------------------------------

class TestUserReport:
    def test_unauthenticated_rejected(self, client):
        resp = client.get("/dashboard/me/report")
        assert resp.status_code == 401

    def test_empty_report(self, client, db):
        user = _make_user(db, "report_empty@example.com")
        token = create_access_token(user.id, role="user")

        resp = client.get("/dashboard/me/report", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

        data = resp.json()
        assert data["user_id"] == user.id
        assert data["detection_count"] == 0
        assert data["detections"] == []
        assert data["report_period"] == "all-time"

    def test_report_with_data(self, client, db):
        user = _make_user(db, "report_data@example.com")
        _seed_detections(db, user, count=4)
        _seed_fact_checks(db, user, count=3)
        _seed_submissions(db, user, count=2)

        token = create_access_token(user.id, role="user")
        resp = client.get("/dashboard/me/report", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()

        assert data["detection_count"] == 4
        assert data["fact_check_count"] == 3
        assert data["submission_count"] == 2
        assert len(data["detections"]) == 4
        assert len(data["fact_checks"]) == 3
        assert len(data["submissions"]) == 2


# ---------------------------------------------------------------------------
# Test: Admin Dashboard (GET /dashboard/admin)
# ---------------------------------------------------------------------------

class TestAdminDashboard:
    def test_unauthenticated_rejected(self, client):
        resp = client.get("/dashboard/admin")
        assert resp.status_code == 401

    def test_regular_user_forbidden(self, client, db):
        user = _make_user(db, "admin_forbidden@example.com", role="user")
        token = create_access_token(user.id, role="user")

        resp = client.get("/dashboard/admin", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_admin_can_access(self, client, db):
        admin = _make_user(db, "admin_ok@example.com", role="admin", full_name="Admin User")
        token = create_access_token(admin.id, role="admin")

        resp = client.get("/dashboard/admin", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

        data = resp.json()
        assert "total_users" in data
        assert "total_detections" in data
        assert "global_verdict_breakdown" in data
        assert "global_fact_check_breakdown" in data
        assert "most_active_users" in data
        assert "top_flagged_claims" in data

    def test_admin_stats_reflect_all_users(self, client, db):
        admin = _make_user(db, "admin_stats@example.com", role="admin", full_name="Stats Admin")
        u1 = _make_user(db, "stats_u1@example.com")
        u2 = _make_user(db, "stats_u2@example.com")
        _seed_detections(db, u1, count=3)
        _seed_detections(db, u2, count=2)

        token = create_access_token(admin.id, role="admin")
        resp = client.get("/dashboard/admin", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()

        # total detections should include data from all users
        assert data["total_detections"] >= 5


# ---------------------------------------------------------------------------
# Test: Admin Report (GET /dashboard/admin/report)
# ---------------------------------------------------------------------------

class TestAdminReport:
    def test_regular_user_forbidden(self, client, db):
        user = _make_user(db, "rpt_forbidden@example.com", role="user")
        token = create_access_token(user.id, role="user")

        resp = client.get("/dashboard/admin/report", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_admin_report_structure(self, client, db):
        admin = _make_user(db, "admin_rpt@example.com", role="admin", full_name="Report Admin")
        token = create_access_token(admin.id, role="admin")

        resp = client.get("/dashboard/admin/report", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

        data = resp.json()
        assert data["report_period"] == "all-time"
        assert "system_stats" in data
        assert "all_users" in data
        assert isinstance(data["all_users"], list)


# ---------------------------------------------------------------------------
# Test: Admin Users Activity (GET /dashboard/admin/users)
# ---------------------------------------------------------------------------

class TestAdminUsersActivity:
    def test_unauthenticated_rejected(self, client):
        resp = client.get("/dashboard/admin/users")
        assert resp.status_code == 401

    def test_regular_user_forbidden(self, client, db):
        user = _make_user(db, "usr_forbidden@example.com", role="user")
        token = create_access_token(user.id, role="user")

        resp = client.get("/dashboard/admin/users", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_admin_gets_user_table(self, client, db):
        admin = _make_user(db, "admin_utable@example.com", role="admin", full_name="Table Admin")
        token = create_access_token(admin.id, role="admin")

        resp = client.get("/dashboard/admin/users", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

        data = resp.json()
        assert "total_users" in data
        assert "users" in data
        assert isinstance(data["users"], list)
