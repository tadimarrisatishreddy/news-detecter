import re
from typing import Dict, List, Optional
from nlp.tokenization import ENGLISH_STOPWORDS, tokenize_words


def extract_search_keywords(claim: str, max_keywords: int = 6) -> List[str]:
    """
    Extracts the most salient keywords and entities from a claim for search indexing.
    """
    if not claim:
        return []

    tokens = tokenize_words(claim, lowercase=False, remove_punct=True)
    # Filter out standard stopwords and single character noise
    meaningful = [
        t for t in tokens
        if t.lower() not in ENGLISH_STOPWORDS and len(t) > 1 and not t.isdigit()
    ]

    # Preserve numeric values / years / amounts if present (e.g. 2026, 50000, 50k)
    numbers_and_symbols = re.findall(r"\b(?:\$|₹|€)?\d+(?:,\d+)*(?:\.\d+)?(?:k|m|b|cr|lakh)?\b", claim, re.IGNORECASE)

    combined = []
    # Add numbers first as they are crucial fact-checking discriminators
    for n in numbers_and_symbols[:2]:
        if n not in combined:
            combined.append(n)

    for word in meaningful:
        if word not in combined:
            combined.append(word)
        if len(combined) >= max_keywords:
            break

    return combined


def build_verification_queries(
    claim: str,
    check_government_only: bool = False,
) -> Dict[str, str]:
    """
    Builds optimized search queries targeted at specific authority tiers.
    """
    keywords = extract_search_keywords(claim)
    core_query = " ".join(keywords) if keywords else claim.strip()

    queries = {
        "government_query": f"{core_query} (site:gov.in OR site:pib.gov.in OR site:.gov OR site:nic.in)",
        "factcheck_query": f"{core_query} fact check (site:pib.gov.in OR site:snopes.com OR site:politifact.com OR site:boomlive.in OR site:factcheck.org)",
        "newswire_query": f"{core_query} (site:reuters.com OR site:apnews.com OR site:bbc.com)",
        "general_verified_query": f"{core_query} official press release",
    }

    if check_government_only:
        return {
            "government_query": queries["government_query"],
            "pib_factcheck_query": f"{core_query} site:pib.gov.in",
        }

    return queries
