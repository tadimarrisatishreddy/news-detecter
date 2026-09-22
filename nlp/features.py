import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from nlp.cleaning import clean_text
from nlp.tokenization import (
    ENGLISH_STOPWORDS,
    remove_stopwords,
    split_into_sentences,
    tokenize_words,
)

# Common sensationalist & clickbait trigger phrases/words in news media
SENSATIONAL_TRIGGERS = [
    "shocking", "bombshell", "miracle", "secret", "exposed", "unmasked",
    "you won't believe", "you will not believe", "what happened next",
    "will blow your mind", "blows mind", "breaking news", "conspiracy",
    "undeniable", "suppressed", "leaked", "urgent", "warning", "catastrophe",
    "devastating", "unbelievable", "mind blowing", "mind-blowing", "scandal",
    "cover up", "cover-up", "they don't want you to know", "magic pill",
    "cure all", "cure-all", "instant cure", "hoax", "hidden truth", "plot",
    "nightmare", "classified", "censored", "destroyed", "disaster", "viral",
    "explosive", "absolute proof", "100% proof", "proven true", "guaranteed",
]


def count_syllables_in_word(word: str) -> int:
    """
    Heuristic count of syllables in an English word.
    """
    word = word.lower().strip()
    if not word:
        return 0
    if len(word) <= 3:
        return 1

    # Remove non-alpha
    word = re.sub(r"[^a-z]", "", word)
    if not word:
        return 0

    # Exceptions & common endings
    word = re.sub(r"(?:[^laeiouy]|ed|es|e)$", "", word)
    if not word:
        return 1

    # Count vowel groups
    vowel_groups = re.findall(r"[aeiouy]{1,2}", word)
    count = len(vowel_groups)
    return max(1, count)


