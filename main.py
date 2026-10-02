from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import Base, engine
from models import Analysis, DetectionHistory, User
from schemas import (
    AnalysisCreate,
    BatchDetectionRequest,
    BatchDetectionResponse,
    DetectionRequest,
    DetectionResponse,
    DetectionResponseItem,
)
from auth import (
    create_access_token as auth_create_access_token,
    get_current_active_user,
    get_current_user,
    get_db,
    require_role,
    router as auth_router,
)
from gemma_service import detect_fake_news, detect_fake_news_batch
from news_input import router as news_router1
from fact_checking.router import router as fact_checking_router
from dashboard import router as dashboard_router


class NewsRequest(BaseModel):
    claim: str


# Initialize database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AI Fake News Detector API",
    description="Backend API with user authentication, role-based access control, news detection, and fact checking.",
    version="1.0.0",
)

# Include Routers
app.include_router(auth_router)
app.include_router(news_router1)
app.include_router(fact_checking_router)
app.include_router(dashboard_router)

# Mount Static Files (Module 6 Frontend)
STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# Helper function for backward-compatibility in tests
def create_access_token(user_id: int, role: str = "user") -> str:
    token, _, _ = auth_create_access_token(user_id, role=role)
    return token


@app.get("/health", tags=["General"])
def health_check():
    """System health check endpoint for monitoring & deployment."""
    return {
        "status": "healthy",
        "service": "TruthLens AI Fake News Detector",
        "version": "1.0.0",
        "modules": [
            "1. Authentication & RBAC",
            "2. News Input & NLP Studio",
            "3. AI Detection (Gemma 3)",
            "4. Fact Checking & Government Verification",
            "5. Dashboard & Reports",
            "6. Modern Web Frontend & Deployment",
        ],
    }


@app.get("/api", tags=["General"])
def api_info():
    """API overview and documentation links."""
    return {
        "message": "Welcome to AI Fake News Detector API",
        "docs_url": "/docs",
        "auth_endpoints": "/auth",
    }


@app.get("/", tags=["General"])
def home(request: Request):
    """
    Root endpoint:
    - Serves the TruthLens Web Application (Module 6) when accessed via browser.
    - Returns JSON API metadata when requested with Accept: application/json.
    """
    accept = request.headers.get("accept", "")
    if "application/json" in accept and "text/html" not in accept:
        return {
            "message": "Welcome to AI Fake News Detector API",
            "docs_url": "/docs",
            "auth_endpoints": "/auth",
        }

    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))

    return {
        "message": "Welcome to AI Fake News Detector API",
        "docs_url": "/docs",
        "auth_endpoints": "/auth",
    }


@app.get("/profile", tags=["User Authentication"], deprecated=True)
def get_legacy_profile(current_user: User = Depends(get_current_active_user)):
    """Legacy profile endpoint for backward compatibility."""
    return {
        "username": current_user.username or current_user.full_name,
        "email": current_user.email,
        "role": current_user.role,
    }


# -----------------------------------------------------------------------------
# Protected Detection & Analysis Endpoints
# -----------------------------------------------------------------------------

