import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from models import EvidenceItemRecord, FactCheckRecord, User
from auth.dependencies import get_db
from auth.jwt import create_access_token
from auth.password import hash_password
from main import app
from fact_checking.trusted_sources import (
    classify_domain,
    extract_domain,
    TIER_FACT_CHECKER,
    TIER_GOVERNMENT,
    TIER_NEWS_WIRE,
    TIER_UNVERIFIED,
)
from fact_checking.query_builder import (
    build_verification_queries,
    extract_search_keywords,
)
from fact_checking.stance_detector import (
    calculate_lexical_overlap,
    classify_stance,
)
from fact_checking.service import verify_claim
from fact_checking.providers.mock_provider import MockEvidenceProvider


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
    email: str = "fact_checker@example.com",
    full_name: str = "Fact Checker",
    password: str = "StrongPass123!",
    role: str = "user",
    is_active: bool = True,
    is_verified: bool = True,
) -> User:
    """Helper to insert a test user into the test database."""
    db = TestingSessionLocal()
    user = User(
        full_name=full_name,
        email=email,
        hashed_password=hash_password(password),
        role=role,
        is_active=is_active,
        is_verified=is_verified,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


def auth_header_for_user(user: User) -> dict:
    """Generate Authorization header with valid JWT for given user."""
    token, _, _ = create_access_token(user.id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# 1. UNIT TESTS - TRUSTED SOURCES & DOMAIN CLASSIFICATION
# =============================================================================

class TestTrustedSources:
    def test_extract_domain(self):
        assert extract_domain("https://www.pib.gov.in/PressRelease.aspx") == "pib.gov.in"
        assert extract_domain("http://snopes.com/fact-check") == "snopes.com"
        assert extract_domain("reuters.com/news") == "reuters.com"
        assert extract_domain("") == ""

    def test_classify_domain_government_tier(self):
        name, tier, weight = classify_domain("pib.gov.in")
        assert tier == TIER_GOVERNMENT
        assert weight == 1.0
        assert "PIB" in name or "Press Information" in name

        _name, tier_us, weight_us = classify_domain("https://whitehouse.gov/briefing")
        assert tier_us == TIER_GOVERNMENT
        assert weight_us == 1.0

        _name, tier_nic, weight_nic = classify_domain("portal.nic.in")
        assert tier_nic == TIER_GOVERNMENT

    def test_classify_domain_fact_checker_tier(self):
        name, tier, weight = classify_domain("https://www.snopes.com")
        assert tier == TIER_FACT_CHECKER
        assert weight == 0.95

        _name, tier_poly, weight_poly = classify_domain("politifact.com")
        assert tier_poly == TIER_FACT_CHECKER

    def test_classify_domain_news_wire_tier(self):
        name, tier, weight = classify_domain("https://reuters.com/markets")
        assert tier == TIER_NEWS_WIRE
        assert weight == 0.85

        _name, tier_nat, weight_nat = classify_domain("nature.com")
        assert tier_nat == TIER_NEWS_WIRE

    def test_classify_domain_unverified(self):
        name, tier, weight = classify_domain("https://random-rumor-blog.xyz")
        assert tier == TIER_UNVERIFIED
        assert weight <= 0.20


# =============================================================================
# 2. UNIT TESTS - QUERY BUILDER
# =============================================================================

class TestQueryBuilder:
    def test_extract_search_keywords(self):
        claim = "Government announced a new ₹50,000 direct allowance for all students."
        keywords = extract_search_keywords(claim)
        assert len(keywords) > 0
        assert any("50,000" in k or "50000" in k for k in keywords)
        assert any("allowance" in k.lower() for k in keywords)

    def test_build_verification_queries(self):
        claim = "NASA discovered subsurface ocean on Mars."
        queries = build_verification_queries(claim)
        assert "government_query" in queries
        assert "factcheck_query" in queries
        assert "site:.gov" in queries["government_query"] or "site:pib.gov.in" in queries["government_query"]
        assert "snopes.com" in queries["factcheck_query"] or "politifact.com" in queries["factcheck_query"]


# =============================================================================
# 3. UNIT TESTS - STANCE DETECTOR
# =============================================================================

class TestStanceDetector:
    def test_calculate_lexical_overlap(self):
        claim = "Central bank announced interest rate reduction."
        snippet = "The central bank confirmed reduction in the benchmark interest rate."
        overlap = calculate_lexical_overlap(claim, snippet)
        assert overlap > 0.40

    def test_stance_refutes_detected(self):
        claim = "Government announced ₹50,000 allowance for students."
        snippet = "PIB Fact Check confirms this message is completely FAKE and fraudulent. No such scheme exists."
        stance, confidence = classify_stance(claim, snippet)
        assert stance == "REFUTES"
        assert confidence >= 0.70

    def test_stance_supports_detected(self):
        claim = "Scientists published milestone research on quantum fusion energy."
        snippet = "Peer-reviewed findings confirm verified experimental milestones in energy generation published today."
        stance, confidence = classify_stance(claim, snippet)
        assert stance == "SUPPORTS"
        assert confidence >= 0.65

    def test_stance_not_enough_info(self):
        claim = "Company X acquires Company Y."
        snippet = "General overview of stock market movements and daily volume statistics."
        stance, _ = classify_stance(claim, snippet)
        assert stance == "NOT_ENOUGH_INFO"


# =============================================================================
# 4. UNIT TESTS - FACT CHECKING SERVICE
# =============================================================================

class TestFactCheckingService:
    def test_verify_claim_refuted(self):
        claim = "Government announces ₹50,000 direct allowance for students."
        provider = MockEvidenceProvider()
        result = verify_claim(claim, provider=provider)
        assert result["status"] == "REFUTED"
        assert result["verdict"] == "FALSE"
        assert result["trust_score"] >= 75.0
        assert result["evidence_count"] > 0
        assert any(s["stance"] == "REFUTES" for s in result["evidence_sources"])

    def test_verify_claim_verified(self):
        claim = "Scientists announce milestone in fusion energy research."
        provider = MockEvidenceProvider()
        result = verify_claim(claim, provider=provider)
        assert result["status"] == "VERIFIED"
        assert result["verdict"] == "TRUE"
        assert result["trust_score"] >= 70.0
        assert any(s["stance"] == "SUPPORTS" for s in result["evidence_sources"])

    def test_verify_claim_empty(self):
        result = verify_claim("")
        assert result["status"] == "UNPROVEN"
        assert result["verdict"] == "UNVERIFIED"
        assert result["trust_score"] == 0.0


# =============================================================================
# 5. INTEGRATION TESTS - API ENDPOINTS (/fact-check/*)
# =============================================================================

class TestFactCheckingAPIEndpoints:
    def test_whitelist_endpoint_public(self):
        res = client.get("/fact-check/sources/whitelist")
        assert res.status_code == 200
        data = res.json()
        assert data["total_sources"] > 0
        assert len(data["trusted_domains"]) > 0
        assert any("pib.gov.in" in d["domain"] for d in data["trusted_domains"])

    def test_verify_endpoint_authenticated(self):
        user = create_test_user(email="fact_user@news.com")
        headers = auth_header_for_user(user)

        payload = {
            "claim": "Government announced ₹50,000 allowance for students on portal.",
            "check_government_only": True,
            "max_sources": 3,
        }
        res = client.post("/fact-check/verify", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["id"] is not None
        assert data["status"] == "REFUTED"
        assert data["verdict"] == "FALSE"
        assert data["trust_score"] >= 75.0
        assert len(data["evidence_sources"]) > 0
        assert data["evidence_sources"][0]["source_name"] != ""

    def test_verify_endpoint_unauthenticated_fails(self):
        payload = {"claim": "Unauthenticated claim verification request."}
        res = client.post("/fact-check/verify", json=payload)
        assert res.status_code == 401

    def test_user_history_and_isolation(self):
        user1 = create_test_user(email="user1_fc@news.com")
        user2 = create_test_user(email="user2_fc@news.com")
        admin = create_test_user(email="admin_fc@news.com", role="admin")

        headers1 = auth_header_for_user(user1)
        headers2 = auth_header_for_user(user2)
        headers_admin = auth_header_for_user(admin)

        # User 1 submits a fact check
        create_res = client.post(
            "/fact-check/verify",
            json={"claim": "Government announced new solar scheme PM-KUSUM."},
            headers=headers1,
        )
        record_id = create_res.json()["id"]

        # User 1 can see history
        hist1 = client.get("/fact-check/history", headers=headers1)
        assert hist1.status_code == 200
        assert len(hist1.json()) == 1

        # User 2 history is empty
        hist2 = client.get("/fact-check/history", headers=headers2)
        assert hist2.status_code == 200
        assert len(hist2.json()) == 0

        # User 2 cannot access User 1's record
        res_forbidden = client.get(f"/fact-check/history/{record_id}", headers=headers2)
        assert res_forbidden.status_code == 404

        # Admin can access User 1's record
        res_admin = client.get(f"/fact-check/history/{record_id}", headers=headers_admin)
        assert res_admin.status_code == 200
        assert res_admin.json()["id"] == record_id
