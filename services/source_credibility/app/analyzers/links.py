"""
URL / domain analysis.

Checks for:
  - URL shorteners  (bit.ly, t.co, tinyurl.com, …)
  - Suspicious TLDs (.xyz, .click, .top, .buzz, .gq, …)
  - Domains that look like misspelled versions of major brands
"""

from __future__ import annotations

import logging
import re
from typing import NamedTuple
from urllib.parse import urlparse

from cachetools import TTLCache

from app.config import DOMAIN_CACHE_MAX_SIZE, DOMAIN_CACHE_TTL

logger = logging.getLogger(__name__)

# ── Caches & constants ──────────────────────────────────────────────────────

_domain_cache: TTLCache[str, bool] = TTLCache(
    maxsize=DOMAIN_CACHE_MAX_SIZE, ttl=DOMAIN_CACHE_TTL
)

URL_SHORTENERS = frozenset({
    "bit.ly", "t.co", "tinyurl.com", "goo.gl", "ow.ly", "is.gd",
    "buff.ly", "shorturl.at", "rb.gy", "cutt.ly", "tiny.cc",
    "lnkd.in", "soo.gd", "s.id",
})

SUSPICIOUS_TLDS = frozenset({
    ".xyz", ".click", ".top", ".buzz", ".gq", ".ml", ".tk", ".cf",
    ".ga", ".work", ".fit", ".surf", ".icu", ".cam", ".quest",
    ".rest", ".monster",
})

# Major trusted domains — if the link points here, skip suspicion checks
TRUSTED_DOMAINS = frozenset({
    "twitter.com", "x.com", "facebook.com", "instagram.com",
    "linkedin.com", "youtube.com", "reddit.com", "wikipedia.org",
    "bbc.com", "bbc.co.uk", "cnn.com", "nytimes.com", "reuters.com",
    "apnews.com", "theguardian.com", "washingtonpost.com",
    "aljazeera.com", "aljazeera.net", "france24.com",
    "gov.uk", "whitehouse.gov", "who.int", "un.org",
    "github.com", "arxiv.org", "nature.com", "science.org",
})

# Simple fuzzy-match patterns for common brand typosquats
_BRAND_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"cnn[^.]", re.I),
    re.compile(r"faceb[o0]{2}k", re.I),
    re.compile(r"g[o0]{2}gle", re.I),
    re.compile(r"twitt[e3]r", re.I),
    re.compile(r"yout[u0]be", re.I),
    re.compile(r"r[e3]ut[e3]rs", re.I),
    re.compile(r"bbc[^.]", re.I),
]


class LinksResult(NamedTuple):
    flags: list[str]
    suspicious_domains: list[str]
    penalty: float  # number of suspicious domains found


def _extract_domain(url: str) -> str | None:
    """Best-effort domain extraction."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        return urlparse(url).netloc.lower().strip(".")
    except Exception:
        return None


def _is_suspicious(domain: str) -> bool:
    """Evaluate a single domain for suspicious signals (cached)."""
    if domain in _domain_cache:
        return _domain_cache[domain]

    suspicious = False

    # Trusted → not suspicious
    if domain in TRUSTED_DOMAINS or any(
        domain.endswith("." + td) for td in TRUSTED_DOMAINS
    ):
        _domain_cache[domain] = False
        return False

    # URL shortener
    if domain in URL_SHORTENERS:
        suspicious = True

    # Suspicious TLD
    if not suspicious:
        for tld in SUSPICIOUS_TLDS:
            if domain.endswith(tld):
                suspicious = True
                break

    # Typosquat detection
    if not suspicious:
        for pat in _BRAND_PATTERNS:
            if pat.search(domain):
                # Ensure it's not the actual brand domain
                if domain not in TRUSTED_DOMAINS:
                    suspicious = True
                    break

    _domain_cache[domain] = suspicious
    return suspicious


def analyze_links(links: list[str]) -> LinksResult:
    """Analyse all URLs and return aggregated flags + penalty count."""

    flags: list[str] = []
    suspicious_domains: list[str] = []

    seen: set[str] = set()

    for url in links:
        domain = _extract_domain(url)
        if domain is None or domain in seen:
            continue
        seen.add(domain)

        if _is_suspicious(domain):
            suspicious_domains.append(domain)
            logger.info("Flag: suspicious_domain — %s", domain)

    if suspicious_domains:
        flags.append("suspicious_domain")

    return LinksResult(
        flags=flags,
        suspicious_domains=suspicious_domains,
        penalty=len(suspicious_domains),
    )
