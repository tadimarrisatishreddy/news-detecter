"""
tests/test_login_and_history.py
===============================
Tests verifying:
1. User login tracking in database (LoginHistory table and User.last_login_at)
2. GET /auth/login-history endpoint
3. Detection record storage in database on /detect
4. History search, filtering, detail retrieval, deletion and clearing
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from models import DetectionHistory, LoginHistory, User
from auth import get_db, hash_password
from main import app, create_access_token
from ai.gemma_client import default_gemma_client

default_gemma_client.mode = "mock"

TEST_DB_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DB_URL,
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


@pytest.fixture(autouse=True)
def setup_test_db():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.clear()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def create_user(username="testuser", email="test@example.com", password="Password123!"):
    db = TestingSessionLocal()
    user = User(
        full_name=f"{username} Name",
        username=username,
        email=email,
        hashed_password=hash_password(password),
        role="user",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user_id=user.id, role=user.role)
    user_id = user.id
    db.close()
    return user_id, email, password, token


class TestLoginTrackingInDatabase:
    def test_login_stores_audit_record_and_last_login(self, client):
        user_id, email, password, _ = create_user()

        # Login via endpoint
        resp = client.post(
            "/auth/login",
            json={"email": email, "password": password},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

        # Verify DB records
        db = TestingSessionLocal()
        user = db.query(User).filter(User.id == user_id).first()
        assert user.last_login_at is not None

        login_recs = db.query(LoginHistory).filter(LoginHistory.user_id == user_id).all()
        assert len(login_recs) == 1
        assert login_recs[0].status == "success"
        assert login_recs[0].email == email
        db.close()

    def test_failed_login_stores_failed_audit_record(self, client):
        user_id, email, _, _ = create_user()

        resp = client.post(
            "/auth/login",
            json={"email": email, "password": "WrongPassword999!"},
        )
        assert resp.status_code == 401

        db = TestingSessionLocal()
        failed_recs = db.query(LoginHistory).filter(LoginHistory.email == email).all()
        assert len(failed_recs) == 1
        assert failed_recs[0].status == "failed"
        assert failed_recs[0].failure_reason == "Incorrect email or password"
        db.close()

    def test_get_user_login_history_endpoint(self, client):
        _, email, password, token = create_user()

        # Perform 2 logins
        client.post("/auth/login", json={"email": email, "password": password})
        client.post("/auth/login", json={"email": email, "password": password})

        resp = client.get(
            "/auth/login-history",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 2
        assert data[0]["status"] == "success"
        assert data[0]["email"] == email


class TestDetectionAndHistoryDatabase:
    def test_detect_news_and_stores_in_database(self, client):
        user_id, _, _, token = create_user()

        claim_text = "The earth has two moons visible tonight."
        resp = client.post(
            "/detect",
            json={"claim": claim_text},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["claim"] == claim_text
        assert "verdict" in data
        assert "confidence" in data
        assert "detection_id" in data

        # Verify stored in database
        db = TestingSessionLocal()
        record = db.query(DetectionHistory).filter(DetectionHistory.id == data["detection_id"]).first()
        assert record is not None
        assert record.user_id == user_id
        assert record.claim == claim_text
        db.close()

    def test_get_history_with_search_and_verdict_filter(self, client):
        user_id, _, _, token = create_user()

        # Seed detection records directly
        db = TestingSessionLocal()
        db.add(DetectionHistory(user_id=user_id, claim="Economic growth rises by 3 percent", verdict="LIKELY_REAL", confidence=85.0))
        db.add(DetectionHistory(user_id=user_id, claim="Aliens land in capital city", verdict="LIKELY_FAKE", confidence=95.0))
        db.add(DetectionHistory(user_id=user_id, claim="Secret cure for all diseases discovered", verdict="LIKELY_FAKE", confidence=90.0))
        db.commit()
        db.close()

        # All history
        res_all = client.get("/history", headers={"Authorization": f"Bearer {token}"})
        assert res_all.status_code == 200
        assert len(res_all.json()) == 3

        # Filter by verdict LIKELY_FAKE
        res_fake = client.get("/history?verdict=LIKELY_FAKE", headers={"Authorization": f"Bearer {token}"})
        assert res_fake.status_code == 200
        assert len(res_fake.json()) == 2

        # Search by query "aliens"
        res_search = client.get("/history?q=aliens", headers={"Authorization": f"Bearer {token}"})
        assert res_search.status_code == 200
        assert len(res_search.json()) == 1
        assert "Aliens" in res_search.json()[0]["claim"]

    def test_get_and_delete_specific_detection_item(self, client):
        user_id, _, _, token = create_user()

        db = TestingSessionLocal()
        d = DetectionHistory(user_id=user_id, claim="Sample claim to delete", verdict="LIKELY_REAL", confidence=70.0)
        db.add(d)
        db.commit()
        db.refresh(d)
        item_id = d.id
        db.close()

        # Get item
        get_res = client.get(f"/history/{item_id}", headers={"Authorization": f"Bearer {token}"})
        assert get_res.status_code == 200
        assert get_res.json()["id"] == item_id

        # Delete item
        del_res = client.delete(f"/history/{item_id}", headers={"Authorization": f"Bearer {token}"})
        assert del_res.status_code == 200

        # Verify not found
        get_res2 = client.get(f"/history/{item_id}", headers={"Authorization": f"Bearer {token}"})
        assert get_res2.status_code == 404

    def test_clear_all_detection_history(self, client):
        user_id, _, _, token = create_user()

        db = TestingSessionLocal()
        for i in range(4):
            db.add(DetectionHistory(user_id=user_id, claim=f"Claim #{i}", verdict="UNCERTAIN", confidence=50.0))
        db.commit()
        db.close()

        # Verify 4 items
        res = client.get("/history", headers={"Authorization": f"Bearer {token}"})
        assert len(res.json()) == 4

        # Clear history
        clear_res = client.delete("/history", headers={"Authorization": f"Bearer {token}"})
        assert clear_res.status_code == 200
        assert clear_res.json()["deleted_count"] == 4

        # Verify 0 items
        res_after = client.get("/history", headers={"Authorization": f"Bearer {token}"})
        assert len(res_after.json()) == 0
