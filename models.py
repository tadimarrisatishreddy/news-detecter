from sqlalchemy import Column, DateTime, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    role = Column(String, default="user")

    # IMPORTANT
    detections = relationship(
        "DetectionHistory",
        back_populates="user",
        cascade="all, delete-orphan"
    )


class DetectionHistory(Base):
    __tablename__ = "detection_history"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"))

    claim = Column(String)
    news_text = Column(String)
    verdict = Column(String)
    prediction = Column(String)
    confidence = Column(Float)
    explanation = Column(String)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
    )

    # IMPORTANT
    user = relationship(
        "User",
        back_populates="detections"
    )