def calculate_readability(
    text: str,
    sentences: Optional[List[str]] = None,
    tokens: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Calculates readability metrics including Flesch Reading Ease score
    and Flesch-Kincaid Grade Level.
    """
    if sentences is None:
        sentences = split_into_sentences(text)
    if tokens is None:
        tokens = tokenize_words(text, lowercase=True, remove_punct=True)

    num_sentences = max(1, len(sentences))
    num_words = max(1, len(tokens))

    # Total syllables
    total_syllables = sum(count_syllables_in_word(word) for word in tokens)
    if total_syllables == 0:
        total_syllables = num_words

    asl = num_words / num_sentences  # Average Sentence Length
    asw = total_syllables / num_words  # Average Syllables per Word

    # Standard Flesch Reading Ease formula
    # Higher score = easier to read (0-100 typical scale)
    flesch_score = 206.835 - (1.015 * asl) - (84.6 * asw)
    flesch_score = max(0.0, min(100.0, round(flesch_score, 2)))

    # Flesch-Kincaid Grade Level
    fk_grade = (0.39 * asl) + (11.8 * asw) - 15.59
    fk_grade = max(0.0, round(fk_grade, 2))

    # Readability category
    if flesch_score >= 90:
        reading_level = "Very Easy"
    elif flesch_score >= 70:
        reading_level = "Easy"
    elif flesch_score >= 60:
        reading_level = "Standard"
    elif flesch_score >= 50:
        reading_level = "Fairly Difficult"
    elif flesch_score >= 30:
        reading_level = "Difficult"
    else:
        reading_level = "Very Difficult"

    return {
        "flesch_reading_ease": flesch_score,
        "grade_level": fk_grade,
        "reading_level": reading_level,
    }


def calculate_word_stats(
    text: str,
    tokens: Optional[List[str]] = None,
    sentences: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Calculates word counts, character counts, sentence statistics, and lexical diversity.
    """
    if tokens is None:
        tokens = tokenize_words(text, lowercase=True, remove_punct=True)
    if sentences is None:
        sentences = split_into_sentences(text)

    char_count = len(text)
    char_count_no_spaces = len(re.sub(r"\s+", "", text))
    word_count = len(tokens)
    unique_words = len(set(tokens))
    sentence_count = len(sentences)

    # Lexical diversity (Type-Token Ratio)
    lexical_diversity = round(unique_words / max(1, word_count), 4)

    # Average word and sentence lengths
    avg_word_length = round(
        sum(len(t) for t in tokens) / max(1, word_count), 2
    ) if word_count > 0 else 0.0

    avg_sentence_length = round(
        word_count / max(1, sentence_count), 2
    ) if sentence_count > 0 else 0.0

    return {
        "character_count": char_count,
        "character_count_no_spaces": char_count_no_spaces,
        "word_count": word_count,
        "unique_word_count": unique_words,
        "sentence_count": sentence_count,
        "lexical_diversity": lexical_diversity,
        "avg_word_length": avg_word_length,
        "avg_sentence_length": avg_sentence_length,
    }


def detect_sensationalism(
    text: str,
    tokens: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Analyzes text for stylistic sensationalism, shouting patterns (ALL-CAPS),
    punctuation inflation, and clickbait keyword triggers.
    Returns a composite score from 0.0 (objective) to 1.0 (highly sensational).
    """
    if not text or not text.strip():
        return {
            "sensationalism_score": 0.0,
            "is_sensational": False,
            "caps_ratio": 0.0,
            "exclamation_count": 0,
            "question_cluster_count": 0,
            "trigger_words_found": [],
        }

    raw_words = re.findall(r"\b[A-Za-z0-9]+\b", text)
    total_raw_words = len(raw_words)

    # 1. ALL-CAPS words (length >= 2, e.g. "SHOCKING", "SCANDAL")
    all_caps_words = [
        w for w in raw_words if len(w) >= 2 and w.isupper() and not w.isdigit()
    ]
    caps_ratio = len(all_caps_words) / max(1, total_raw_words)

    # 2. Punctuation intensity
    exclamation_count = len(re.findall(r"!", text))
    multiple_exclamations = len(re.findall(r"!{2,}", text))
    multiple_questions = len(re.findall(r"\?{2,}", text))

    # 3. Sensational clickbait triggers
    lowered_text = text.lower()
    found_triggers = [
        trigger for trigger in SENSATIONAL_TRIGGERS
        if re.search(rf"\b{re.escape(trigger)}\b", lowered_text)
    ]

    # Weighted composite score formula
    # - Caps ratio contributes up to 0.35
    # - Trigger words contribute up to 0.40
    # - Punctuation clusters contribute up to 0.25
    caps_component = min(0.35, caps_ratio * 1.5)
    trigger_component = min(0.40, len(found_triggers) * 0.12)
    punct_component = min(
        0.25,
        (exclamation_count * 0.05) + (multiple_exclamations * 0.1) + (multiple_questions * 0.1),
    )

    total_score = round(caps_component + trigger_component + punct_component, 3)
    total_score = min(1.0, total_score)

    is_sensational = total_score >= 0.35

    return {
        "sensationalism_score": total_score,
        "is_sensational": is_sensational,
        "caps_ratio": round(caps_ratio, 4),
        "exclamation_count": exclamation_count,
        "question_cluster_count": multiple_questions,
        "trigger_words_found": found_triggers,
    }


def extract_keywords(
    tokens: List[str],
    top_k: int = 5,
    min_length: int = 3,
) -> List[Tuple[str, int]]:
    """
    Extracts top informative keywords and their frequencies from tokens
    after stopword and length filtering.
    """
    filtered = [
        t.lower() for t in tokens
        if len(t) >= min_length and t.lower() not in ENGLISH_STOPWORDS and not t.isdigit()
    ]
    counter = Counter(filtered)
    return counter.most_common(top_k)


def extract_nlp_features(text: str) -> Dict[str, Any]:
    """
    Master feature extraction pipeline for raw news input.
    """
    cleaned = clean_text(text, lowercase=True, preserve_sentence_punct=False)
    sentences = split_into_sentences(text)
    tokens = tokenize_words(cleaned, lowercase=True, remove_punct=True)
    filtered_tokens = remove_stopwords(tokens)

    stats = calculate_word_stats(text, tokens=tokens, sentences=sentences)
    readability = calculate_readability(text, sentences=sentences, tokens=tokens)
    sensationalism = detect_sensationalism(text, tokens=tokens)
    keywords = extract_keywords(tokens, top_k=5)

    return {
        "raw_text": text,
        "cleaned_text": cleaned,
        "sentences": sentences,
        "tokens": tokens,
        "tokens_no_stopwords": filtered_tokens,
        "statistics": stats,
        "readability": readability,
        "sensationalism": sensationalism,
        "top_keywords": [kw[0] for kw in keywords],
        "top_keywords_with_freq": [{"keyword": kw[0], "count": kw[1]} for kw in keywords],
    }

