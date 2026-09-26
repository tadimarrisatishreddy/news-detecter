"""
Module 5 – Dashboard & Reports
================================
Provides user-level and admin-level dashboards with statistics,
activity summaries, trend data, and exportable reports.

Public API
----------
- router : APIRouter  — all dashboard endpoints (prefixed /dashboard)
"""

from .router import router

__all__ = ["router"]
