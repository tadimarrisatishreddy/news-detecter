"""
Backward-compatibility wrapper for Gemma AI fake news detection service.
"""
from typing import Any, Dict, Optional
from ai.service import detect_fake_news as ai_detect_fake_news, detect_fake_news_batch


def detect_fake_news(claim: str, nlp_features: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Analyzes a news claim or article text to predict its veracity.
    """
    return ai_detect_fake_news(claim, nlp_features=nlp_features)


__all__ = ["detect_fake_news", "detect_fake_news_batch"]