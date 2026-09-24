import json
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from models import Analysis, DetectionHistory, User
from auth.dependencies import get_db
from auth.jwt import create_access_token
from auth.password import hash_password
from main import app
from ai.prompts import build_detection_prompt, SYSTEM_PROMPT
from ai.parser import (
    extract_json_block,
    heuristic_fallback_from_nlp,
    normalize_confidence,
    normalize_verdict,
    parse_ai_response,
    parse_key_value_fallback,
)
from ai.service import calibrate_confidence, detect_fake_news, detect_fake_news_batch
from ai.gemma_client import GemmaClient


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
    email: str = "ai_tester@example.com",
    full_name: str = "AI Tester",
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
# 1. UNIT TESTS - PROMPT ENGINEERING
# =============================================================================

class TestPromptEngineering:
    def test_build_detection_prompt_structure(self):
        claim = "The local zoo acquired a pair of endangered snow leopards."
        messages = build_detection_prompt(claim)
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert claim in messages[1]["content"]
        assert "JSON" in messages[0]["content"]

    def test_build_detection_prompt_with_nlp_context(self):
        claim = "SHOCKING BOMBSHELL!! Miracle pill cures all diseases overnight!!!"
        nlp_context = {
            "sensationalism": {
                "sensationalism_score": 0.85,
                "caps_ratio": 0.25,
                "trigger_words_found": ["shocking", "bombshell", "miracle"],
            },
            "readability": {
                "reading_level": "Easy",
                "grade_level": 4.5,
            },
            "statistics": {
                "word_count": 8,
            },
        }
        messages = build_detection_prompt(claim, nlp_features=nlp_context)
        user_content = messages[1]["content"]
        assert "Sensationalism Index: 0.85" in user_content
        assert "shocking, bombshell, miracle" in user_content
        assert "ALL-CAPS Shouting Ratio: 25.0%" in user_content
        assert "Readability: Easy" in user_content


# =============================================================================
# 2. UNIT TESTS - RESPONSE PARSER & NORMALIZATION
# =============================================================================

class TestResponseParser:
    def test_normalize_verdict_synonyms(self):
        assert normalize_verdict("LIKELY_REAL") == "LIKELY_REAL"
        assert normalize_verdict("real") == "LIKELY_REAL"
        assert normalize_verdict("true") == "LIKELY_REAL"
        assert normalize_verdict("factual") == "LIKELY_REAL"

        assert normalize_verdict("LIKELY_FAKE") == "LIKELY_FAKE"
        assert normalize_verdict("fake") == "LIKELY_FAKE"
        assert normalize_verdict("false") == "LIKELY_FAKE"
        assert normalize_verdict("hoax") == "LIKELY_FAKE"

        assert normalize_verdict("UNCERTAIN") == "UNCERTAIN"
        assert normalize_verdict("unverified") == "UNCERTAIN"
        assert normalize_verdict("unknown") == "UNCERTAIN"
        assert normalize_verdict("") == "UNCERTAIN"

    def test_normalize_confidence_values(self):
        assert normalize_confidence(95) == 95.0
        assert normalize_confidence("88.5%") == 88.5
        assert normalize_confidence(0.92) == 92.0  # Probability conversion
        assert normalize_confidence(125) == 100.0  # Clamping upper bound
        assert normalize_confidence(-10) == 0.0  # Clamping lower bound
        assert normalize_confidence("invalid", default=70.0) == 70.0

    def test_extract_json_block_clean_and_fenced(self):
        clean_json = '{"verdict": "LIKELY_REAL", "confidence": 90, "explanation": "Verified."}'
        assert extract_json_block(clean_json) == {
            "verdict": "LIKELY_REAL",
            "confidence": 90,
            "explanation": "Verified.",
        }

        fenced_json = 'Here is the analysis:\n```json\n{"verdict": "LIKELY_FAKE", "confidence": 95, "explanation": "Hoax."}\n```'
        parsed = extract_json_block(fenced_json)
        assert parsed is not None
        assert parsed["verdict"] == "LIKELY_FAKE"
        assert parsed["confidence"] == 95

    def test_parse_key_value_fallback(self):
        text = "VERDICT: LIKELY_REAL\nCONFIDENCE: 85\nEXPLANATION: The statement aligns with recent government data."
        parsed = parse_key_value_fallback(text)
        assert parsed is not None
        assert parsed["verdict"] == "LIKELY_REAL"
        assert parsed["confidence"] == 85.0
        assert "government data" in parsed["explanation"]

    def test_parse_ai_response_master(self):
        model_output = '```json\n{"verdict": "fake", "confidence": "94%", "explanation": "Fabricated claim.", "key_signals": ["No evidence"], "manipulation_tactics": ["Clickbait"]}\n```'
        result = parse_ai_response(model_output)
        assert result["verdict"] == "LIKELY_FAKE"
        assert result["confidence"] == 94.0
        assert result["explanation"] == "Fabricated claim."
        assert result["key_signals"] == ["No evidence"]
        assert result["manipulation_tactics"] == ["Clickbait"]

    def test_heuristic_fallback_when_output_malformed(self):
        broken_output = "I cannot fulfill this request because the text is empty."
        nlp_context = {
            "sensationalism": {
                "sensationalism_score": 0.8,
                "is_sensational": True,
                "trigger_words_found": ["shocking"],
            }
        }
        result = parse_ai_response(broken_output, nlp_features=nlp_context)
        assert result["verdict"] == "LIKELY_FAKE"
        assert result["confidence"] >= 80.0


