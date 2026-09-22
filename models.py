from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    username = Column(String, unique=True, index=True, nullable=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="user", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    detections = relationship(
        "DetectionHistory",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    analyses = relationship(
        "Analysis",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    revoked_tokens = relationship(
        "RevokedToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    password_reset_tokens = relationship(
        "PasswordResetToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    email_verification_tokens = relationship(
        "EmailVerificationToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    news_submissions = relationship(
        "NewsSubmission",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    id = Column(Integer, primary_key=True, index=True)
    jti = Column(String, unique=True, index=True, nullable=False)
    token_type = Column(String, nullable=False)  # "access" or "refresh"
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="revoked_tokens")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    token = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="password_reset_tokens")


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    token = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="email_verification_tokens")


class NewsSubmission(Base):
    __tablename__ = "news_submissions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)

    title = Column(String, nullable=True)
    raw_text = Column(String, nullable=False)
    cleaned_text = Column(String, nullable=False)
    source_url = Column(String, nullable=True)

    # Extracted NLP metrics
    word_count = Column(Integer, default=0, nullable=False)
    char_count = Column(Integer, default=0, nullable=False)
    sentence_count = Column(Integer, default=0, nullable=False)
    reading_ease_score = Column(Float, nullable=True)
    sensationalism_score = Column(Float, nullable=True)
    lexical_diversity = Column(Float, nullable=True)
    top_keywords = Column(String, nullable=True)  # JSON-encoded string

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="news_submissions")


class DetectionHistory(Base):
    __tablename__ = "detection_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    claim = Column(String, nullable=True)
    news_text = Column(String, nullable=True)
    verdict = Column(String, nullable=True)
    prediction = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    explanation = Column(String, nullable=True)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="detections")


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    input_text = Column(String, nullable=False)
    source_url = Column(String, nullable=True)

    status = Column(String, default="pending", nullable=False)

    verdict = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    explanation = Column(String, nullable=True)

    error_message = Column(String, nullable=True)

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="analyses")