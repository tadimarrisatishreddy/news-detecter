from typing import List, Optional
from fact_checking.providers.base import BaseEvidenceProvider, EvidenceItem
from fact_checking.trusted_sources import (
    classify_domain,
    TIER_GOVERNMENT,
    TIER_FACT_CHECKER,
    TIER_NEWS_WIRE,
)


class MockEvidenceProvider(BaseEvidenceProvider):
    """
    Deterministic evidence provider for automated tests and offline environments.
    """

    def search_evidence(
        self,
        claim: str,
        max_results: int = 5,
        government_only: bool = False,
    ) -> List[EvidenceItem]:
        claim_lower = claim.lower()
        results: List[EvidenceItem] = []

        # 1. Fake Government allowance / laptop / fund scheme claims
        if any(w in claim_lower for w in ["allowance", "50,000", "50000", "free laptop", "pm-kusum", "replace water"]):
            source_name, tier, weight = classify_domain("pib.gov.in")
            results.append(
                EvidenceItem(
                    source_name="Press Information Bureau (PIB Fact Check)",
                    source_url="https://pib.gov.in/FactCheck/Fake-Scheme-Clarification.aspx",
                    domain="pib.gov.in",
                    tier=tier,
                    authority_weight=weight,
                    title="PIB Fact Check: Clarification on Viral Financial Assistance Message",
                    snippet="A viral message claims the government has approved a direct monetary allowance or free distribution scheme. PIB Fact Check confirms this message is completely FAKE and fraudulent. No such scheme has been approved.",
                    stance="REFUTES",
                    published_date="2026-08-15",
                    similarity_score=0.92,
                )
            )
            if not government_only:
                fc_name, fc_tier, fc_weight = classify_domain("snopes.com")
                results.append(
                    EvidenceItem(
                        source_name="Snopes Fact Check",
                        source_url="https://snopes.com/fact-check/government-allowance-scam",
                        domain="snopes.com",
                        tier=fc_tier,
                        authority_weight=fc_weight,
                        title="Fact Check: Fake Government Fund Distribution Hoax",
                        snippet="Reports circulating on messaging platforms regarding an instant student allowance or chemical water replacement are fabricated phishing hoaxes.",
                        stance="REFUTES",
                        published_date="2026-08-16",
                        similarity_score=0.88,
                    )
                )

        # 2. Moon 29th state claim
        elif "moon" in claim_lower and ("29th" in claim_lower or "state" in claim_lower):
            source_name, tier, weight = classify_domain("pib.gov.in")
            results.append(
                EvidenceItem(
                    source_name="Press Information Bureau (PIB)",
                    source_url="https://pib.gov.in/PressReleasePage.aspx?PRID=189000",
                    domain="pib.gov.in",
                    tier=tier,
                    authority_weight=weight,
                    title="Official Statement on Sovereign Territory and Outer Space Treaties",
                    snippet="Under the 1967 United Nations Outer Space Treaty, celestial bodies including the Moon are not subject to national appropriation by claim of sovereignty.",
                    stance="REFUTES",
                    published_date="2026-01-10",
                    similarity_score=0.95,
                )
            )

        # 3. Central Bank / Interest rate / Economy
        elif any(w in claim_lower for w in ["central bank", "interest rate", "basis point", "inflation"]):
            source_name, tier, weight = classify_domain("rbi.org.in")
            results.append(
                EvidenceItem(
                    source_name="Reserve Bank of India / Central Banking Portal",
                    source_url="https://rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=54000",
                    domain="rbi.org.in",
                    tier=tier,
                    authority_weight=weight,
                    title="Monetary Policy Committee Statement: Policy Repo Rate Announcement",
                    snippet="The Monetary Policy Committee decided to adjust the benchmark policy rate following a comprehensive assessment of macroeconomic developments and inflation outlook.",
                    stance="SUPPORTS",
                    published_date="2026-08-10",
                    similarity_score=0.89,
                )
            )
            if not government_only:
                source_name, tier, weight = classify_domain("reuters.com")
                results.append(
                    EvidenceItem(
                        source_name="Reuters News Agency",
                        source_url="https://reuters.com/markets/central-bank-policy-rate-update",
                        domain="reuters.com",
                        tier=tier,
                        authority_weight=weight,
                        title="Central Bank Adjusts Benchmark Rates in Line with Economic Projections",
                        snippet="Policymakers confirmed a strategic rate adjustment to maintain price stability while supporting sustained economic growth.",
                        stance="SUPPORTS",
                        published_date="2026-08-10",
                        similarity_score=0.87,
                    )
                )

        # 4. Scientific / Climate / Health Research
        elif any(w in claim_lower for w in ["scientists", "fusion", "clinical trial", "satellite", "climate", "carbon"]):
            source_name, tier, weight = classify_domain("nature.com")
            results.append(
                EvidenceItem(
                    source_name="Nature Scientific Publishing",
                    source_url="https://nature.com/articles/s41586-026-05000-x",
                    domain="nature.com",
                    tier=tier,
                    authority_weight=weight,
                    title="Progress in Experimental Energy Generation and Collaborative Frameworks",
                    snippet="Peer-reviewed findings confirm verified experimental milestones achieved through multi-institutional research collaborations.",
                    stance="SUPPORTS",
                    published_date="2026-07-20",
                    similarity_score=0.86,
                )
            )

        # 5. Generic / Unverified claims
        else:
            source_name, tier, weight = classify_domain("unverified-blog.org")
            results.append(
                EvidenceItem(
                    source_name="General Web Index",
                    source_url="https://unverified-blog.org/article/unconfirmed-topic",
                    domain="unverified-blog.org",
                    tier=tier,
                    authority_weight=weight,
                    title="Discussion on Emerging Web Claims",
                    snippet="Public discussions regarding the subject matter show no official gazette or verified institutional corroboration at this time.",
                    stance="NOT_ENOUGH_INFO",
                    published_date="2026-09-01",
                    similarity_score=0.45,
                )
            )

        return results[:max_results]
