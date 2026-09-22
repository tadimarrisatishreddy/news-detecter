# AI Fake News Detector - Backend API

A production-ready FastAPI backend for the AI Fake News Detector project, featuring secure User Authentication (Module 1) and robust News Input & NLP Processing (Module 2).

---

## 📌 Modules Overview

### 1. User Authentication & Security (Module 1)
- **User Model & Storage**: SQLAlchemy ORM with `id`, `full_name`, `email` (indexed, unique), `hashed_password`, `role` (`user`/`admin`), `is_active`, `is_verified`, and UTC timestamps.
- **Secure Password Hashing**: Argon2 password hashing via `passlib[argon2]`. Plaintext passwords are never stored or logged.
- **Strong Password Policy**: Enforces minimum 8 characters, uppercase letters, lowercase letters, numbers, and special characters.
- **JWT Authentication**: Short-lived Access Tokens (HS256) & Long-lived Refresh Tokens with JTI tracking and server-side token revocation on logout.
- **Password Management & Verification**: Forgot password (generic responses to prevent enumeration), reset password, and change password.

### 2. News Input & NLP Processing (Module 2)
- **Text Cleaning & Normalization**:
  - HTML entity unescaping and tag stripping (`<p>`, `<b>`, etc.).
  - Unicode normalization (smart quotes `“ ”`, em-dashes `—`, non-breaking spaces).
  - Comprehensive English contraction expansion (`don't` → `do not`, `they're` → `they are`).
  - URL detection and extraction / removal.
  - Special character and excessive whitespace normalization.
- **Tokenization & Linguistic Processing**:
  - Abbreviation-aware sentence splitting (`Dr.`, `Prof.`, `U.S.`, `3.14`).
  - Word tokenization with punctuation stripping.
  - Standard English stopword filtering and contiguous n-gram extraction (bigrams, trigrams).
- **Linguistic Metrics & Heuristics**:
  - **Linguistic Statistics**: Word count, unique word count, character count, sentence count, average word length, average sentence length, and Type-Token Ratio (lexical diversity).
  - **Readability Scoring**: Flesch Reading Ease score (0–100 scale) and Flesch-Kincaid Grade Level.
  - **Sensationalism / Clickbait Detection**: Evaluates ALL-CAPS shouting patterns, multiple punctuation sequences (`!!!`, `???`), and sensational trigger phrases (`shocking`, `bombshell`, `unbelievable`, `conspiracy`, etc.).
  - **Keyword Extraction**: Informative keyword frequency ranking.
- **Persistence & API Endpoints**:
  - Clean, modular REST endpoints for preprocessing, deep feature analysis, batch processing, and authenticated news submission with SQLite/PostgreSQL storage.

---

## 🚀 Setup & Installation

### 1. Clone & Environment Setup

```bash
# Create and activate virtual environment (optional)
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create or update `.env`:
```env
DATABASE_URL=sqlite:///./news_detector.db
JWT_SECRET_KEY=your_strong_random_jwt_secret_key_here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES=15
EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS=24
EMAIL_FROM=noreply@fakenewsdetector.com
APP_BASE_URL=http://localhost:8000
```

### 3. Start Server

Database tables are initialized automatically on startup:

```bash
uvicorn main:app --reload --port 8000
```

Interactive API documentation:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 📖 API Endpoints Reference

### 🔐 Authentication Endpoints (`/auth`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/auth/register` | Register new user account | No |
| `POST` | `/auth/login` | Log in and receive access + refresh tokens | No |
| `GET` | `/auth/me` | Fetch authenticated user profile | Bearer Token |
| `POST` | `/auth/refresh` | Exchange refresh token for new access token | No |
| `POST` | `/auth/logout` | Revoke active access and refresh tokens | Bearer Token |
| `POST` | `/auth/forgot-password` | Request password reset instructions | No |
| `POST` | `/auth/reset-password` | Reset password using reset token | No |
| `POST` | `/auth/change-password` | Change password with current password verification | Bearer Token |

---

### 📰 News Input & NLP Processing Endpoints (`/news`)

#### 1. Clean & Preprocess Text
**`POST /news/preprocess`** (Status: `200 OK`)

Request Body:
```json
{
  "text": "<p>Breaking! You won't believe this update: https://example.com/live 100% cure discovered!</p>",
  "lowercase": true,
  "strip_html": true,
  "expand_contractions": true,
  "remove_urls": true,
  "remove_stopwords": false,
  "preserve_sentence_punct": false
}
```

Response Body:
```json
{
  "cleaned_text": "breaking you will not believe this update 100 cure discovered",
  "word_count": 9,
  "tokens": ["breaking", "you", "will", "not", "believe", "this", "update", "100", "cure", "discovered"],
  "sentences": ["Breaking! You won't believe this update: https://example.com/live 100% cure discovered!"]
}
```

---

#### 2. Comprehensive NLP Feature Analysis
**`POST /news/analyze`** (Status: `200 OK`)

Request Body:
```json
{
  "news_text": "SHOCKING BOMBSHELL!! International researchers confirmed a breakthrough in quantum fusion energy after years of collaboration."
}
```

Response Body:
```json
{
  "raw_text": "SHOCKING BOMBSHELL!! International researchers confirmed a breakthrough in quantum fusion energy after years of collaboration.",
  "cleaned_text": "shocking bombshell international researchers confirmed a breakthrough in quantum fusion energy after years of collaboration",
  "sentences": [
    "SHOCKING BOMBSHELL!!",
    "International researchers confirmed a breakthrough in quantum fusion energy after years of collaboration."
  ],
  "tokens": ["shocking", "bombshell", "international", "researchers", "confirmed", "a", "breakthrough", "in", "quantum", "fusion", "energy", "after", "years", "of", "collaboration"],
  "tokens_no_stopwords": ["shocking", "bombshell", "international", "researchers", "confirmed", "breakthrough", "quantum", "fusion", "energy", "years", "collaboration"],
  "statistics": {
    "character_count": 128,
    "character_count_no_spaces": 113,
    "word_count": 15,
    "unique_word_count": 15,
    "sentence_count": 2,
    "lexical_diversity": 1.0,
    "avg_word_length": 6.8,
    "avg_sentence_length": 7.5
  },
  "readability": {
    "flesch_reading_ease": 38.45,
    "grade_level": 12.8,
    "reading_level": "Difficult"
  },
  "sensationalism": {
    "sensationalism_score": 0.44,
    "is_sensational": true,
    "caps_ratio": 0.1333,
    "exclamation_count": 2,
    "question_cluster_count": 0,
    "trigger_words_found": ["shocking", "bombshell"]
  },
  "top_keywords": ["shocking", "bombshell", "international", "researchers", "confirmed"],
  "top_keywords_with_freq": [
    {"keyword": "shocking", "count": 1},
    {"keyword": "bombshell", "count": 1},
    {"keyword": "international", "count": 1},
    {"keyword": "researchers", "count": 1},
    {"keyword": "confirmed", "count": 1}
  ]
}
```

---

#### 3. Submit News Article (Authenticated Persistence)
**`POST /news/submit`** (Status: `201 Created`)

Headers:
```http
Authorization: Bearer <access_token>
```

Request Body:
```json
{
  "title": "Global Climate Accord Finalized",
  "news_text": "Representatives from 120 nations reached a consensus on global environmental targets in Geneva today.",
  "source_url": "https://reuters.com/news/environment"
}
```

Response Body:
```json
{
  "id": 1,
  "user_id": 1,
  "title": "Global Climate Accord Finalized",
  "raw_text": "Representatives from 120 nations reached a consensus on global environmental targets in Geneva today.",
  "cleaned_text": "representatives from 120 nations reached a consensus on global environmental targets in geneva today",
  "source_url": "https://reuters.com/news/environment",
  "word_count": 14,
  "char_count": 101,
  "sentence_count": 1,
  "reading_ease_score": 42.15,
  "sensationalism_score": 0.0,
  "lexical_diversity": 1.0,
  "top_keywords": "[\"representatives\", \"nations\", \"reached\", \"consensus\", \"global\"]",
  "created_at": "2026-09-10T16:30:00Z"
}
```

---

#### 4. List User Submissions
**`GET /news/submissions?limit=20&offset=0`** (Status: `200 OK`)

Headers:
```http
Authorization: Bearer <access_token>
```

---

#### 5. Get Submission by ID
**`GET /news/submissions/{id}`** (Status: `200 OK`)

Headers:
```http
Authorization: Bearer <access_token>
```
*Note: Users can only retrieve their own submissions. Admin accounts have cross-user visibility.*

---

#### 6. Batch News Analysis
**`POST /news/batch-analyze`** (Status: `200 OK`)

Request Body:
```json
{
  "articles": [
    {
      "id": "item-1",
      "text": "SHOCKING BOMBSHELL!! You won't believe what they found!"
    },
    {
      "id": "item-2",
      "text": "The aerospace organization deployed a new weather observation satellite into polar orbit."
    }
  ]
}
```

Response Body:
```json
{
  "total_processed": 2,
  "results": [
    {
      "id": "item-1",
      "word_count": 8,
      "cleaned_text": "shocking bombshell you will not believe what they found",
      "readability_score": 75.2,
      "sensationalism_score": 0.54,
      "is_sensational": true,
      "top_keywords": ["shocking", "bombshell", "believe", "found"]
    },
    {
      "id": "item-2",
      "word_count": 11,
      "cleaned_text": "the aerospace organization deployed a new weather observation satellite into polar orbit",
      "readability_score": 35.1,
      "sensationalism_score": 0.0,
      "is_sensational": false,
      "top_keywords": ["aerospace", "organization", "deployed", "weather", "observation"]
    }
  ]
}
```

---

## 🧪 Running Automated Tests

```bash
# Run NLP & News Input test suite (30 tests)
python -m pytest tests/test_nlp.py -v

# Run Authentication test suite (27 tests)
python -m pytest tests/test_auth.py -v

# Run Full Test Suite (83 tests total)
python -m pytest -v
```
