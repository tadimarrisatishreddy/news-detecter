"""
Dashboard Router – Module 5
============================
All /dashboard endpoints.

Endpoints
---------
GET  /dashboard/me            — Personal dashboard (authenticated user)
GET  /dashboard/me/report     — Full exportable JSON report (authenticated user)
GET  /dashboard/admin         — System-wide stats (admin only)
GET  /dashboard/admin/report  — Full system-wide report (admin only)
GET  /dashboard/admin/users   — Per-user activity table (admin only)
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth import get_current_active_user, get_db, require_role
from models import User
from dashboard.schemas import AdminReport, SystemStats, UserDashboardStats, UserReport
from dashboard.service import (
    generate_admin_report,
    generate_user_report,
    get_admin_dashboard,
    get_user_dashboard,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard & Reports"])


# ---------------------------------------------------------------------------
# User endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/me",
    response_model=UserDashboardStats,
    summary="Personal dashboard statistics",
)
def user_dashboard(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Returns aggregated statistics for the authenticated user:
    - Detection counts & verdict breakdown
    - Fact-check counts & trust-score average
    - News submission counts & sensationalism average
    - Recent activity feeds (last 5 of each)
    """
    return get_user_dashboard(current_user, db)


@router.get(
    "/me/report",
    response_model=UserReport,
    summary="Export full personal report as JSON",
)
def user_report(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Exports the complete history of detections, fact-checks, and submissions
    for the authenticated user as a structured JSON report (all-time).
    """
    return generate_user_report(current_user, db)


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/admin",
    response_model=SystemStats,
    summary="System-wide admin dashboard",
)
def admin_dashboard(
    _admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """
    Returns platform-wide statistics (admin only):
    - Total users, detections, fact-checks, submissions
    - Global verdict & fact-check breakdowns
    - Top 5 flagged fake claims
    - Top 10 most active users
    """
    return get_admin_dashboard(db)


@router.get(
    "/admin/report",
    response_model=AdminReport,
    summary="Export full system-wide report as JSON (admin only)",
)
def admin_report(
    _admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """
    Exports the full platform report including system stats and
    per-user activity summary (admin only, all-time).
    """
    return generate_admin_report(db)


@router.get(
    "/admin/users",
    summary="Per-user activity table (admin only)",
)
def admin_users_activity(
    _admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """
    Returns a table of all users with their detection, fact-check,
    and submission counts — useful for monitoring user engagement.
    """
    stats = get_admin_dashboard(db)
    return {
        "total_users": stats.total_users,
        "users": [u.model_dump() for u in stats.most_active_users],
    }
