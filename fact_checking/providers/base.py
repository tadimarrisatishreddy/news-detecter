from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    """Represents an individual retrieved piece of evidence or citation."""
    source_name: str
    source_url: str
    domain: str
    tier: str
    authority_weight: float = Field(ge=0.0, le=1.0)
    title: str = ""
    snippet: str = ""
    stance: str = "NOT_ENOUGH_INFO"  # SUPPORTS, REFUTES, NOT_ENOUGH_INFO
    published_date: Optional[str] = None
    similarity_score: float = 0.0


class BaseEvidenceProvider(ABC):
    """Abstract interface for fact-checking evidence retrieval providers."""

    @abstractmethod
    def search_evidence(
        self,
        claim: str,
        max_results: int = 5,
        government_only: bool = False,
    ) -> List[EvidenceItem]:
        """Search and retrieve evidence items for a given claim."""
        pass
