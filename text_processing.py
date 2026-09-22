from nlp import (
    calculate_readability,
    calculate_word_stats,
    clean_text,
    detect_sensationalism,
    extract_keywords,
    extract_nlp_features,
    split_into_sentences,
    tokenize_words,
)


def get_word_count(text: str) -> int:
    """Count words in text."""
    tokens = tokenize_words(text, lowercase=True, remove_punct=True)
    return len(tokens)


__all__ = [
    "clean_text",
    "get_word_count",
    "tokenize_words",
    "split_into_sentences",
    "calculate_word_stats",
    "calculate_readability",
    "detect_sensationalism",
    "extract_keywords",
    "extract_nlp_features",
]