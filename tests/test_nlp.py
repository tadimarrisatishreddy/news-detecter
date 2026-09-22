import json
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from models import NewsSubmission, User
from auth.dependencies import get_db
from auth.jwt import create_access_token
from auth.password import hash_password
from main import app
from nlp.cleaning import (
    clean_special_characters,
    clean_text,
    expand_contractions,
    extract_urls,
    normalize_unicode,
    normalize_whitespace,
    remove_urls,
    strip_html,
)
from nlp.tokenization import (
    ENGLISH_STOPWORDS,
    extract_ngrams,
    remove_stopwords,
    split_into_sentences,
    tokenize_words,
)
from nlp.features import (
    calculate_readability,
    calculate_word_stats,
    count_syllables_in_word,
    detect_sensationalism,
    extract_keywords,
    extract_nlp_features,
)

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
    email: str = "alice@example.com",
    full_name: str = "Alice Journalist",
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
# 1. UNIT TESTS - NLP CLEANING MODULE
# =============================================================================

class TestNLPCleaning:
    def test_strip_html_tags_and_entities(self):
        raw_html = "<p>Scientists discover <b>groundbreaking</b> result &amp; new evidence.</p>"
        result = strip_html(raw_html)
        assert "<p>" not in result
        assert "<b>" not in result
        assert "&amp;" not in result
        assert "Scientists discover groundbreaking result & new evidence." in " ".join(result.split())

    def test_strip_html_empty_or_none(self):
        assert strip_html("") == ""
        assert strip_html(None) == ""

    def test_normalize_unicode_quotes_and_dashes(self):
        unicode_text = "“Special quote” from ‘author’ — with an em–dash and a\u00a0non-breaking space."
        normalized = normalize_unicode(unicode_text)
        assert '"Special quote"' in normalized
        assert "'author'" in normalized
        assert " - " in normalized

    def test_expand_contractions(self):
        text = "They don't know that we haven't seen it and it's isn't working."
        expanded = expand_contractions(text)
        assert "do not" in expanded
        assert "have not" in expanded
        assert "it is" in expanded
        assert "is not" in expanded

    def test_expand_contractions_capitalization(self):
        text = "Don't worry, won't happen."
        expanded = expand_contractions(text)
        assert expanded.startswith("Do not")
        assert "will not" in expanded

    def test_extract_and_remove_urls(self):
        text = "Check out https://www.bbc.com/news/world and www.example.org/test for details."
        urls = extract_urls(text)
        assert len(urls) == 2
        assert "https://www.bbc.com/news/world" in urls

        cleaned = remove_urls(text, replace_with="[LINK]")
        assert "https://www.bbc.com/news/world" not in cleaned
        assert "[LINK]" in cleaned

    def test_clean_special_characters(self):
        text = "Alert! Stock #AAPL jumped 15% ($150 -> $172.50) @market."
        without_punct = clean_special_characters(text, preserve_sentence_punct=False)
        assert "#" not in without_punct
        assert "%" not in without_punct
        assert "$" not in without_punct

        with_punct = clean_special_characters(text, preserve_sentence_punct=True)
        assert "!" in with_punct
        assert "." in with_punct

    def test_normalize_whitespace(self):
        text = "  Multiple    spaces   and\n\nnewlines\t\thandled.  "
        normalized = normalize_whitespace(text)
        assert normalized == "Multiple spaces and newlines handled."

    def test_clean_text_full_pipeline(self):
        raw = "<h1>BREAKING!</h1> You won't believe this: https://fakelink.com <b>100% cure</b> found!"
        cleaned = clean_text(raw, lowercase=True, preserve_sentence_punct=False)
        assert "<h1>" not in cleaned
        assert "won't" not in cleaned
        assert "will not" in cleaned
        assert "https://" not in cleaned
        assert cleaned == "breaking you will not believe this 100 cure found"


# =============================================================================
# 2. UNIT TESTS - NLP TOKENIZATION MODULE
# =============================================================================