# =============================================================================
# 3. UNIT TESTS - HYBRID CONFIDENCE CALIBRATION
# =============================================================================

class TestHybridCalibration:
    def test_confidence_calibration_fake_boosted_by_sensationalism(self):
        nlp = {"sensationalism": {"sensationalism_score": 0.75, "is_sensational": True}}
        calibrated = calibrate_confidence("LIKELY_FAKE", raw_confidence=85.0, nlp_features=nlp)
        assert calibrated > 85.0
        assert calibrated <= 99.0

    def test_confidence_calibration_real_penalized_by_high_sensationalism(self):
        nlp = {"sensationalism": {"sensationalism_score": 0.8, "is_sensational": True}}
        calibrated = calibrate_confidence("LIKELY_REAL", raw_confidence=90.0, nlp_features=nlp)
        assert calibrated < 90.0


# =============================================================================
# 4. INTEGRATION TESTS - AI DETECTION SERVICE & CLIENT
# =============================================================================

class TestDetectionService:
    def test_detect_fake_news_mock_fake_claim(self):
        claim = "SHOCKING BOMBSHELL!! The government announced the moon will be declared a state tomorrow!"
        mock_client = GemmaClient(mode="mock")
        res = detect_fake_news(claim, client=mock_client)
        assert res["verdict"] == "LIKELY_FAKE"
        assert res["confidence"] >= 80.0
        assert "nlp_summary" in res
        assert res["nlp_summary"]["word_count"] > 0

    def test_detect_fake_news_mock_real_claim(self):
        claim = "Scientists announce a groundbreaking milestone in clinical trial published in the medical journal."
        mock_client = GemmaClient(mode="mock")
        res = detect_fake_news(claim, client=mock_client)
        assert res["verdict"] == "LIKELY_REAL"
        assert res["confidence"] >= 80.0

    def test_detect_fake_news_empty_claim(self):
        res = detect_fake_news("")
        assert res["verdict"] == "UNCERTAIN"
        assert res["confidence"] == 0.0

    def test_detect_fake_news_batch(self):
        claims = [
            "SHOCKING BOMBSHELL!! Secret cure exposed!",
            "Central bank announced a 25 basis point reduction in the benchmark interest rate.",
        ]
        mock_client = GemmaClient(mode="mock")
        results = detect_fake_news_batch(claims, client=mock_client)
        assert len(results) == 2
        assert results[0]["verdict"] == "LIKELY_FAKE"
        assert results[1]["verdict"] == "LIKELY_REAL"


# =============================================================================
# 5. INTEGRATION TESTS - API ENDPOINTS (/detect, /analyses, /history)
# =============================================================================

class TestDetectionAPIEndpoints:
    def test_detect_endpoint_authenticated(self):
        user = create_test_user(email="detect_user@news.com")
        headers = auth_header_for_user(user)

        payload = {"claim": "SHOCKING BOMBSHELL!! Secret cure they don't want you to know!"}
        res = client.post("/detect", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["message"] == "News analyzed successfully"
        assert data["detection_id"] > 0
        assert data["verdict"] == "LIKELY_FAKE"
        assert data["confidence"] > 0
        assert data["explanation"] != ""

    def test_detect_endpoint_unauthenticated_fails(self):
        payload = {"claim": "Some claim text without token."}
        res = client.post("/detect", json=payload)
        assert res.status_code == 401

    def test_detect_batch_endpoint(self):
        user = create_test_user(email="batch_user@news.com")
        headers = auth_header_for_user(user)

        payload = {
            "claims": [
                "SHOCKING BOMBSHELL!! Secret aliens conspiracy revealed!",
                "International conference concludes with unanimous agreement on carbon emissions.",
            ]
        }
        res = client.post("/detect/batch", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["total_processed"] == 2
        assert len(data["results"]) == 2
        assert data["results"][0]["verdict"] == "LIKELY_FAKE"
        assert data["results"][1]["verdict"] == "LIKELY_REAL"

    def test_analyses_endpoint_end_to_end(self):
        user = create_test_user(email="analyst@news.com")
        headers = auth_header_for_user(user)

        payload = {
            "input_text": "Researchers published a peer-reviewed collaboration study on quantum computing advances.",
            "source_url": "https://nature.com/articles/sample",
        }
        res = client.post("/analyses", json=payload, headers=headers)
        assert res.status_code == 201
        data = res.json()
        assert data["id"] > 0
        assert data["status"] == "completed"
        assert data["verdict"] == "LIKELY_REAL"
        assert data["confidence"] >= 70.0
        assert data["source_url"] == payload["source_url"]

