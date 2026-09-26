from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fact_checking.providers.base import BaseEvidenceProvider, EvidenceItem
from fact_checking.providers.google_factcheck import GoogleFactCheckProvider
from fact_checking.providers.gov_registry import GovernmentRegistryProvider
from fact_checking.providers.mock_provider import MockEvidenceProvider
from fact_checking.stance_detector import classify_stance

default_gov_provider = GovernmentRegistryProvider()
default_factcheck_provider = GoogleFactCheckProvider()


def verify_claim(
    claim: str,
    check_government_only: bool = False,
    max_sources: int = 5,
    provider: Optional[BaseEvidenceProvider] = None,
) -> Dict[str, Any]:
    """
    Master fact-checking verification service:
    1. Queries authoritative registries and fact-checking providers.
    2. Runs stance detection on retrieved evidence snippets.
    3. Calculates authority-weighted factuality scores.
    4. Compiles citations and human-readable summary.
    """
    if not claim or not claim.strip():
        return {
            "claim": "",
            "status": "UNPROVEN",
            "verdict": "UNVERIFIED",
            "trust_score": 0.0,
            "summary": "No claim provided for fact-checking.",
            "evidence_count": 0,
            "evidence_sources": [],
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }

    # Select provider
    if provider is None:
        if check_government_only:
            provider = default_gov_provider
        else:
            provider = default_factcheck_provider

    evidence_items = provider.search_evidence(
        claim=claim,
        max_results=max_sources,
        government_only=check_government_only,
    )

    # Stance alignment
    support_weight = 0.0
    refute_weight = 0.0
    processed_sources: List[Dict[str, Any]] = []

    for item in evidence_items:
        stance, confidence = classify_stance(claim, item.snippet + " " + item.title)
        # If provider already set specific stance (e.g. from Google Fact Check API), preserve it
        if item.stance in ("SUPPORTS", "REFUTES"):
            stance = item.stance

        item.stance = stance
        weighted_score = item.authority_weight * max(0.6, confidence)

        if stance == "REFUTES":
            refute_weight += weighted_score
        elif stance == "SUPPORTS":
            support_weight += weighted_score

        processed_sources.append(
            {
                "source_name": item.source_name,
                "source_url": item.source_url,
                "domain": item.domain,
                "tier": item.tier,
                "authority_weight": item.authority_weight,
                "stance": item.stance,
                "title": item.title,
                "snippet": item.snippet,
                "published_date": item.published_date,
            }
        )

    # Determine overall verdict and trust score
    if refute_weight > support_weight and refute_weight >= 0.5:
        status = "REFUTED"
        verdict = "FALSE"
        trust_score = min(98.0, 70.0 + (refute_weight * 15.0))
        top_refuter = next((s["source_name"] for s in processed_sources if s["stance"] == "REFUTES"), "Authoritative records")
        summary = f"Claim is REFUTED by official evidence from {top_refuter}. Official records contradict this assertion."

    elif support_weight > refute_weight and support_weight >= 0.5:
        status = "VERIFIED"
        verdict = "TRUE"
        trust_score = min(98.0, 70.0 + (support_weight * 15.0))
        top_supporter = next((s["source_name"] for s in processed_sources if s["stance"] == "SUPPORTS"), "Official portals")
        summary = f"Claim is VERIFIED by authoritative records from {top_supporter}."


    elif support_weight > 0 and refute_weight > 0:
        status = "DISPUTED"
        verdict = "MISLEADING"
        trust_score = 55.0
        summary = "Mixed or conflicting evidence found across public and media archives. Claim may contain partial inaccuracies."

    else:
        status = "UNPROVEN"
        verdict = "UNVERIFIED"
        trust_score = 40.0
        summary = "No decisive confirmation or refutation found in indexed official government archives or fact-checking databases."

    return {
        "claim": claim.strip(),
        "status": status,
        "verdict": verdict,
        "trust_score": round(trust_score, 1),
        "summary": summary,
        "evidence_count": len(processed_sources),
        "evidence_sources": processed_sources,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }
