from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from auth.schemas import (
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)

# Aliases for backward compatibility
UserRegister = UserRegisterRequest
UserLogin = UserLoginRequest


# -----------------------------------------------------------------------------
# NLP & NEWS PREPROCESSING SCHEMAS
# -----------------------------------------------------------------------------

class NewsInput(BaseModel):
    """Basic news input schema for analysis submission."""
    news_text: str = Field(
        ...,
        min_length=20,
        max_length=50000,
        description="News article or claim text to analyze",
    )


class NewsPreprocessRequest(BaseModel):
    """Custom request options for NLP text preprocessing."""
    text: str = Field(
        ...,
        min_length=1,
        max_length=50000,
        description="Raw text to clean and preprocess",
    )
    lowercase: bool = Field(default=True, description="Convert text to lowercase")
    strip_html: bool = Field(default=True, description="Remove HTML tags & decode entities")
    expand_contractions: bool = Field(default=True, description="Expand English contractions")
    remove_urls: bool = Field(default=True, description="Remove URL links")
    remove_stopwords: bool = Field(default=False, description="Filter out common stopwords")
    preserve_sentence_punct: bool = Field(default=False, description="Keep sentence punctuation marks")


class NewsPreprocessResponse(BaseModel):
    """Cleaned text and token representation."""
    cleaned_text: str
    word_count: int
    tokens: List[str]
    sentences: List[str]


class TextStatistics(BaseModel):
    """Linguistic and structural text statistics."""
    character_count: int
    character_count_no_spaces: int
    word_count: int
    unique_word_count: int
    sentence_count: int
    lexical_diversity: float
    avg_word_length: float
    avg_sentence_length: float


class ReadabilityMetrics(BaseModel):
    """Readability scores and reading grade levels."""
    flesch_reading_ease: float
    grade_level: float
    reading_level: str


class SensationalismMetrics(BaseModel):
    """Sensationalism and clickbait heuristic metrics."""
    sensationalism_score: float
    is_sensational: bool
    caps_ratio: float
    exclamation_count: int
    question_cluster_count: int
    trigger_words_found: List[str]


class KeywordItem(BaseModel):
    keyword: str
    count: int


class NLPAnalysisResponse(BaseModel):
    """Complete NLP analysis output."""
    raw_text: str
    cleaned_text: str
    sentences: List[str]
    tokens: List[str]
    tokens_no_stopwords: List[str]
    statistics: TextStatistics
    readability: ReadabilityMetrics
    sensationalism: SensationalismMetrics
    top_keywords: List[str]
    top_keywords_with_freq: List[KeywordItem]


# -----------------------------------------------------------------------------
# NEWS SUBMISSION PERSISTENCE SCHEMAS
# -----------------------------------------------------------------------------

class NewsSubmissionCreate(BaseModel):
    """Request body for authenticated news submission."""
    title: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional headline/title of the news article",
    )
    news_text: str = Field(
        ...,
        min_length=20,
        max_length=50000,
        description="News article or claim content",
    )
    source_url: Optional[str] = Field(
        default=None,
        max_length=2048,
        description="Optional source URL",
    )


class NewsSubmissionResponse(BaseModel):
    """Response body representing a stored news submission."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: Optional[str]
    raw_text: str
    cleaned_text: str
    source_url: Optional[str]
    word_count: int
    char_count: int
    sentence_count: int
    reading_ease_score: Optional[float]
    sensationalism_score: Optional[float]
    lexical_diversity: Optional[float]
    top_keywords: Optional[str]
    created_at: datetime


# -----------------------------------------------------------------------------
# BATCH NLP PROCESSING SCHEMAS
# -----------------------------------------------------------------------------

class BatchNewsItem(BaseModel):
    id: Optional[str] = None
    text: str = Field(..., min_length=1, max_length=50000)


class BatchNewsAnalysisRequest(BaseModel):
    articles: List[BatchNewsItem] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of news articles to process in batch",
    )


class BatchNewsAnalysisItemResult(BaseModel):
    id: Optional[str] = None
    word_count: int
    cleaned_text: str
    readability_score: float
    sensationalism_score: float
    is_sensational: bool
    top_keywords: List[str]


class BatchNewsAnalysisResponse(BaseModel):
    total_processed: int
    results: List[BatchNewsAnalysisItemResult]


# -----------------------------------------------------------------------------
# ANALYSIS SCHEMAS (EXISTING)
# -----------------------------------------------------------------------------

class AnalysisCreate(BaseModel):
    """Request body for POST /analyses."""

    input_text: str = Field(
        ...,
        min_length=20,
        max_length=50000,
        description="News claim or article text to analyze",
    )

    source_url: Optional[str] = Field(
        default=None,
        max_length=2048,
        description="Optional URL of the news source",
    )


class AnalysisResponse(BaseModel):
    """Response body for a single analysis."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    input_text: str
    source_url: Optional[str]
    status: str
    verdict: Optional[str]
    confidence: Optional[float]
    explanation: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime