import logging
from typing import Any, Dict, List, Optional

from ai.gemma_client import GemmaClient, default_gemma_client
from ai.parser import parse_ai_response
from ai.prompts import build_detection_prompt
from nlp import extract_nlp_features

logger = logging.getLogger("ai.service")


def calibrate_confidence(
    verdict: str,
    raw_confidence: float,
    nlp_features: Dict[str, Any],
) -> float:
    """
    Applies hybrid confidence calibration by reconciling LLM confidence
    with deterministic linguistic heuristics (sensationalism and readability).
    """
    sensationalism = nlp_features.get("sensationalism", {})
    sensationalism_score = sensationalism.get("sensationalism_score", 0.0)
    is_sensational = sensationalism.get("is_sensational", False)

    confidence = raw_confidence

    if verdict == "LIKELY_FAKE":
        # If the LLM predicts FAKE and NLP detects high sensationalism, reinforce certainty
        if is_sensational or sensationalism_score >= 0.4:
            boost = min(10.0, sensationalism_score * 12.0)
            confidence = min(99.0, confidence + boost)
        elif sensationalism_score <= 0.1:
            # Subtle fake news with objective tone: maintain LLM confidence
            confidence = max(55.0, confidence)

    elif verdict == "LIKELY_REAL":
        # If the LLM predicts REAL but text has extreme sensationalism, moderate confidence
        if sensationalism_score >= 0.6:
            penalty = min(20.0, sensationalism_score * 25.0)
            confidence = max(50.0, confidence - penalty)
        elif sensationalism_score <= 0.15:
            # Clean journalistic tone reinforces REAL verdict
            confidence = min(98.0, max(confidence, 80.0))

    return round(confidence, 1)


def detect_fake_news(
    claim: str,
    nlp_features: Optional[Dict[str, Any]] = None,
    client: Optional[GemmaClient] = None,
) -> Dict[str, Any]:
    """
    Master Detection Pipeline:
    1. Preprocesses text and computes linguistic NLP metrics.
    2. Builds structured prompt with context injection.
    3. Runs Gemma AI inference.
    4. Parses structured JSON response.
    5. Applies hybrid confidence calibration.
    """
    if not claim or not claim.strip():
        return {
            "verdict": "UNCERTAIN",
            "confidence": 0.0,
            "explanation": "No text or claim provided for analysis.",
            "key_signals": [],
            "manipulation_tactics": [],
            "nlp_summary": {},
            "raw_model_output": "",
        }

    # 1. NLP Feature Extraction
    if nlp_features is None:
        nlp_features = extract_nlp_features(claim)

    # 2. Prompt Construction
    messages = build_detection_prompt(claim, nlp_features=nlp_features)

    # 3. AI Inference
    ai_client = client or default_gemma_client
    try:
        raw_output = ai_client.generate_chat_response(messages)
    except Exception as e:
        logger.error(f"Error during AI inference: {e}")
        raw_output = ""

    # 4. Output Parsing
    parsed = parse_ai_response(raw_output, nlp_features=nlp_features)

    # 5. Hybrid Calibration
    final_confidence = calibrate_confidence(
        verdict=parsed["verdict"],
        raw_confidence=parsed["confidence"],
        nlp_features=nlp_features,
    )
    parsed["confidence"] = final_confidence

    # 6. Attach NLP Summary
    parsed["nlp_summary"] = {
        "word_count": nlp_features.get("statistics", {}).get("word_count", 0),
        "character_count": nlp_features.get("statistics", {}).get("character_count", 0),
        "sensationalism_score": nlp_features.get("sensationalism", {}).get("sensationalism_score", 0.0),
        "is_sensational": nlp_features.get("sensationalism", {}).get("is_sensational", False),
        "reading_ease": nlp_features.get("readability", {}).get("flesch_reading_ease", 0.0),
        "reading_level": nlp_features.get("readability", {}).get("reading_level", ""),
        "top_keywords": nlp_features.get("top_keywords", []),
    }

    return parsed


def detect_fake_news_batch(
    claims: List[str],
    client: Optional[GemmaClient] = None,
) -> List[Dict[str, Any]]:
    """
    Executes AI detection across a batch of news articles or claims.
    """
    results = []
    for text in claims:
        res = detect_fake_news(text, client=client)
        results.append(res)
    return results

