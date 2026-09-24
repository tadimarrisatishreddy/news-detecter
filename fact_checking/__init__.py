from fact_checking.trusted_sources import (
    AUTHORITY_WEIGHTS,
    TIER_FACT_CHECKER,
    TIER_GOVERNMENT,
    TIER_MAINSTREAM,
    TIER_NEWS_WIRE,
    TIER_UNVERIFIED,
    TRUSTED_DOMAINS,
    classify_domain,
    extract_domain,
)
from fact_checking.query_builder import build_verification_queries, extract_search_keywords
from fact_checking.stance_detector import calculate_lexical_overlap, classify_stance
from fact_checking.service import (
    default_factcheck_provider,
    default_gov_provider,
    verify_claim,
)

__all__ = [
    "classify_domain",
    "extract_domain",
    "TRUSTED_DOMAINS",
    "AUTHORITY_WEIGHTS",
    "TIER_GOVERNMENT",
    "TIER_FACT_CHECKER",
    "TIER_NEWS_WIRE",
    "TIER_MAINSTREAM",
    "TIER_UNVERIFIED",
    "build_verification_queries",
    "extract_search_keywords",
    "calculate_lexical_overlap",
    "classify_stance",
    "verify_claim",
    "default_gov_provider",
    "default_factcheck_provider",
]
