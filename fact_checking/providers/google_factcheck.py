import logging
import os
import httpx
from typing import List, Optional
from fact_checking.providers.base import BaseEvidenceProvider, EvidenceItem
from fact_checking.providers.mock_provider import MockEvidenceProvider
from fact_checking.trusted_sources import classify_domain

logger = logging.getLogger("fact_checking.google_factcheck")


class GoogleFactCheckProvider(BaseEvidenceProvider):
    """
    Interfaces with Google Fact Check Tools API (ClaimReview data).
    API Endpoint: https://factchecktools.googleapis.com/v1alpha1/claims:search
    Falls back gracefully to mock provider if API key is missing or request fails.
    """

    def __init__(self, api_key: Optional[str] = None, timeout: float = 5.0):
        self.api_key = api_key or os.getenv("GOOGLE_FACT_CHECK_API_KEY", "")
        self.timeout = timeout
        self._fallback = MockEvidenceProvider()

    def search_evidence(
        self,
        claim: str,
        max_results: int = 5,
        government_only: bool = False,
    ) -> List[EvidenceItem]:
        if not self.api_key:
            return self._fallback.search_evidence(claim, max_results=max_results, government_only=government_only)

        try:
            url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
            params = {
                "query": claim,
                "key": self.api_key,
                "pageSize": max_results,
            }
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    claims_list = data.get("claims", [])
                    results: List[EvidenceItem] = []

                    for c in claims_list:
                        claim_reviews = c.get("claimReview", [])
                        for r in claim_reviews:
                            publisher = r.get("publisher", {})
                            pub_name = publisher.get("name", "Fact Checker")
                            pub_site = publisher.get("site", "")
                            review_url = r.get("url", pub_site)
                            rating = r.get("textualRating", "").lower()
                            title = r.get("title", c.get("text", ""))

                            # Determine stance from rating
                            if any(w in rating for w in ["false", "fake", "incorrect", "hoax", "debunked", "pants on fire"]):
                                stance = "REFUTES"
                            elif any(w in rating for w in ["true", "correct", "accurate", "verified"]):
                                stance = "SUPPORTS"
                            else:
                                stance = "NOT_ENOUGH_INFO"

                            source_name, tier, weight = classify_domain(pub_site or review_url)

                            results.append(
                                EvidenceItem(
                                    source_name=pub_name or source_name,
                                    source_url=review_url,
                                    domain=pub_site,
                                    tier=tier,
                                    authority_weight=weight,
                                    title=title,
                                    snippet=f"Fact-check Rating: {r.get('textualRating', 'Unrated')}. Reviewed claim: {c.get('text', '')}",
                                    stance=stance,
                                    published_date=r.get("reviewDate"),
                                    similarity_score=0.90,
                                )
                            )
                    if results:
                        return results[:max_results]
        except Exception as e:
            logger.debug(f"Google Fact Check API query failed: {e}")

        return self._fallback.search_evidence(claim, max_results=max_results, government_only=government_only)
