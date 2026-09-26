"""
Dashboard Schemas – Module 5
============================
Pydantic models for all /dashboard endpoint responses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


# ---------------------------------------------------------------------------
# Shared primitives
# ---------------------------------------------------------------------------

class VerdictBreakdown(BaseModel):
    """Count of each AI verdict label."""
    LIKELY_FAKE: int = 0
    LIKELY_REAL: int = 0
    UNCERTAIN: int = 0
    MISLEADING: int = 0
    OTHER: int = 0


class FactCheckBreakdown(BaseModel):
    """Count of each fact-check status."""
    VERIFIED: int = 0
    REFUTED: int = 0
    DISPUTED: int = 0
    UNPROVEN: int = 0


class RecentDetectionItem(BaseModel):
    """Compact representation of a single detection for activity feeds."""
    id: int
    claim: str
    verdict: Optional[str]
    confidence: Optional[float]
    created_at: datetime


class RecentFactCheckItem(BaseModel):
    """Compact representation of a single fact-check for activity feeds."""
    id: int
    claim: str
    status: str
    trust_score: float
    created_at: datetime


class RecentSubmissionItem(BaseModel):
    """Compact representation of a news submission for activity feeds."""
    id: int
    title: Optional[str]
    word_count: int
    sensationalism_score: Optional[float]
    created_at: datetime


# ---------------------------------------------------------------------------
# User Dashboard
# ---------------------------------------------------------------------------

class UserDashboardStats(BaseModel):
    """Aggregated statistics for a single authenticated user."""
    user_id: int
    full_name: str
    email: str
    role: str
    member_since: datetime

    # Detection stats
    total_detections: int
    verdict_breakdown: VerdictBreakdown
    avg_detection_confidence: float  # 0.0 – 1.0

    # Fact-check stats
    total_fact_checks: int
    fact_check_breakdown: FactCheckBreakdown
    avg_trust_score: float  # 0 – 100

    # News submission stats
    total_submissions: int
    avg_sensationalism_score: float  # 0.0 – 1.0
    avg_word_count: float

    # Activity feed (latest 5 of each)
    recent_detections: List[RecentDetectionItem] = Field(default_factory=list)
    recent_fact_checks: List[RecentFactCheckItem] = Field(default_factory=list)
    recent_submissions: List[RecentSubmissionItem] = Field(default_factory=list)

    generated_at: datetime


# ---------------------------------------------------------------------------
# Admin Dashboard
# ---------------------------------------------------------------------------

class UserActivitySummary(BaseModel):
    """Per-user summary row for the admin dashboard."""
    user_id: int
    full_name: str
    email: str
    role: str
    is_active: bool
    total_detections: int
    total_fact_checks: int
    total_submissions: int
    member_since: datetime


class TopFlaggedClaim(BaseModel):
    """Most-detected fake or misleading claims across all users."""
    claim: str
    verdict: str
    times_detected: int
    avg_confidence: float


class SystemStats(BaseModel):
    """Platform-wide aggregated statistics for admin overview."""
    total_users: int
    active_users: int
    total_detections: int
    total_analyses: int
    total_fact_checks: int
    total_submissions: int

    # Verdict distribution across ALL detections
    global_verdict_breakdown: VerdictBreakdown

    # Fact-check distribution across ALL checks
    global_fact_check_breakdown: FactCheckBreakdown

    # Averages
    avg_detection_confidence: float
    avg_trust_score: float

    # Top suspicious claims
    top_flagged_claims: List[TopFlaggedClaim] = Field(default_factory=list)

    # Per-user leaderboard (most active)
    most_active_users: List[UserActivitySummary] = Field(default_factory=list)

    generated_at: datetime


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

class DetectionReportItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    claim: Optional[str]
    verdict: Optional[str]
    confidence: Optional[float]
    explanation: Optional[str]
    created_at: datetime


class FactCheckReportItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    claim: str
    status: str
    verdict: str
    trust_score: float
    summary: Optional[str]
    created_at: datetime


class SubmissionReportItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: Optional[str]
    source_url: Optional[str]
    word_count: int
    sensationalism_score: Optional[float]
    reading_ease_score: Optional[float]
    top_keywords: Optional[str]
    created_at: datetime


class UserReport(BaseModel):
    """Full exportable report for the authenticated user."""
    user_id: int
    full_name: str
    email: str
    report_period: str  # e.g. "all-time"

    detection_count: int
    fact_check_count: int
    submission_count: int

    detections: List[DetectionReportItem] = Field(default_factory=list)
    fact_checks: List[FactCheckReportItem] = Field(default_factory=list)
    submissions: List[SubmissionReportItem] = Field(default_factory=list)

    generated_at: datetime


class AdminReport(BaseModel):
    """Full exportable system-wide report (admin only)."""
    report_period: str
    system_stats: SystemStats
    all_users: List[UserActivitySummary] = Field(default_factory=list)
    generated_at: datetime
