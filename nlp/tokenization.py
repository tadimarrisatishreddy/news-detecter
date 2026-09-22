import re
from typing import List, Optional, Set, Tuple

# Standard comprehensive English stopwords set
ENGLISH_STOPWORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves",
    "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves",
}

# Common abbreviations to prevent false sentence splitting
ABBREVIATIONS = (
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "vs", "etc", "inc", "ltd", "corp",
    "u.s", "u.k", "u.n", "e.g", "i.e", "a.m", "p.m", "jan", "feb", "mar", "apr",
    "aug", "sept", "oct", "nov", "dec", "no", "st", "ave", "blvd", "dept", "gen",
    "gov", "sen", "rep", "sgt", "capt", "col",
)


def split_into_sentences(text: str) -> List[str]:
    """
    Splits text into sentences while respecting common abbreviations,
    numbers with decimal points, and multi-punctuation sequences.
    """
    if not text or not text.strip():
        return []

    cleaned = text.strip()

    # Protect abbreviations by replacing period with placeholder while preserving casing
    for abbr in ABBREVIATIONS:
        pattern = re.compile(rf"\b({re.escape(abbr)})\.", re.IGNORECASE)
        cleaned = pattern.sub(lambda m: m.group(1).replace(".", "__DOT__") + "__DOT__", cleaned)

    # Protect decimal numbers (e.g. 3.14)
    cleaned = re.sub(r"(\d+)\.(\d+)", r"\1__DOT__\2", cleaned)

    # Protect single-letter chained acronyms (e.g. U.S.A.)
    cleaned = re.sub(r"([A-Za-z])\.([A-Za-z])\.", r"\1__DOT__\2__DOT__", cleaned)

    # Split on sentence terminals followed by whitespace or end of string
    raw_sentences = re.split(r"(?<=[.!?])\s+", cleaned)

    sentences = []
    for s in raw_sentences:
        # Restore protected dots
        restored = s.replace("__DOT__", ".")
        restored = restored.strip()
        if restored:
            sentences.append(restored)

    return sentences if sentences else [text.strip()]


def tokenize_words(
    text: str,
    lowercase: bool = True,
    remove_punct: bool = True,
    min_word_length: int = 1,
) -> List[str]:
    """
    Tokenizes text into a list of word tokens.
    """
    if not text:
        return []

    if lowercase:
        text = text.lower()

    if remove_punct:
        # Extract word tokens matching alphanumeric sequences (including intra-word hyphens/apostrophes)
        tokens = re.findall(r"\b[a-zA-Z0-9]+(?:['-_][a-zA-Z0-9]+)*\b", text)
    else:
        tokens = text.split()

    if min_word_length > 1:
        tokens = [t for t in tokens if len(t) >= min_word_length]

    return tokens


def remove_stopwords(
    tokens: List[str],
    custom_stopwords: Optional[Set[str]] = None,
) -> List[str]:
    """Filter out stopwords from a list of tokens."""
    stop_set = custom_stopwords if custom_stopwords is not None else ENGLISH_STOPWORDS
    return [token for token in tokens if token.lower() not in stop_set]


def extract_ngrams(tokens: List[str], n: int = 2) -> List[str]:
    """Extract contiguous n-grams (e.g. bigrams, trigrams) from tokens."""
    if len(tokens) < n or n < 1:
        return []
    return [" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]
