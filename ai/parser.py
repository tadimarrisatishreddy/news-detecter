import json
import re
from typing import Any, Dict, List, Optional


VALID_VERDICTS = {"LIKELY_REAL", "LIKELY_FAKE", "UNCERTAIN"}

VERDICT_SYNONYMS = {
    "real": "LIKELY_REAL",
    "likely real": "LIKELY_REAL",
    "likely_real": "LIKELY_REAL",
    "true": "LIKELY_REAL",
    "factual": "LIKELY_REAL",
    "verified": "LIKELY_REAL",
    "fake": "LIKELY_FAKE",
    "likely fake": "LIKELY_FAKE",
    "likely_fake": "LIKELY_FAKE",
    "false": "LIKELY_FAKE",
    "misinformation": "LIKELY_FAKE",
    "disinformation": "LIKELY_FAKE",
    "hoax": "LIKELY_FAKE",
    "uncertain": "UNCERTAIN",
    "unverified": "UNCERTAIN",
    "inconclusive": "UNCERTAIN",
    "disputed": "UNCERTAIN",
    "mixed": "UNCERTAIN",
}


def normalize_verdict(raw_verdict: str) -> str:
    """Normalizes any raw verdict string into LIKELY_REAL, LIKELY_FAKE, or UNCERTAIN."""
    if not raw_verdict:
        return "UNCERTAIN"

    cleaned = raw_verdict.strip().lower().replace("-", " ").replace("_", " ")

    # Direct synonym lookup
    if cleaned in VERDICT_SYNONYMS:
        return VERDICT_SYNONYMS[cleaned]

    # Partial substring matches
    if "fake" in cleaned or "false" in cleaned or "hoax" in cleaned:
        return "LIKELY_FAKE"
    if "real" in cleaned or "true" in cleaned or "factual" in cleaned:
        return "LIKELY_REAL"
    if "uncertain" in cleaned or "unverified" in cleaned or "unknown" in cleaned:
        return "UNCERTAIN"

    return "UNCERTAIN"


def normalize_confidence(raw_confidence: Any, default: float = 70.0) -> float:
    """Safely converts confidence to a float between 0.0 and 100.0."""
    try:
        if isinstance(raw_confidence, str):
            # Extract number from string like '95%', '0.85', '95/100'
            clean_str = re.sub(r"[^\d.]", "", raw_confidence)
            val = float(clean_str)
        else:
            val = float(raw_confidence)

        # If value is given as probability (e.g. 0.85), convert to 0-100 scale
        if 0.0 <= val <= 1.0:
            val = val * 100.0

        return max(0.0, min(100.0, round(val, 2)))
    except (ValueError, TypeError):
        return default


def extract_json_block(text: str) -> Optional[dict]:
    """Extracts and parses JSON object from a string, handling markdown fences."""
    if not text:
        return None

    # 1. Try direct parsing
    try:
        data = json.loads(text.strip())
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # 2. Try extracting from markdown ```json ... ```
    json_fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_fence:
        try:
            data = json.loads(json_fence.group(1))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    # 3. Try finding first '{' and matching '}'
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        json_candidate = text[first_brace : last_brace + 1]
        try:
            data = json.loads(json_candidate)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    return None


def parse_key_value_fallback(text: str) -> Optional[dict]:
    """Parses key-value formatted text (e.g. VERDICT: ... CONFIDENCE: ...)."""
    if not text:
        return None

    verdict_match = re.search(r"(?:verdict|prediction):\s*([a-zA-Z_ ]+)", text, re.IGNORECASE)
    confidence_match = re.search(r"(?:confidence|certainty|score):\s*([\d.]+)", text, re.IGNORECASE)
    explanation_match = re.search(
        r"(?:explanation|reason|reasoning|analysis):\s*(.+?)(?=(?:\n[A-Z_]+:|$))",
        text,
        re.IGNORECASE | re.DOTALL,
    )

    if verdict_match:
        verdict = verdict_match.group(1).strip()
        confidence = float(confidence_match.group(1)) if confidence_match else 75.0
        explanation = (
            explanation_match.group(1).strip()
            if explanation_match
            else "Analysis based on semantic and contextual features."
        )

        return {
            "verdict": verdict,
            "confidence": confidence,
            "explanation": explanation,
            "key_signals": [],
            "manipulation_tactics": [],
        }

    return None


def heuristic_fallback_from_nlp(nlp_features: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Generates an emergency rule-based verdict if AI is offline or parsing fails."""
    if not nlp_features:
        return {
            "verdict": "UNCERTAIN",
            "confidence": 50.0,
            "explanation": "Insufficient information to evaluate factual validity.",
            "key_signals": ["Inconclusive textual signals"],
            "manipulation_tactics": [],
        }

    sensationalism = nlp_features.get("sensationalism", {})
    score = sensationalism.get("sensationalism_score", 0.0)
    triggers = sensationalism.get("trigger_words_found", [])
    is_sensational = sensationalism.get("is_sensational", False)

    if is_sensational or score >= 0.45:
        return {
            "verdict": "LIKELY_FAKE",
            "confidence": min(95.0, round(50.0 + (score * 50.0), 1)),
            "explanation": f"High sensationalism ({score:.2f}) and clickbait markers ({', '.join(triggers) if triggers else 'exclamations'}) suggest likely misinformation or hyperbole.",
            "key_signals": triggers if triggers else ["High sensationalism score", "Exclamation inflation"],
            "manipulation_tactics": ["Emotional appeal / sensationalism", "Clickbait framing"],
        }
    elif score <= 0.15:
        return {
            "verdict": "LIKELY_REAL",
            "confidence": 75.0,
            "explanation": "Objective language and neutral linguistic tone typical of factual reporting.",
            "key_signals": ["Neutral tone", "Absence of sensationalist language"],
            "manipulation_tactics": [],
        }
    else:
        return {
            "verdict": "UNCERTAIN",
            "confidence": 60.0,
            "explanation": "Moderate tone with mixed linguistic markers. Further factual verification recommended.",
            "key_signals": ["Mixed linguistic markers"],
            "manipulation_tactics": [],
        }


def parse_ai_response(
    raw_response: str,
    nlp_features: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Master parser: Converts raw LLM output into a validated, normalized detection dictionary.
    """
    parsed = extract_json_block(raw_response)

    if not parsed:
        parsed = parse_key_value_fallback(raw_response)

    if not parsed:
        # Fall back to heuristic assessment
        fallback = heuristic_fallback_from_nlp(nlp_features)
        fallback["raw_model_output"] = raw_response
        return fallback

    # Extract & normalize fields
    raw_verdict = parsed.get("verdict", "")
    verdict = normalize_verdict(raw_verdict)
    confidence = normalize_confidence(parsed.get("confidence", 70.0))
    explanation = parsed.get("explanation", "").strip() or "Analysis completed successfully."
    key_signals = parsed.get("key_signals", [])
    if not isinstance(key_signals, list):
        key_signals = [str(key_signals)] if key_signals else []
    manipulation_tactics = parsed.get("manipulation_tactics", [])
    if not isinstance(manipulation_tactics, list):
        manipulation_tactics = [str(manipulation_tactics)] if manipulation_tactics else []

    return {
        "verdict": verdict,
        "confidence": confidence,
        "explanation": explanation,
        "key_signals": key_signals,
        "manipulation_tactics": manipulation_tactics,
        "raw_model_output": raw_response,
    }

