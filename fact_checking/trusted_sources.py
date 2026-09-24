import re
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

# Source Tiers and their authority multipliers
TIER_GOVERNMENT = "Tier 1: Government & Official Public Bodies"
TIER_FACT_CHECKER = "Tier 2: Verified Fact-Checking Registries"
TIER_NEWS_WIRE = "Tier 3: Global News Wires & Academic Institutions"
TIER_MAINSTREAM = "Tier 4: Standard Mainstream News Outlets"
TIER_UNVERIFIED = "Tier 5: Unverified / User-Generated Content"

AUTHORITY_WEIGHTS = {
    TIER_GOVERNMENT: 1.00,
    TIER_FACT_CHECKER: 0.95,
    TIER_NEWS_WIRE: 0.85,
    TIER_MAINSTREAM: 0.70,
    TIER_UNVERIFIED: 0.15,
}

# Whitelist of trusted authoritative domains and their designations
TRUSTED_DOMAINS: Dict[str, Dict[str, str]] = {
    # Government & Public Health (Tier 1)
    "pib.gov.in": {"name": "Press Information Bureau (PIB)", "tier": TIER_GOVERNMENT},
    "gov.in": {"name": "Government of India Official Portal", "tier": TIER_GOVERNMENT},
    "nic.in": {"name": "National Informatics Centre (NIC)", "tier": TIER_GOVERNMENT},
    "data.gov.in": {"name": "Open Government Data India", "tier": TIER_GOVERNMENT},
    "rbi.org.in": {"name": "Reserve Bank of India", "tier": TIER_GOVERNMENT},
    "isro.gov.in": {"name": "Indian Space Research Organisation", "tier": TIER_GOVERNMENT},
    "whitehouse.gov": {"name": "The White House Official", "tier": TIER_GOVERNMENT},
    "gov.uk": {"name": "UK Government Digital Service", "tier": TIER_GOVERNMENT},
    "who.int": {"name": "World Health Organization (WHO)", "tier": TIER_GOVERNMENT},
    "cdc.gov": {"name": "Centers for Disease Control and Prevention", "tier": TIER_GOVERNMENT},
    "nasa.gov": {"name": "National Aeronautics and Space Administration", "tier": TIER_GOVERNMENT},
    "un.org": {"name": "United Nations Official", "tier": TIER_GOVERNMENT},

    # Verified Fact-Check Registries (Tier 2 - IFCN Signatories)
    "snopes.com": {"name": "Snopes Fact Check", "tier": TIER_FACT_CHECKER},
    "politifact.com": {"name": "PolitiFact", "tier": TIER_FACT_CHECKER},
    "factcheck.org": {"name": "FactCheck.org", "tier": TIER_FACT_CHECKER},
    "boomlive.in": {"name": "BOOM FactCheck", "tier": TIER_FACT_CHECKER},
    "altnews.in": {"name": "Alt News", "tier": TIER_FACT_CHECKER},
    "fullfact.org": {"name": "Full Fact UK", "tier": TIER_FACT_CHECKER},
    "leadstories.com": {"name": "Lead Stories", "tier": TIER_FACT_CHECKER},

    # Global News Wires & Academic (Tier 3)
    "reuters.com": {"name": "Reuters News Agency", "tier": TIER_NEWS_WIRE},
    "apnews.com": {"name": "Associated Press (AP)", "tier": TIER_NEWS_WIRE},
    "afp.com": {"name": "Agence France-Presse (AFP)", "tier": TIER_NEWS_WIRE},
    "bbc.com": {"name": "BBC News", "tier": TIER_NEWS_WIRE},
    "bbc.co.uk": {"name": "BBC News UK", "tier": TIER_NEWS_WIRE},
    "nature.com": {"name": "Nature Scientific Journal", "tier": TIER_NEWS_WIRE},
    "science.org": {"name": "Science Journal (AAAS)", "tier": TIER_NEWS_WIRE},
    "thehindu.com": {"name": "The Hindu", "tier": TIER_MAINSTREAM},
    "indianexpress.com": {"name": "The Indian Express", "tier": TIER_MAINSTREAM},
}


def extract_domain(url: str) -> str:
    """Extracts normalized clean domain from a URL."""
    if not url:
        return ""
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Strip www. and port numbers
        domain = re.sub(r"^www\.", "", domain)
        domain = domain.split(":")[0]
        return domain
    except Exception:
        return ""


def classify_domain(domain_or_url: str) -> Tuple[str, str, float]:
    """
    Identifies the tier, source name, and authority multiplier of a domain or URL.
    Returns: (source_name, tier, authority_weight)
    """
    domain = extract_domain(domain_or_url)
    if not domain:
        return ("Unknown Source", TIER_UNVERIFIED, AUTHORITY_WEIGHTS[TIER_UNVERIFIED])

    # Direct whitelist lookup
    if domain in TRUSTED_DOMAINS:
        info = TRUSTED_DOMAINS[domain]
        tier = info["tier"]
        return (info["name"], tier, AUTHORITY_WEIGHTS[tier])

    # Suffix and pattern checks (e.g. all *.gov, *.gov.*, *.nic.in, *.mil, *.edu)
    if (
        domain.endswith(".gov")
        or ".gov." in domain
        or domain.endswith(".nic.in")
        or domain.endswith(".mil")
        or domain.endswith(".gov.in")
        or domain.endswith(".gov.uk")
    ):
        return (f"Official Government Portal ({domain})", TIER_GOVERNMENT, AUTHORITY_WEIGHTS[TIER_GOVERNMENT])

    if domain.endswith(".edu") or domain.endswith(".ac.in") or domain.endswith(".ac.uk"):
        return (f"Academic / Research Institute ({domain})", TIER_NEWS_WIRE, AUTHORITY_WEIGHTS[TIER_NEWS_WIRE])

    # Default to unverified/general
    return (domain, TIER_UNVERIFIED, AUTHORITY_WEIGHTS[TIER_UNVERIFIED])
