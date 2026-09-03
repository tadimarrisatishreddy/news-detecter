import re


def clean_text(text: str) -> str:
    """
    Clean raw news text for NLP processing.
    """

    # Convert to lowercase
    text = text.lower()

    # Remove URLs
    text = re.sub(
        r"http\S+|www\S+|https\S+",
        "",
        text
    )

    # Remove special characters
    text = re.sub(
        r"[^a-zA-Z0-9\s]",
        " ",
        text
    )

    # Remove extra spaces
    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    return text


def get_word_count(text: str) -> int:
    """
    Count words in text.
    """

    return len(text.split())