class TestNLPTokenization:
    def test_split_into_sentences_basic(self):
        text = "This is the first sentence. This is the second sentence! Is this the third?"
        sentences = split_into_sentences(text)
        assert len(sentences) == 3
        assert sentences[0] == "This is the first sentence."
        assert sentences[1] == "This is the second sentence!"
        assert sentences[2] == "Is this the third?"

    def test_split_into_sentences_abbreviations_and_decimals(self):
        text = "Dr. Smith met with Prof. Jones in the U.S. at 3.14 p.m. to discuss the study."
        sentences = split_into_sentences(text)
        assert len(sentences) == 1
        assert "Dr. Smith" in sentences[0]
        assert "U.S." in sentences[0]

    def test_tokenize_words(self):
        text = "FastAPI and NLP provide state-of-the-art text processing capabilities."
        tokens = tokenize_words(text, lowercase=True, remove_punct=True)
        assert "fastapi" in tokens
        assert "nlp" in tokens
        assert "state-of-the-art" in tokens
        assert "." not in tokens

    def test_remove_stopwords(self):
        tokens = ["the", "quick", "brown", "fox", "jumps", "over", "a", "lazy", "dog"]
        filtered = remove_stopwords(tokens)
        assert "the" not in filtered
        assert "a" not in filtered
        assert "over" not in filtered
        assert "quick" in filtered
        assert "fox" in filtered

    def test_extract_ngrams(self):
        tokens = ["artificial", "intelligence", "fake", "news", "detector"]
        bigrams = extract_ngrams(tokens, n=2)
        assert "artificial intelligence" in bigrams
        assert "fake news" in bigrams
        assert "news detector" in bigrams
        assert len(bigrams) == 4

        trigrams = extract_ngrams(tokens, n=3)
        assert "artificial intelligence fake" in trigrams
        assert len(trigrams) == 3


# =============================================================================
# 3. UNIT TESTS - NLP FEATURES MODULE
# =============================================================================

class TestNLPFeatures:
    def test_count_syllables_in_word(self):
        assert count_syllables_in_word("cat") == 1
        assert count_syllables_in_word("happy") == 2
        assert count_syllables_in_word("incredible") >= 3
        assert count_syllables_in_word("") == 0

    def test_calculate_readability(self):
        simple_text = "The cat sat on the mat. The dog ran in the park. It was a sunny day."
        result = calculate_readability(simple_text)
        assert "flesch_reading_ease" in result
        assert "grade_level" in result
        assert "reading_level" in result
        assert result["flesch_reading_ease"] >= 70.0  # Simple text is easy to read

    def test_calculate_word_stats(self):
        text = "Natural language processing analyzes text. Text processing is powerful."
        stats = calculate_word_stats(text)
        assert stats["word_count"] > 0
        assert stats["unique_word_count"] > 0
        assert stats["sentence_count"] == 2
        assert 0.0 <= stats["lexical_diversity"] <= 1.0
        assert stats["character_count"] == len(text)

    def test_detect_sensationalism_high(self):
        sensational_text = "SHOCKING BOMBSHELL!! You won't believe what happened next!!! Absolute proof secret exposed!!!"
        result = detect_sensationalism(sensational_text)
        assert result["is_sensational"] is True
        assert result["sensationalism_score"] >= 0.35
        assert len(result["trigger_words_found"]) > 0
        assert result["exclamation_count"] >= 3

    def test_detect_sensationalism_objective(self):
        objective_text = "The central bank announced a 25 basis point reduction in the benchmark interest rate on Tuesday."
        result = detect_sensationalism(objective_text)
        assert result["is_sensational"] is False
        assert result["sensationalism_score"] < 0.20
        assert len(result["trigger_words_found"]) == 0

    def test_extract_keywords(self):
        tokens = ["vaccine", "health", "vaccine", "research", "medical", "vaccine", "health"]
        keywords = extract_keywords(tokens, top_k=3)
        assert keywords[0][0] == "vaccine"
        assert keywords[0][1] == 3
        assert keywords[1][0] == "health"
        assert keywords[1][1] == 2

    def test_extract_nlp_features_master(self):
        text = "Breaking report: Scientists discover new treatment in laboratory clinical trials across Europe."
        features = extract_nlp_features(text)
        assert "raw_text" in features
        assert "cleaned_text" in features
        assert "sentences" in features
        assert "tokens" in features
        assert "statistics" in features
        assert "readability" in features
        assert "sensationalism" in features
        assert "top_keywords" in features


# =============================================================================
# 4. INTEGRATION TESTS - API ENDPOINTS (/news)
# =============================================================================

