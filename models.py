from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
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

    news_text = Column(String)
    prediction = Column(String)
    confidence = Column(String)

    # IMPORTANT
    user = relationship(
        "User",
        back_populates="detections"
    )