@app.post("/detect", tags=["Detection"])
def detect_news(
    news: NewsRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    result = detect_fake_news(news.claim)

    new_detection = DetectionHistory(
        claim=news.claim,
        verdict=result.get("verdict"),
        confidence=result.get("confidence"),
        explanation=result.get("explanation"),
        user_id=current_user.id,
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


@app.get("/history", tags=["Detection"])
def get_history(
    limit: int = 20,
    current_user: User = Depends(get_current_active_user),
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


@app.post("/detect/batch", response_model=BatchDetectionResponse, tags=["Detection"])
def batch_detect_news(
    payload: BatchDetectionRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Batch analyze multiple news claims with Gemma AI."""
    results = []
    for claim in payload.claims:
        res = detect_fake_news(claim)

        detection = DetectionHistory(
            claim=claim,
            verdict=res.get("verdict"),
            confidence=res.get("confidence"),
            explanation=res.get("explanation"),
            user_id=current_user.id,
        )
        db.add(detection)

        results.append(
            DetectionResponseItem(
                claim=claim,
                verdict=res.get("verdict", "UNCERTAIN"),
                confidence=res.get("confidence", 0.0),
                explanation=res.get("explanation", ""),
                key_signals=res.get("key_signals", []),
            )
        )
    db.commit()

    return BatchDetectionResponse(
        total_processed=len(results),
        results=results,
    )


@app.post("/analyses", status_code=status.HTTP_201_CREATED, tags=["Analysis"])
def create_analysis(
    body: AnalysisCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Submit a news claim or article for AI analysis."""
    analysis = Analysis(
        user_id=current_user.id,
        input_text=body.input_text,
        source_url=body.source_url,
        status="pending",
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    try:
        analysis.status = "processing"
        db.commit()

        result = detect_fake_news(analysis.input_text)

        analysis.verdict = result.get("verdict")
        analysis.confidence = result.get("confidence")
        analysis.explanation = result.get("explanation")
        analysis.status = "completed"
    except Exception as e:
        analysis.status = "failed"
        analysis.error_message = str(e)

    db.commit()
    db.refresh(analysis)

    return {
        "id": analysis.id,
        "input_text": analysis.input_text,
        "source_url": analysis.source_url,
        "status": analysis.status,
        "verdict": analysis.verdict,
        "confidence": analysis.confidence,
        "explanation": analysis.explanation,
        "error_message": analysis.error_message,
        "created_at": analysis.created_at,
        "updated_at": analysis.updated_at,
    }


@app.get("/analyses", tags=["Analysis"])
def list_analyses(
    limit: int = 20,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List the authenticated user's own analyses."""
    analyses = (
        db.query(Analysis)
        .filter(Analysis.user_id == current_user.id)
        .order_by(Analysis.id.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": a.id,
            "input_text": a.input_text,
            "source_url": a.source_url,
            "status": a.status,
            "verdict": a.verdict,
            "confidence": a.confidence,
            "explanation": a.explanation,
            "error_message": a.error_message,
            "created_at": a.created_at,
            "updated_at": a.updated_at,
        }
        for a in analyses
    ]


@app.get("/analyses/{analysis_id}", tags=["Analysis"])
def get_analysis(
    analysis_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get a single analysis by ID. Users see only their own."""
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()

    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        )

    if current_user.role != "admin" and analysis.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        )

    return {
        "id": analysis.id,
        "input_text": analysis.input_text,
        "source_url": analysis.source_url,
        "status": analysis.status,
        "verdict": analysis.verdict,
        "confidence": analysis.confidence,
        "explanation": analysis.explanation,
        "error_message": analysis.error_message,
        "created_at": analysis.created_at,
        "updated_at": analysis.updated_at,
    }


# -----------------------------------------------------------------------------
# Admin-only Endpoints
# -----------------------------------------------------------------------------

@app.get("/admin/users", tags=["Admin"])
def list_users(
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """List all registered users (admin only)."""
    users = db.query(User).all()
    return [
        {
            "id": u.id,
            "full_name": u.full_name,
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "is_verified": u.is_verified,
            "created_at": u.created_at,
        }
        for u in users
    ]


@app.get("/admin/detections", tags=["Admin"])
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


@app.get("/admin/analyses", tags=["Admin"])
def admin_list_analyses(
    limit: int = 50,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """View all analyses across all users (admin only)."""
    analyses = (
        db.query(Analysis)
        .order_by(Analysis.id.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": a.id,
            "user_id": a.user_id,
            "input_text": a.input_text,
            "source_url": a.source_url,
            "status": a.status,
            "verdict": a.verdict,
            "confidence": a.confidence,
            "explanation": a.explanation,
            "error_message": a.error_message,
            "created_at": a.created_at,
            "updated_at": a.updated_at,
        }
        for a in analyses
    ]