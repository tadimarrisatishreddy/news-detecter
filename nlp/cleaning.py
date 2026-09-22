import html
import re
import unicodedata
from typing import List, Optional

# Comprehensive English contractions mapping
CONTRACTIONS_DICT = {
    "ain't": "is not",
    "aren't": "are not",
    "can't": "cannot",
    "can't've": "cannot have",
    "'cause": "because",
    "could've": "could have",
    "couldn't": "could not",
    "couldn't've": "could not have",
    "didn't": "did not",
    "doesn't": "does not",
    "don't": "do not",
    "hadn't": "had not",
    "hadn't've": "had not have",
    "hasn't": "has not",
    "haven't": "have not",
    "he'd": "he would",
    "he'd've": "he would have",
    "he'll": "he will",
    "he'll've": "he will have",
    "he's": "he is",
    "how'd": "how did",
    "how'd'y": "how do you",
    "how'll": "how will",
    "how's": "how is",
    "i'd": "i would",
    "i'd've": "i would have",
    "i'll": "i will",
    "i'll've": "i will have",
    "i'm": "i am",
    "i've": "i have",
    "isn't": "is not",
    "it'd": "it would",
    "it'd've": "it would have",
    "it'll": "it will",
    "it'll've": "it will have",
    "it's": "it is",
    "let's": "let us",
    "ma'am": "madam",
    "mayn't": "may not",
    "might've": "might have",
    "mightn't": "might not",
    "mightn't've": "might not have",
    "must've": "must have",
    "mustn't": "must not",
    "mustn't've": "must not have",
    "needn't": "need not",
    "needn't've": "need not have",
    "o'clock": "of the clock",
    "oughtn't": "ought not",
    "oughtn't've": "ought not have",
    "shan't": "shall not",
    "sha'n't": "shall not",
    "shan't've": "shall not have",
    "she'd": "she would",
    "she'd've": "she would have",
    "she'll": "she will",
    "she'll've": "she will have",
    "she's": "she is",
    "should've": "should have",
    "shouldn't": "should not",
    "shouldn't've": "should not have",
    "so've": "so have",
    "so's": "so is",
    "that'd": "that would",
    "that'd've": "that would have",
    "that's": "that is",
    "there'd": "there would",
    "there'd've": "there would have",
    "there's": "there is",
    "they'd": "they would",
    "they'd've": "they would have",
    "they'll": "they will",
    "they'll've": "they will have",
    "they're": "they are",
    "they've": "they have",
    "to've": "to have",
    "wasn't": "was not",
    "we'd": "we would",
    "we'd've": "we would have",
    "we'll": "we will",
    "we'll've": "we will have",
    "we're": "we are",
    "we've": "we have",
    "weren't": "were not",
    "what'll": "what will",
    "what'll've": "what will have",
    "what're": "what are",
    "what's": "what is",
    "what've": "what have",
    "when's": "when is",
    "when've": "when have",
    "where'd": "where did",
    "where's": "where is",
    "where've": "where have",
    "who'll": "who will",
    "who'll've": "who will have",
    "who's": "who is",
    "who've": "who have",
    "why's": "why is",
    "why've": "why have",
    "will've": "will have",
    "won't": "will not",
    "won't've": "will not have",
    "would've": "would have",
    "wouldn't": "would not",
    "wouldn't've": "would not have",
    "y'all": "you all",
    "y'all'd": "you all would",
    "y'all'd've": "you all would have",
    "y'all're": "you all are",
    "y'all've": "you all have",
    "you'd": "you would",
    "you'd've": "you would have",
    "you'll": "you will",
    "you'll've": "you will have",
    "you're": "you are",
    "you've": "you have",
}

# Compiled regex for contractions
CONTRACTIONS_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in CONTRACTIONS_DICT.keys()) + r")\b",
    re.IGNORECASE,
)

# URL Pattern
URL_PATTERN = re.compile(
    r"https?://(?:www\.)?[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b[-a-zA-Z0-9()@:%_+.~#?&/=]*|"
    r"www\.[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b[-a-zA-Z0-9()@:%_+.~#?&/=]*",
    re.IGNORECASE,
)

# HTML Tag Pattern
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    """Remove HTML tags and decode HTML entities."""
    if not text:
        return ""
    # Unescape HTML entities (&amp;, &quot;, &#39;, etc.)
    unescaped = html.unescape(text)
    # Strip HTML tags
    cleaned = HTML_TAG_PATTERN.sub(" ", unescaped)
    return cleaned


def normalize_unicode(text: str) -> str:
    """
    Normalize Unicode characters:
    - Replaces smart quotes, em-dashes, and special symbols with ASCII equivalents
    - Applies NFKD normalization
    """
    if not text:
        return ""
    # Replace common typographic characters
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2014": " - ",
        "\u2013": " - ",
        "\u2026": "...",
        "\u00a0": " ",
        "\u200b": "",
    }
    for orig, repl in replacements.items():
        text = text.replace(orig, repl)

    # Normalize unicode characters
    normalized = unicodedata.normalize("NFKD", text)
    return normalized


def expand_contractions(text: str) -> str:
    """Expand English contractions (e.g. 'don't' -> 'do not')."""
    if not text:
        return ""

    def replace(match):
        match_str = match.group(0).lower()
        expanded = CONTRACTIONS_DICT.get(match_str, match.group(0))
        # Match case of original first letter
        if match.group(0)[0].isupper() and expanded:
            return expanded[0].upper() + expanded[1:]
        return expanded

    return CONTRACTIONS_PATTERN.sub(replace, text)


def extract_urls(text: str) -> List[str]:
    """Extract all URLs found in the text."""
    if not text:
        return []
    return URL_PATTERN.findall(text)


def remove_urls(text: str, replace_with: str = "") -> str:
    """Remove or replace URLs from text."""
    if not text:
        return ""
    return URL_PATTERN.sub(replace_with, text)


def clean_special_characters(text: str, preserve_sentence_punct: bool = False) -> str:
    """
    Remove special characters and non-alphanumeric noise.
    If preserve_sentence_punct is True, keeps . ! ? , ' -
    """
    if not text:
        return ""
    if preserve_sentence_punct:
        pattern = r"[^a-zA-Z0-9\s.,!?'\-_]"
    else:
        pattern = r"[^a-zA-Z0-9\s]"
    return re.sub(pattern, " ", text)


def normalize_whitespace(text: str) -> str:
    """Collapse multiple spaces, tabs, and newlines into single spaces."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def clean_text(
    text: str,
    lowercase: bool = True,
    strip_html_flag: bool = True,
    expand_contractions_flag: bool = True,
    remove_urls_flag: bool = True,
    preserve_sentence_punct: bool = False,
) -> str:
    """
    Full text cleaning pipeline for NLP.
    """
    if not text:
        return ""

    # 1. Strip HTML and decode entities
    if strip_html_flag:
        text = strip_html(text)

    # 2. Normalize Unicode
    text = normalize_unicode(text)

    # 3. Expand contractions
    if expand_contractions_flag:
        text = expand_contractions(text)

    # 4. Remove URLs
    if remove_urls_flag:
        text = remove_urls(text, replace_with=" ")

    # 5. Clean special characters
    text = clean_special_characters(text, preserve_sentence_punct=preserve_sentence_punct)

    # 6. Lowercase
    if lowercase:
        text = text.lower()

    # 7. Normalize whitespace
    text = normalize_whitespace(text)

    return text

