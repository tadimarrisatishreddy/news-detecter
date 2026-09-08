from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from auth.schemas import (
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)

# Aliases for backward compatibility
UserRegister = UserRegisterRequest
UserLogin = UserLoginRequest


# -------------------------
# NEWS INPUT
# -------------------------

class NewsInput(BaseModel):
    news_text: str = Field(
        ...,
        min_length=20,
        max_length=10000,
        description="News article or claim to analyze",
    )


# -------------------------
# ANALYSIS
# -------------------------

class AnalysisCreate(BaseModel):
    """Request body for POST /analyses."""

    input_text: str = Field(
        ...,
        min_length=20,
        max_length=10000,
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