class TestNewsEndpoints:
    def test_preprocess_endpoint(self):
        payload = {
            "text": "<p>Don't miss the <b>latest</b> update on https://example.com/news!</p>",
            "lowercase": True,
            "strip_html": True,
            "expand_contractions": True,
            "remove_urls": True,
            "remove_stopwords": False,
        }
        res = client.post("/news/preprocess", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "cleaned_text" in data
        assert "tokens" in data
        assert "sentences" in data
        assert "do not" in data["cleaned_text"]
        assert "<p>" not in data["cleaned_text"]
        assert "https://" not in data["cleaned_text"]

    def test_analyze_endpoint(self):
        payload = {
            "news_text": "Scientists announce a groundbreaking milestone in nuclear fusion energy research after years of international collaboration."
        }
        res = client.post("/news/analyze", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["raw_text"] == payload["news_text"]
        assert "statistics" in data
        assert data["statistics"]["word_count"] > 0
        assert "readability" in data
        assert "sensationalism" in data
        assert "top_keywords" in data
        assert isinstance(data["top_keywords"], list)

    def test_analyze_endpoint_validation_failure(self):
        # Text is too short (under 20 characters)
        res = client.post("/news/analyze", json={"news_text": "Too short"})
        assert res.status_code == 422

    def test_submit_news_unauthenticated_fails(self):
        payload = {
            "title": "Unauthenticated Submission",
            "news_text": "This article should fail because no Authorization header was provided in the request.",
        }
        res = client.post("/news/submit", json=payload)
        assert res.status_code == 401

    def test_submit_news_authenticated_success(self):
        user = create_test_user(email="journalist@news.com")
        headers = auth_header_for_user(user)

        payload = {
            "title": "Global Climate Conference Concludes",
            "news_text": "Delegates from over one hundred countries agreed on a new framework for carbon emission reductions.",
            "source_url": "https://reuters.com/news/sample",
        }
        res = client.post("/news/submit", json=payload, headers=headers)
        assert res.status_code == 201
        data = res.json()
        assert data["id"] is not None
        assert data["user_id"] == user.id
        assert data["title"] == payload["title"]
        assert data["word_count"] > 0
        assert data["char_count"] > 0
        assert data["reading_ease_score"] is not None
        assert data["sensationalism_score"] is not None

    def test_list_user_submissions(self):
        user1 = create_test_user(email="user1@news.com")
        user2 = create_test_user(email="user2@news.com")

        # Submit 2 articles as user 1
        headers1 = auth_header_for_user(user1)
        client.post(
            "/news/submit",
            json={"title": "Article 1", "news_text": "Article one body text for NLP processing and validation."},
            headers=headers1,
        )
        client.post(
            "/news/submit",
            json={"title": "Article 2", "news_text": "Article two body text for NLP processing and validation."},
            headers=headers1,
        )

        # Submit 1 article as user 2
        headers2 = auth_header_for_user(user2)
        client.post(
            "/news/submit",
            json={"title": "Article 3", "news_text": "Article three body text for NLP processing and validation."},
            headers=headers2,
        )

        # User 1 should see only their 2 submissions
        res1 = client.get("/news/submissions", headers=headers1)
        assert res1.status_code == 200
        articles1 = res1.json()
        assert len(articles1) == 2
        assert all(a["user_id"] == user1.id for a in articles1)

        # User 2 should see only their 1 submission
        res2 = client.get("/news/submissions", headers=headers2)
        assert res2.status_code == 200
        articles2 = res2.json()
        assert len(articles2) == 1
        assert articles2[0]["user_id"] == user2.id

    def test_get_submission_by_id_and_isolation(self):
        user1 = create_test_user(email="alice_writer@news.com")
        user2 = create_test_user(email="bob_writer@news.com")

        headers1 = auth_header_for_user(user1)
        headers2 = auth_header_for_user(user2)

        # Create submission by user 1
        create_res = client.post(
            "/news/submit",
            json={"title": "Secret Tech Innovation", "news_text": "A new semiconductor architecture was revealed today in Tokyo."},
            headers=headers1,
        )
        submission_id = create_res.json()["id"]

        # User 1 can view it
        res_owner = client.get(f"/news/submissions/{submission_id}", headers=headers1)
        assert res_owner.status_code == 200
        assert res_owner.json()["id"] == submission_id

        # User 2 receives 404 (isolation)
        res_other = client.get(f"/news/submissions/{submission_id}", headers=headers2)
        assert res_other.status_code == 404

    def test_admin_can_access_any_submission(self):
        user = create_test_user(email="reporter@news.com", role="user")
        admin = create_test_user(email="chief_editor@news.com", role="admin")

        user_headers = auth_header_for_user(user)
        admin_headers = auth_header_for_user(admin)

        create_res = client.post(
            "/news/submit",
            json={"title": "Economic Forecast 2027", "news_text": "Inflation rates are projected to stabilize according to financial analysts."},
            headers=user_headers,
        )
        sub_id = create_res.json()["id"]

        # Admin can view the submission
        res_admin = client.get(f"/news/submissions/{sub_id}", headers=admin_headers)
        assert res_admin.status_code == 200
        assert res_admin.json()["id"] == sub_id

    def test_batch_analyze_endpoint(self):
        batch_payload = {
            "articles": [
                {
                    "id": "art-1",
                    "text": "SHOCKING BOMBSHELL!! You won't believe what happened in this viral video!",
                },
                {
                    "id": "art-2",
                    "text": "The international space station successfully completed its orbital trajectory adjustment.",
                },
            ]
        }
        res = client.post("/news/batch-analyze", json=batch_payload)
        assert res.status_code == 200
        data = res.json()
        assert data["total_processed"] == 2
        results = data["results"]
        assert len(results) == 2
        assert results[0]["id"] == "art-1"
        assert results[0]["is_sensational"] is True
        assert results[1]["id"] == "art-2"
        assert results[1]["is_sensational"] is False

