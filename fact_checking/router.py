from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from dependencies import get_current_active_user, get_db
from models import EvidenceItemRecord, FactCheckRecord, User
from fact_checking.service import verify_claim
from fact_checking.trusted_sources import AUTHORITY_WEIGHTS, TRUSTED_DOMAINS
from schemas import (
    EvidenceSourceSchema,
    FactCheckRequest,
    FactCheckResponse,
    TrustedSourceItem,
    WhitelistResponse,
)

router = APIRouter(
    prefix="/fact-check",
    tags=["Fact Checking & Source Verification (Module 4)"],
)


# -----------------------------------------------------------------------------
# 1. Claim Verification Endpoint
# -----------------------------------------------------------------------------
@router.post(
    "/verify",
    response_model=FactCheckResponse,
    summary="Verify a news claim against authoritative government portals and fact-checkers",
)
def verify_news_claim(
    payload: FactCheckRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Cross-references news claim against official registries, government records (.gov, PIB),
    news wires (Reuters, AP), and verified fact-checking databases (ClaimReview):
    - Retrieves authoritative evidence snippets
    - Evaluates stance (SUPPORTS, REFUTES, UNRELATED)
    - Computes authority-weighted trust score (0-100%)
    - Persists verification and citations to database
    """
    result = verify_claim(
        claim=payload.claim,
        check_government_only=payload.check_government_only,
        max_sources=payload.max_sources,
    )

    # Persist in database
    record = FactCheckRecord(
        user_id=current_user.id,
        claim=result["claim"],
        status=result["status"],
        verdict=result["verdict"],
        trust_score=result["trust_score"],
        summary=result["summary"],
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    # Persist evidence items
    for item in result["evidence_sources"]:
        ev = EvidenceItemRecord(
            fact_check_id=record.id,
            source_name=item["source_name"],
            source_url=item["source_url"],
            domain=item.get("domain"),
            tier=item.get("tier"),
            authority_weight=item.get("authority_weight", 0.5),
            stance=item.get("stance", "NOT_ENOUGH_INFO"),
            title=item.get("title"),
            snippet=item.get("snippet"),
            published_date=item.get("published_date"),
        )
        db.add(ev)
    db.commit()

    result["id"] = record.id
    return FactCheckResponse(**result)


# -----------------------------------------------------------------------------
# 2. Trusted Sources Whitelist
# -----------------------------------------------------------------------------
@router.get(
    "/sources/whitelist",
    response_model=WhitelistResponse,
    summary="List all verified government, fact-checking, and news wire domains",
)
def get_trusted_sources_whitelist():
    """Returns the registry of whitelisted authoritative domains and their trust tiers."""
    items: List[TrustedSourceItem] = []
    for domain, info in TRUSTED_DOMAINS.items():
        tier = info["tier"]
        weight = AUTHORITY_WEIGHTS.get(tier, 0.5)
        items.append(
            TrustedSourceItem(
                domain=domain,
                name=info["name"],
                tier=tier,
                authority_weight=weight,
            )
        )

    return WhitelistResponse(
        total_sources=len(items),
        trusted_domains=items,
    )


# -----------------------------------------------------------------------------
# 3. User Fact Check History
# -----------------------------------------------------------------------------
@router.get(
    "/history",
    response_model=List[FactCheckResponse],
    summary="List past fact-check verifications for the authenticated user",
)
def get_user_fact_check_history(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Retrieves previous fact-check inquiries and verified citations."""
    records = (
        db.query(FactCheckRecord)
        .filter(FactCheckRecord.user_id == current_user.id)
        .order_by(FactCheckRecord.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    results = []
    for r in records:
        evidence_sources = [
            EvidenceSourceSchema(
                source_name=ev.source_name,
                source_url=ev.source_url,
                domain=ev.domain,
                tier=ev.tier,
                authority_weight=ev.authority_weight,
                stance=ev.stance,
                title=ev.title,
                snippet=ev.snippet,
                published_date=ev.published_date,
            )
            for ev in r.evidence_items
        ]
        results.append(
            FactCheckResponse(
                id=r.id,
                claim=r.claim,
                status=r.status,
                verdict=r.verdict,
                trust_score=r.trust_score,
                summary=r.summary or "",
                evidence_count=len(evidence_sources),
                evidence_sources=evidence_sources,
                verified_at=r.created_at.isoformat(),
            )
        )

    return results


# -----------------------------------------------------------------------------
# 4. Get Single Fact Check by ID
# -----------------------------------------------------------------------------
@router.get(
    "/history/{fact_check_id}",
    response_model=FactCheckResponse,
    summary="Retrieve a specific fact-check record and all citations by ID",
)
def get_fact_check_by_id(
    fact_check_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Retrieves a single fact-check result. Users can only access their own records."""
    record = db.query(FactCheckRecord).filter(FactCheckRecord.id == fact_check_id).first()

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fact-check record not found",
        )

    if current_user.role != "admin" and record.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fact-check record not found",
        )

    evidence_sources = [
        EvidenceSourceSchema(
            source_name=ev.source_name,
            source_url=ev.source_url,
            domain=ev.domain,
            tier=ev.tier,
            authority_weight=ev.authority_weight,
            stance=ev.stance,
            title=ev.title,
            snippet=ev.snippet,
            published_date=ev.published_date,
        )
        for ev in record.evidence_items
    ]

    return FactCheckResponse(
        id=record.id,
        claim=record.claim,
        status=record.status,
        verdict=record.verdict,
        trust_score=record.trust_score,
        summary=record.summary or "",
        evidence_count=len(evidence_sources),
        evidence_sources=evidence_sources,
        verified_at=record.created_at.isoformat(),
    )
