import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import Base, SessionLocal, engine
from models import DetectionHistory, User
from schemas import UserRegister
from auth import hash_password, verify_password
from gemma_service import detect_fake_news
from news_input import router as news_router1


SECRET_KEY = os.getenv("SECRET_KEY", "replace-this-development-secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


class NewsRequest(BaseModel):
    claim: str


Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AI Fake News Detector API",
    version="1.0",
)

app.include_router(news_router1)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_access_token(subject: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    return jwt.encode(
        {"sub": subject, "exp": expires_at},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        username = payload.get("sub")

        if not username:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()

    if user is None:
        raise credentials_exception

    return user


def require_role(*allowed_roles: str):
    """Dependency factory: restrict access to specific roles."""

    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource",
            )
        return current_user

    return role_checker


@app.get("/")
def home():
    return {"message": "Welcome to AI Fake News Detector"}


@app.post("/register", status_code=status.HTTP_201_CREATED)
def register(user: UserRegister, db: Session = Depends(get_db)):
    existing_user = (
        db.query(User)
        .filter((User.email == user.email) | (User.username == user.username))
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username is already registered",
        )

    new_user = User(
        full_name=user.full_name,
        username=user.username,
        email=user.email,
        password=hash_password(user.password),
        role="user",
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "User registered successfully"}


@app.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == form_data.username).first()

    if user is None or not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(user.username)

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


@app.get("/profile")
def profile(current_user: User = Depends(require_role("user", "admin"))):
    return {
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role,
    }


@app.post("/detect")
def detect_news(
    news: NewsRequest,
    user_id: int,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    result = detect_fake_news(news.claim)

    new_detection = DetectionHistory(
        claim=news.claim,
        verdict=result["verdict"],
        confidence=result["confidence"],
        explanation=result["explanation"],
        user_id=user_id,
    )

    db.add(new_detection)
    db.commit()
    db.refresh(new_detection)

    return {
        "message": "News analyzed successfully",
        "detection_id": new_detection.id,
        "claim": new_detection.claim,
        "verdict": new_detection.verdict,
        "confidence": new_detection.confidence,
        "explanation": new_detection.explanation,
        "created_at": new_detection.created_at,
    }


@app.get("/history")
def get_history(
    limit: int = 20,
    current_user: User = Depends(require_role("user", "admin")),
    db: Session = Depends(get_db),
):
    """Return detection history for the authenticated user."""
    detections = (
        db.query(DetectionHistory)
        .filter(DetectionHistory.user_id == current_user.id)
        .order_by(DetectionHistory.id.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": d.id,
            "claim": d.claim,
            "verdict": d.verdict,
            "confidence": d.confidence,
            "explanation": d.explanation,
            "created_at": d.created_at,
        }
        for d in detections
    ]


# -------------------------
# ADMIN-ONLY ENDPOINTS
# -------------------------


@app.get("/admin/users")
def list_users(
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """List all registered users (admin only)."""
    users = db.query(User).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role,
        }
        for u in users
    ]


@app.get("/admin/detections")
def all_detections(
    limit: int = 50,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """View all detection history across users (admin only)."""
    detections = (
        db.query(DetectionHistory)
        .order_by(DetectionHistory.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": d.id,
            "user_id": d.user_id,
            "claim": d.claim,
            "verdict": d.verdict,
            "confidence": d.confidence,
            "explanation": d.explanation,
            "created_at": d.created_at,
        }
        for d in detections
    ]