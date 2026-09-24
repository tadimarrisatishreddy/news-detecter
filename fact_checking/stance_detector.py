import re
from typing import Dict, List, Tuple
from nlp.tokenization import ENGLISH_STOPWORDS, tokenize_words

REFUTATION_MARKERS = {
    "fake", "hoax", "false", "debunked", "untrue", "clarification", "misleading",
    "fraudulent", "no such", "deny", "denies", "denied", "refutes", "refuted",
    "not approved", "not true", "rumor", "rumour", "phishing", "scam", "fabricated",
    "unfounded", "baseless", "incorrect", "disproven", "warning against",
}

SUPPORT_MARKERS = {
    "confirmed", "approved", "announced", "published", "official statement",
    "milestone", "verified", "agreed", "implemented", "enacted", "ratified",
    "launched", "established", "consensus", "declared", "concluded",
}


def calculate_lexical_overlap(claim: str, snippet: str) -> float:
    """Calculates Jaccard similarity between non-stopword tokens of claim and snippet."""
    claim_tokens = {
        t.lower() for t in tokenize_words(claim, remove_punct=True)
        if t.lower() not in ENGLISH_STOPWORDS and len(t) > 2
    }
    snippet_tokens = {
        t.lower() for t in tokenize_words(snippet, remove_punct=True)
        if t.lower() not in ENGLISH_STOPWORDS and len(t) > 2
    }

    if not claim_tokens or not snippet_tokens:
        return 0.0

    intersection = claim_tokens.intersection(snippet_tokens)
    union = claim_tokens.union(snippet_tokens)
    return round(len(intersection) / len(union), 3)


def classify_stance(claim: str, snippet: str) -> Tuple[str, float]:
    """
    Evaluates whether the evidence snippet SUPPORTS, REFUTES, or has NOT_ENOUGH_INFO on the claim.
    Returns: (stance, confidence)
    """
    if not snippet or not claim:
        return ("NOT_ENOUGH_INFO", 0.0)

    snippet_lower = snippet.lower()
    overlap = calculate_lexical_overlap(claim, snippet)

    # Check for strong refutation signals
    found_refutations = [m for m in REFUTATION_MARKERS if m in snippet_lower]
    found_supports = [m for m in SUPPORT_MARKERS if m in snippet_lower]

    if found_refutations:
        confidence = min(0.98, 0.70 + (len(found_refutations) * 0.1) + (overlap * 0.2))
        return ("REFUTES", round(confidence, 2))

    if found_supports and overlap >= 0.15:
        confidence = min(0.95, 0.65 + (len(found_supports) * 0.1) + (overlap * 0.2))
        return ("SUPPORTS", round(confidence, 2))

    if overlap >= 0.30:
        return ("SUPPORTS", round(0.50 + overlap * 0.4, 2))

    return ("NOT_ENOUGH_INFO", 0.40)
