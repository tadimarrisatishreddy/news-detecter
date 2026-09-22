import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from dependencies import get_current_active_user, get_db
from models import NewsSubmission, User
from nlp import (
    clean_text,
    extract_nlp_features,
    remove_stopwords,
    split_into_sentences,
    tokenize_words,
)
from schemas import (
    BatchNewsAnalysisItemResult,
    BatchNewsAnalysisRequest,
    BatchNewsAnalysisResponse,
    NewsInput,
    NewsPreprocessRequest,
    NewsPreprocessResponse,
    NewsSubmissionCreate,
    NewsSubmissionResponse,
    NLPAnalysisResponse,
)

router = APIRouter(
    prefix="/news",
    tags=["News Input & NLP Processing"],
)


# -----------------------------------------------------------------------------
# 1. Text Preprocessing Endpoint
# -----------------------------------------------------------------------------
@router.post(
    "/preprocess",
    response_model=NewsPreprocessResponse,
    summary="Clean and normalize raw news text",
)
def preprocess_news_text(
    payload: NewsPreprocessRequest,
):
    """
    Cleans raw text with configurable pipeline:
    - HTML entity decoding & tag stripping
    - Contraction expansion (e.g. 'don\'t' -> 'do not')
    - URL extraction & removal
    - Unicode character normalization
    - Tokenization and sentence segmentation
    """
    cleaned = clean_text(
        text=payload.text,
        lowercase=payload.lowercase,
        strip_html_flag=payload.strip_html,
        expand_contractions_flag=payload.expand_contractions,
        remove_urls_flag=payload.remove_urls,
        preserve_sentence_punct=payload.preserve_sentence_punct,
    )

    tokens = tokenize_words(cleaned, lowercase=payload.lowercase, remove_punct=True)
    if payload.remove_stopwords:
        tokens = remove_stopwords(tokens)

    sentences = split_into_sentences(payload.text)

    return NewsPreprocessResponse(
        cleaned_text=cleaned,
        word_count=len(tokens),
        tokens=tokens,
        sentences=sentences,
    )


# -----------------------------------------------------------------------------
# 2. Comprehensive NLP Feature Analysis Endpoint
# -----------------------------------------------------------------------------
@router.post(
    "/analyze",
    response_model=NLPAnalysisResponse,
    summary="Extract NLP statistics, readability scores, and sensationalism metrics",
)
def analyze_news_text(
    payload: NewsInput,
):
    """
    Performs full linguistic and structural analysis on news text:
    - Word, sentence, and character counts
    - Lexical diversity (Type-Token Ratio)
    - Flesch Reading Ease & Grade Level
    - Sensationalism & Clickbait heuristic scoring (caps ratio, trigger words, punctuation)
    - Top informative keyword extraction
    """
    features = extract_nlp_features(payload.news_text)
    return NLPAnalysisResponse(**features)


# -----------------------------------------------------------------------------
# 3. Authenticated News Submission & Storage Endpoint
# -----------------------------------------------------------------------------
@router.post(
    "/submit",
    response_model=NewsSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a news article for NLP processing and persistent storage",
)
def submit_news(
    submission: NewsSubmissionCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Ingests and saves a news submission for the authenticated user:
    - Automatically executes NLP preprocessing
    - Calculates and stores readability and sensationalism scores
    - Stores raw and cleaned text in database
    """
    features = extract_nlp_features(submission.news_text)

    record = NewsSubmission(
        user_id=current_user.id,
        title=submission.title,
        raw_text=submission.news_text,
        cleaned_text=features["cleaned_text"],
        source_url=submission.source_url,
        word_count=features["statistics"]["word_count"],
        char_count=features["statistics"]["character_count"],
        sentence_count=features["statistics"]["sentence_count"],
        reading_ease_score=features["readability"]["flesch_reading_ease"],
        sensationalism_score=features["sensationalism"]["sensationalism_score"],
        lexical_diversity=features["statistics"]["lexical_diversity"],
        top_keywords=json.dumps(features["top_keywords"]),
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return record


# -----------------------------------------------------------------------------
# 4. List User Submissions Endpoint
# -----------------------------------------------------------------------------
@router.get(
    "/submissions",
    response_model=List[NewsSubmissionResponse],
    summary="List processed news submissions for the authenticated user",
)
def list_user_submissions(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves the authenticated user's news submissions, newest first.
    """
    submissions = (
        db.query(NewsSubmission)
        .filter(NewsSubmission.user_id == current_user.id)
        .order_by(NewsSubmission.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return submissions


# -----------------------------------------------------------------------------
# 5. Get Single Submission by ID Endpoint
# -----------------------------------------------------------------------------
@router.get(
    "/submissions/{submission_id}",
    response_model=NewsSubmissionResponse,
    summary="Retrieve a specific news submission by ID",
)
def get_submission_by_id(
    submission_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves a single news submission. Regular users can only access their own submissions.
    """
    submission = db.query(NewsSubmission).filter(NewsSubmission.id == submission_id).first()

    if submission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="News submission not found",
        )

    if current_user.role != "admin" and submission.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="News submission not found",
        )

    return submission


# -----------------------------------------------------------------------------
# 6. Batch News Analysis Endpoint
# -----------------------------------------------------------------------------
@router.post(
    "/batch-analyze",
    response_model=BatchNewsAnalysisResponse,
    summary="Process and analyze multiple news articles in a single batch request",
)
def batch_analyze_news(
    payload: BatchNewsAnalysisRequest,
):
    """
    Processes up to 50 news articles in batch:
    - Runs text cleaning and feature extraction for each article
    - Returns summary statistics and sensationalism assessment
    """
    results: List[BatchNewsAnalysisItemResult] = []

    for item in payload.articles:
        features = extract_nlp_features(item.text)
        results.append(
            BatchNewsAnalysisItemResult(
                id=item.id,
                word_count=features["statistics"]["word_count"],
                cleaned_text=features["cleaned_text"],
                readability_score=features["readability"]["flesch_reading_ease"],
                sensationalism_score=features["sensationalism"]["sensationalism_score"],
                is_sensational=features["sensationalism"]["is_sensational"],
                top_keywords=features["top_keywords"],
            )
        )

    return BatchNewsAnalysisResponse(
        total_processed=len(results),
        results=results,
    )