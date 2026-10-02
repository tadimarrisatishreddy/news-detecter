# TruthLens AI - Fake News Detector & Fact-Checking Studio

A complete, production-ready full-stack AI system featuring:
- **Module 1**: Secure User Authentication & Role-Based Access Control (RBAC)
- **Module 2**: Deterministic News Input & NLP Text Processing Engine
- **Module 3**: AI Detection & Fake News Classification with Google Gemma 3
- **Module 4**: Fact-Checking & Official Government Registry Verification
- **Module 5**: Analytics Dashboard & Exportable Audit Reports
- **Module 6**: Modern Web Application Frontend & Containerized Deployment

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

### 3. AI Detection & Verification Engine (Module 3)
- **Google Gemma AI Integration**:
  - Direct connector to **Ollama** running `gemma3:4b` (or configurable model).
  - Low-temperature deterministic inference with fact-checking role prompt.
- **Context-Enriched Prompting**:
  - Automatically injects Module 2's NLP signals (sensationalism index, ALL-CAPS ratio, clickbait triggers, reading level) into the prompt context.
- **Robust Output Parsing & Normalization**:
  - Robust JSON parser with regex fallbacks and synonym normalization.
  - Classifies news into `LIKELY_REAL`, `LIKELY_FAKE`, or `UNCERTAIN`.
  - Produces calibrated confidence scores (0–100%) and explainable reasoning.
- **Hybrid Confidence Calibration**:
  - Reconciles LLM predictions with deterministic linguistic metrics for higher fidelity.
- **Batch Processing & Resilience**:
  - Instant offline fallback simulation for testing and low-latency environments.
  - `POST /detect/batch` for evaluating up to 50 claims concurrently.

### 4. Fact-Checking & Government Registry Verification (Module 4)
- **5-Tier Domain Authority Registry**:
  - Tier 1: Official Government Portals (`.gov`, `.gov.in`, `pib.gov.in`, `rbi.org.in`) - 1.0 weight
  - Tier 2: Certified Independent Fact-Checkers (`snopes.com`, `politifact.com`, `factcheck.org`) - 0.9 weight
  - Tier 3: Global News Wires (`reuters.com`, `apnews.com`, `afp.com`) - 0.8 weight
  - Tier 4: Major Press Publications (`bbc.com`, `thehindu.com`, etc.) - 0.65 weight
  - Tier 5: General & Unverified web sources - 0.15 weight
- **Automated Evidence Stance Classification**:
  - Semantic and lexical overlap evaluation determining whether citations `SUPPORTS`, `REFUTES`, or provide `NOT_ENOUGH_INFO`.
- **Authoritative Verification Pipeline**:
  - Produces multi-source trust scores (0-100) and overall status (`VERIFIED`, `REFUTED`, `DISPUTED`, `UNPROVEN`).

### 5. Analytics Dashboard & Reporting (Module 5)
- **User Dashboard (`GET /dashboard/me`)**:
  - Aggregates individual claim detections, fact-checks, linguistic sensationalism average, and personal activity feeds.
- **Admin Control Panel (`GET /dashboard/admin`)**:
  - Platform-wide threat monitoring, global verdict distributions, most-flagged fake news claims, and user engagement metrics.
- **Exportable Audit Reports**:
  - Machine-readable JSON reports for individual audit histories or full platform oversight.

### 6. Modern Web Application & Deployment (Module 6)
- **Full-Stack Web Interface (`/static`)**:
  - Interactive Single-Page Application (SPA) designed with modern semantic HTML5, accessible forms, native `<dialog>` modals, and clean CSS variables.
  - Dedicated interactive tabs for AI Detection (with pre-set quick samples), Fact-Checking, NLP Studio, Personal Dashboard, and Admin Control Panel.
- **One-Click System Runner (`run.py`)**:
  - Validates SQLite database tables, checks frontend assets, inspects AI runtime mode, and starts the full-stack server on `http://localhost:8000`.
- **Containerized Deployment**:
  - Production `Dockerfile` and `docker-compose.yml` with persistent volume storage and health check monitoring.

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

# Gemma AI Configuration
OLLAMA_BASE_URL=http://localhost:11434
GEMMA_MODEL=gemma3:4b
AI_TIMEOUT_SECONDS=30
AI_DETECTION_MODE=auto
```

### 3. Start Server

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

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/news/preprocess` | Clean, normalize, and tokenize raw news text | No |
| `POST` | `/news/analyze` | Linguistic stats, readability, and sensationalism | No |
| `POST` | `/news/submit` | Ingest and store news article for calling user | Bearer Token |
| `GET` | `/news/submissions` | List user's processed news submissions | Bearer Token |
| `GET` | `/news/submissions/{id}` | Get single submission with user isolation | Bearer Token |
| `POST` | `/news/batch-analyze` | Batch process up to 50 news articles | No |

---

### 🤖 AI Detection Endpoints (`/detect` & `/analyses`)

#### 1. Instant News Detection
**`POST /detect`** (Status: `200 OK`)

Headers:
```http
Authorization: Bearer <access_token>
```

Request Body:
```json
{
  "claim": "The government announced that the moon will be declared the 29th state of the country tomorrow."
}
```

Response Body:
```json
{
  "message": "News analyzed successfully",
  "detection_id": 1,
  "claim": "The government announced that the moon will be declared the 29th state of the country tomorrow.",
  "verdict": "LIKELY_FAKE",
  "confidence": 95.0,
  "explanation": "This claim is highly implausible and lacks any credible evidence. The statement contradicts established geopolitical realities and legal frameworks.",
  "created_at": "2026-09-24T17:30:00Z"
}
```

---

#### 2. Batch AI Detection
**`POST /detect/batch`** (Status: `200 OK`)

Headers:
```http
Authorization: Bearer <access_token>
```

Request Body:
```json
{
  "claims": [
    "SHOCKING BOMBSHELL!! Miracle cure they don't want you to know!",
    "Central bank announced a 25 basis point reduction in the benchmark interest rate."
  ]
}
```

Response Body:
```json
{
  "total_processed": 2,
  "results": [
    {
      "claim": "SHOCKING BOMBSHELL!! Miracle cure they don't want you to know!",
      "verdict": "LIKELY_FAKE",
      "confidence": 95.0,
      "explanation": "Sensational clickbait styling and unsubstantiated claims of miracle remedies indicate fabricated content.",
      "key_signals": ["Sensationalist clickbait style", "Unsubstantiated factual claim"]
    },
    {
      "claim": "Central bank announced a 25 basis point reduction in the benchmark interest rate.",
      "verdict": "LIKELY_REAL",
      "confidence": 88.0,
      "explanation": "The article uses objective, journalistic language consistent with legitimate institutional reporting.",
      "key_signals": ["Neutral objective tone", "Verifiable institutional attribution"]
    }
  ]
}
```

---

#### 3. Deep Analysis with Source URL
**`POST /analyses`** (Status: `201 Created`)

Headers:
```http
Authorization: Bearer <access_token>
```

Request Body:
```json
{
  "input_text": "Scientists announce a groundbreaking milestone in nuclear fusion energy research after years of international collaboration.",
  "source_url": "https://nature.com/articles/sample"
}
```

---

## 🚀 Running the Full-Stack Application

### Option 1: Native Python Runner (One-Click)
```bash
# Start server and run initial checks
python run.py

# Optionally automatically open the web browser
python run.py --open
```
- **Web Application**: [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check Probe**: [http://localhost:8000/health](http://localhost:8000/health)

### Option 2: Docker Containerization
```bash
# Build and run with Docker Compose
docker compose up --build -d

# Check container health status
curl http://localhost:8000/health
```

---

## 🧪 Running Automated Tests

The comprehensive automated test suite features **146 passing tests** across all 6 modules:

```bash
# Run the entire test suite (146 tests)
python -m pytest -v

# Run Frontend & Deployment tests (8 tests)
python -m pytest tests/test_frontend.py -v

# Run Dashboard & Reports tests (19 tests)
python -m pytest tests/test_dashboard.py -v

# Run Fact-Checking tests (18 tests)
python -m pytest tests/test_fact_checking.py -v

# Run AI Detection test suite (18 tests)
python -m pytest tests/test_ai_detection.py -v

# Run NLP text processing suite (30 tests)
python -m pytest tests/test_nlp.py -v

# Run Authentication & Security suite (27 tests)
python -m pytest tests/test_auth.py -v
```
