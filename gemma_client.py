"""
Backward-compatibility wrapper for Gemma AI client.
"""
from ai.gemma_client import GemmaClient, default_gemma_client
from ai.prompts import build_detection_prompt


def analyze_news(news_text: str) -> str:
    """
    Sends news text to Gemma and returns raw response string.
    """
    messages = build_detection_prompt(news_text)
    return default_gemma_client.generate_chat_response(messages)


__all__ = ["analyze_news", "GemmaClient", "default_gemma_client"]