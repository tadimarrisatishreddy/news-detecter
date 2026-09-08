# AI Fake News Detector - User Authentication Module

A secure, modular, and production-ready User Authentication & Role-Based Access Control (RBAC) module built for the FastAPI Fake News Detector backend.

---

## 📌 Features

- **User Model & Storage**: SQLAlchemy ORM model with `id`, `full_name`, `email` (indexed, unique), `hashed_password`, `role` (`user`/`admin`), `is_active`, `is_verified`, and UTC timestamps (`created_at`, `updated_at`).
- **Secure Password Hashing**: Argon2 password hashing via `passlib[argon2]`. Plaintext passwords are never stored or logged.
- **Strong Password Policy**: Enforces minimum 8 characters, uppercase letters, lowercase letters, numbers, and special characters.
- **JWT Authentication**:
  - Short-lived Access Tokens (HS256)
  - Long-lived Refresh Tokens with unique JTI identifiers
  - Token Blacklisting / Revocation on logout and password change
- **Password Management**:
  - Generic-response Forgot Password flow (prevents email enumeration)
  - Short-lived, single-use Password Reset tokens
  - Protected Change Password with current password verification
- **Email Verification Readiness**: Pluggable email verification token architecture with development logger.
- **Reusable Dependencies**:
  - `get_current_user`
  - `get_current_active_user`
  - `require_role("admin", ...)` factory for RBAC
- **Safe Responses**: All authentication endpoints strictly exclude password hashes and secret claims.

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

Copy `.env.example` to `.env` and configure your settings:

```bash
cp .env.example .env
```

Example `.env`:
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

### 3. Run Database Initialization & Start Server

The database tables are automatically created on startup with SQLAlchemy metadata:

```bash
uvicorn main:app --reload --port 8000
```

Interactive API documentation will be available at:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🔐 Authentication Endpoints Reference

### 1. Register User
**`POST /auth/register`** (Status: `201 Created`)

**Request Body:**
```json
{
  "full_name": "Jane Doe",
  "email": "jane.doe@example.com",
  "password": "SecurePassword123!",
  "confirm_password": "SecurePassword123!"
}
```

**Response Body:**
```json
{
  "id": 1,
  "full_name": "Jane Doe",
  "email": "jane.doe@example.com",
  "role": "user",
  "is_active": true,
  "is_verified": false,
  "created_at": "2026-09-08T21:50:00.000000Z"
}
```

---

### 2. Login
**`POST /auth/login`** (Status: `200 OK`)

**Request Body:**
```json
{
  "email": "jane.doe@example.com",
  "password": "SecurePassword123!"
}
```

**Response Body:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

### 3. Current User Profile
**`GET /auth/me`** (Status: `200 OK`)

**Headers:**
```http
Authorization: Bearer <access_token>
```

**Response Body:**
```json
{
  "id": 1,
  "full_name": "Jane Doe",
  "email": "jane.doe@example.com",
  "role": "user",
  "is_active": true,
  "is_verified": false,
  "created_at": "2026-09-08T21:50:00.000000Z"
}
```

---

### 4. Refresh Access Token
**`POST /auth/refresh`** (Status: `200 OK`)

**Request Body:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response Body:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

### 5. Logout & Token Revocation
**`POST /auth/logout`** (Status: `200 OK`)

**Headers:**
```http
Authorization: Bearer <access_token>
```

**Optional Request Body:**
```json
{
  "refresh_token": "<optional_refresh_token>"
}
```

**Response Body:**
```json
{
  "message": "Successfully logged out and tokens revoked."
}
```

> **Logout Mechanism Note**: This project implements server-side token blacklisting using the `revoked_tokens` database table. In addition to server-side revocation, client applications should always securely delete the stored tokens from browser storage (localStorage / secure cookies).

---

### 6. Forgot Password
**`POST /auth/forgot-password`** (Status: `200 OK`)

**Request Body:**
```json
{
  "email": "jane.doe@example.com"
}
```

**Response Body:**
```json
{
  "message": "If this email is registered, password reset instructions have been sent."
}
```

---

### 7. Reset Password
**`POST /auth/reset-password`** (Status: `200 OK`)

**Request Body:**
```json
{
  "token": "32_character_url_safe_token",
  "new_password": "NewSecurePassword456!",
  "confirm_password": "NewSecurePassword456!"
}
```

**Response Body:**
```json
{
  "message": "Password has been successfully reset. You may now log in with your new password."
}
```

---

### 8. Change Password
**`POST /auth/change-password`** (Status: `200 OK`)

**Headers:**
```http
Authorization: Bearer <access_token>
```

**Request Body:**
```json
{
  "current_password": "SecurePassword123!",
  "new_password": "NewSecurePassword456!",
  "confirm_password": "NewSecurePassword456!"
}
```

**Response Body:**
```json
{
  "message": "Password updated successfully."
}
```

---

### 9. Request Email Verification
**`POST /auth/request-email-verification`** (Status: `200 OK`)

**Request Body:**
```json
{
  "email": "jane.doe@example.com"
}
```

---

### 10. Verify Email
**`POST /auth/verify-email`** (Status: `200 OK`)

**Request Body:**
```json
{
  "token": "32_character_verification_token"
}
```

---

## 🧪 Running Automated Tests

To run the complete test suite:

```bash
# Run auth test suite
python -m pytest tests/test_auth.py -v

# Run full project test suite
python -m pytest -v
```

