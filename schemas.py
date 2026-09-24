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


# -----------------------------------------------------------------------------
# AI DETECTION SCHEMAS (MODULE 3)
# -----------------------------------------------------------------------------

class DetectionRequest(BaseModel):
    """Request body for POST /detect."""
    claim: str = Field(
        ...,
        min_length=5,
        max_length=50000,
        description="News claim or article statement to detect veracity",
    )


class DetectionResponse(BaseModel):
    """Response model for AI fake news detection."""
    message: str = "News analyzed successfully"
    detection_id: int
    claim: str
    verdict: str
    confidence: float
    explanation: str
    key_signals: Optional[List[str]] = Field(default_factory=list)
    manipulation_tactics: Optional[List[str]] = Field(default_factory=list)
    created_at: datetime


class DetectionResponseItem(BaseModel):
    claim: str
    verdict: str
    confidence: float
    explanation: str
    key_signals: List[str] = Field(default_factory=list)


class BatchDetectionRequest(BaseModel):
    claims: List[str] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of claims to analyze with Gemma AI in batch",
    )


class BatchDetectionResponse(BaseModel):
    total_processed: int
    results: List[DetectionResponseItem]


# -----------------------------------------------------------------------------
# FACT CHECKING SCHEMAS (MODULE 4)
# -----------------------------------------------------------------------------

class EvidenceSourceSchema(BaseModel):
    """Schema representing an individual retrieved evidence citation."""
    source_name: str
    source_url: str
    domain: Optional[str] = None
    tier: Optional[str] = None
    authority_weight: float = 0.5
    stance: str = "NOT_ENOUGH_INFO"
    title: Optional[str] = None
    snippet: Optional[str] = None
    published_date: Optional[str] = None


class FactCheckRequest(BaseModel):
    """Request payload for verifying a claim against trusted sources."""
    claim: str = Field(
        ...,
        min_length=5,
        max_length=50000,
        description="News claim, headline, or assertion to fact-check",
    )
    check_government_only: bool = Field(
        default=False,
        description="If True, restricts search strictly to official government portals and gazettes",
    )
    max_sources: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of authoritative citations to retrieve",
    )


class FactCheckResponse(BaseModel):
    """Response payload with fact-checking verdict and evidence breakdown."""
    id: Optional[int] = None
    claim: str
    status: str  # VERIFIED, REFUTED, DISPUTED, UNPROVEN
    verdict: str  # TRUE, FALSE, MISLEADING, UNVERIFIED
    trust_score: float = Field(ge=0.0, le=100.0)
    summary: str
    evidence_count: int
    evidence_sources: List[EvidenceSourceSchema]
    verified_at: str


class TrustedSourceItem(BaseModel):
    domain: str
    name: str
    tier: str
    authority_weight: float


class WhitelistResponse(BaseModel):
    total_sources: int
    trusted_domains: List[TrustedSourceItem]