import os
from pathlib import Path

# Base Directory
BASE_DIR = Path(__file__).resolve().parent

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/news_detector.db")

# JWT Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "replace-with-a-secure-random-secret-key-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Password Reset & Verification Configuration
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = int(os.getenv("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", "15"))
EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS = int(os.getenv("EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS", "24"))

# Email Service Configuration
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@fakenewsdetector.com")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")

