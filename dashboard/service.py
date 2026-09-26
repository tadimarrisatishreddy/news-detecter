"""
Dashboard Service – Module 5
=============================
Pure-function aggregation logic over SQLAlchemy sessions.
No HTTP concerns here — all query-and-compute work lives in this file.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from models import (
    Analysis,
    DetectionHistory,
    FactCheckRecord,
    NewsSubmission,
    User,
)
from dashboard.schemas import (
    AdminReport,
    DetectionReportItem,
    FactCheckBreakdown,
    FactCheckReportItem,
    RecentDetectionItem,
    RecentFactCheckItem,
    RecentSubmissionItem,
    SubmissionReportItem,
    SystemStats,
    TopFlaggedClaim,
    UserActivitySummary,
    UserDashboardStats,
    UserReport,
    VerdictBreakdown,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_avg(values: list[float], default: float = 0.0) -> float:
    return round(sum(values) / len(values), 4) if values else default


def _verdict_breakdown(verdicts: list[str]) -> VerdictBreakdown:
    counts: Counter = Counter(v.upper() if v else "OTHER" for v in verdicts)
    return VerdictBreakdown(
        LIKELY_FAKE=counts.get("LIKELY_FAKE", 0),
        LIKELY_REAL=counts.get("LIKELY_REAL", 0),
        UNCERTAIN=counts.get("UNCERTAIN", 0),
        MISLEADING=counts.get("MISLEADING", 0),
        OTHER=sum(v for k, v in counts.items()
                  if k not in {"LIKELY_FAKE", "LIKELY_REAL", "UNCERTAIN", "MISLEADING"}),
    )


def _fc_breakdown(statuses: list[str]) -> FactCheckBreakdown:
    counts: Counter = Counter(s.upper() if s else "UNPROVEN" for s in statuses)
    return FactCheckBreakdown(
        VERIFIED=counts.get("VERIFIED", 0),
        REFUTED=counts.get("REFUTED", 0),
        DISPUTED=counts.get("DISPUTED", 0),
        UNPROVEN=counts.get("UNPROVEN", 0),
    )


# ---------------------------------------------------------------------------
# User-level aggregation
# ---------------------------------------------------------------------------

def get_user_dashboard(user: User, db: Session) -> UserDashboardStats:
    """Build the personal dashboard for *user*."""

    # --- Detection stats ---
    detections = (
        db.query(DetectionHistory)
        .filter(DetectionHistory.user_id == user.id)
        .order_by(DetectionHistory.id.desc())
        .all()
    )
    verdicts = [d.verdict for d in detections]
    confidences = [d.confidence for d in detections if d.confidence is not None]

    recent_detections = [
        RecentDetectionItem(
            id=d.id,
            claim=(d.claim or "")[:120],
            verdict=d.verdict,
            confidence=d.confidence,
            created_at=d.created_at,
        )
        for d in detections[:5]
    ]

    # --- Fact-check stats ---
    fact_checks = (
        db.query(FactCheckRecord)
        .filter(FactCheckRecord.user_id == user.id)
        .order_by(FactCheckRecord.id.desc())
        .all()
    )
    fc_statuses = [fc.status for fc in fact_checks]
    trust_scores = [fc.trust_score for fc in fact_checks if fc.trust_score is not None]

    recent_fact_checks = [
        RecentFactCheckItem(
            id=fc.id,
            claim=fc.claim[:120],
            status=fc.status,
            trust_score=fc.trust_score,
            created_at=fc.created_at,
        )
        for fc in fact_checks[:5]
    ]

    # --- Submission stats ---
    submissions = (
        db.query(NewsSubmission)
        .filter(NewsSubmission.user_id == user.id)
        .order_by(NewsSubmission.id.desc())
        .all()
    )
    sens_scores = [s.sensationalism_score for s in submissions if s.sensationalism_score is not None]
    word_counts = [float(s.word_count) for s in submissions]

    recent_submissions = [
        RecentSubmissionItem(
            id=s.id,
            title=s.title,
            word_count=s.word_count,
            sensationalism_score=s.sensationalism_score,
            created_at=s.created_at,
        )
        for s in submissions[:5]
    ]

    return UserDashboardStats(
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        member_since=user.created_at,
        # Detection
        total_detections=len(detections),
        verdict_breakdown=_verdict_breakdown(verdicts),
        avg_detection_confidence=_safe_avg(confidences),
        # Fact-check
        total_fact_checks=len(fact_checks),
        fact_check_breakdown=_fc_breakdown(fc_statuses),
        avg_trust_score=_safe_avg(trust_scores),
        # Submissions
        total_submissions=len(submissions),
        avg_sensationalism_score=_safe_avg(sens_scores),
        avg_word_count=_safe_avg(word_counts),
        # Feeds
        recent_detections=recent_detections,
        recent_fact_checks=recent_fact_checks,
        recent_submissions=recent_submissions,
        generated_at=_now(),
    )


# ---------------------------------------------------------------------------
# Admin-level aggregation
# ---------------------------------------------------------------------------

def _user_activity_summary(user: User, db: Session) -> UserActivitySummary:
    det_count = db.query(DetectionHistory).filter(DetectionHistory.user_id == user.id).count()
    fc_count = db.query(FactCheckRecord).filter(FactCheckRecord.user_id == user.id).count()
    sub_count = db.query(NewsSubmission).filter(NewsSubmission.user_id == user.id).count()
    return UserActivitySummary(
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        total_detections=det_count,
        total_fact_checks=fc_count,
        total_submissions=sub_count,
        member_since=user.created_at,
    )


def _top_flagged_claims(db: Session, limit: int = 5) -> List[TopFlaggedClaim]:
    """Return the most-detected fake/misleading claims globally."""
    rows = db.query(DetectionHistory).filter(
        DetectionHistory.verdict.in_(["LIKELY_FAKE", "MISLEADING"])
    ).all()

    claim_groups: dict[str, list[float]] = defaultdict(list)
    claim_verdict: dict[str, str] = {}
    for row in rows:
        key = (row.claim or "").strip().lower()[:200]
        if key:
            claim_groups[key].append(row.confidence or 0.0)
            claim_verdict[key] = row.verdict or "LIKELY_FAKE"

    results = sorted(
        claim_groups.items(),
        key=lambda kv: len(kv[1]),
        reverse=True,
    )[:limit]

    return [
        TopFlaggedClaim(
            claim=claim[:200],
            verdict=claim_verdict[claim],
            times_detected=len(confs),
            avg_confidence=round(sum(confs) / len(confs), 4),
        )
        for claim, confs in results
    ]


def get_admin_dashboard(db: Session) -> SystemStats:
    """Build the system-wide admin dashboard."""
    all_users = db.query(User).all()

    all_detections = db.query(DetectionHistory).all()
    all_analyses = db.query(Analysis).all()
    all_fact_checks = db.query(FactCheckRecord).all()
    all_submissions = db.query(NewsSubmission).all()

    verdicts = [d.verdict for d in all_detections]
    confidences = [d.confidence for d in all_detections if d.confidence is not None]

    fc_statuses = [fc.status for fc in all_fact_checks]
    trust_scores = [fc.trust_score for fc in all_fact_checks if fc.trust_score is not None]

    # Most active users (sorted by total activity)
    user_summaries = [_user_activity_summary(u, db) for u in all_users]
    most_active = sorted(
        user_summaries,
        key=lambda s: s.total_detections + s.total_fact_checks + s.total_submissions,
        reverse=True,
    )[:10]

    return SystemStats(
        total_users=len(all_users),
        active_users=sum(1 for u in all_users if u.is_active),
        total_detections=len(all_detections),
        total_analyses=len(all_analyses),
        total_fact_checks=len(all_fact_checks),
        total_submissions=len(all_submissions),
        global_verdict_breakdown=_verdict_breakdown(verdicts),
        global_fact_check_breakdown=_fc_breakdown(fc_statuses),
        avg_detection_confidence=_safe_avg(confidences),
        avg_trust_score=_safe_avg(trust_scores),
        top_flagged_claims=_top_flagged_claims(db),
        most_active_users=most_active,
        generated_at=_now(),
    )


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def generate_user_report(user: User, db: Session) -> UserReport:
    """Generate a full exportable report for the authenticated user."""
    detections = (
        db.query(DetectionHistory)
        .filter(DetectionHistory.user_id == user.id)
        .order_by(DetectionHistory.created_at.asc())
        .all()
    )
    fact_checks = (
        db.query(FactCheckRecord)
        .filter(FactCheckRecord.user_id == user.id)
        .order_by(FactCheckRecord.created_at.asc())
        .all()
    )
    submissions = (
        db.query(NewsSubmission)
        .filter(NewsSubmission.user_id == user.id)
        .order_by(NewsSubmission.created_at.asc())
        .all()
    )

    return UserReport(
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        report_period="all-time",
        detection_count=len(detections),
        fact_check_count=len(fact_checks),
        submission_count=len(submissions),
        detections=[
            DetectionReportItem(
                id=d.id,
                claim=d.claim,
                verdict=d.verdict,
                confidence=d.confidence,
                explanation=d.explanation,
                created_at=d.created_at,
            )
            for d in detections
        ],
        fact_checks=[
            FactCheckReportItem(
                id=fc.id,
                claim=fc.claim,
                status=fc.status,
                verdict=fc.verdict,
                trust_score=fc.trust_score,
                summary=fc.summary,
                created_at=fc.created_at,
            )
            for fc in fact_checks
        ],
        submissions=[
            SubmissionReportItem(
                id=s.id,
                title=s.title,
                source_url=s.source_url,
                word_count=s.word_count,
                sensationalism_score=s.sensationalism_score,
                reading_ease_score=s.reading_ease_score,
                top_keywords=s.top_keywords,
                created_at=s.created_at,
            )
            for s in submissions
        ],
        generated_at=_now(),
    )


def generate_admin_report(db: Session) -> AdminReport:
    """Generate a system-wide report (admin only)."""
    system_stats = get_admin_dashboard(db)
    all_users = db.query(User).all()
    user_summaries = [_user_activity_summary(u, db) for u in all_users]

    return AdminReport(
        report_period="all-time",
        system_stats=system_stats,
        all_users=user_summaries,
        generated_at=_now(),
    )
