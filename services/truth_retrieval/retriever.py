"""
Axis 3 – Source Credibility
Axis 4 – Truth Retrieval  (Wikipedia + DuckDuckGo)
"""
from __future__ import annotations

import logging
import re
import urllib.parse
from typing import Optional

import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("truth-service")


# ─────────────────────────────────────────────────────────────────────────────
# Axis 3 – Source Credibility
# ─────────────────────────────────────────────────────────────────────────────

BLACKLISTED_DOMAINS = {
    "fakenewssite.com", "propaganda.ru", "disinfo.net",
    "clickbait.io",     "conspiracyhub.org", "infowars.com",
    "naturalcure.biz",  "worldnewsdailyreport.com", "empirenews.net",
}

_BOT_PATTERNS = re.compile(
    r"(bot\d+|[a-z]{1,4}\d{5,}|[A-Z]{2,}\d{3,}|user_\d+|account_\d+|"
    r"temp_[a-z]+|rand[a-z]*\d+|[a-z]+_[a-z]+\d{4,})",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"https?://([^/\s]+)")


def evaluate_source(username: str = "", bio: str = "", links: list[str] = None) -> dict:
    links   = links or []
    signals = []
    score   = 1.0

    # Username heuristics
    if username:
        if _BOT_PATTERNS.search(username):
            signals.append("Username matches bot/throwaway pattern.")
            score -= 0.30
        if len(username) < 4:
            signals.append("Very short username.")
            score -= 0.10
        if re.search(r"\d{4,}", username):
            signals.append("Username contains long numeric suffix (bot indicator).")
            score -= 0.10

    # Bio
    if not bio or len(bio.strip()) < 10:
        signals.append("Missing or minimal bio.")
        score -= 0.15
    else:
        spam_bio = re.findall(
            r"\b(click here|free|win now|giveaway|dm for|promo|discount|"
            r"follow back|f4f|l4l|crypto|nft|onlyfans)\b",
            bio, re.IGNORECASE,
        )
        if spam_bio:
            signals.append(f"Bio contains spam/promotional keywords: {spam_bio[:2]}")
            score -= 0.30

    # Link domain blacklist
    for link in links:
        for domain in _URL_RE.findall(link):
            clean = domain.lower().replace("www.", "").split(":")[0]
            if clean in BLACKLISTED_DOMAINS:
                signals.append(f"Link to blacklisted domain: '{clean}'")
                score -= 0.50
                break

    score = max(0.0, min(1.0, round(score, 4)))
    risk  = "low" if score > 0.65 else "medium" if score > 0.35 else "high"

    return {
        "credibility_score": score,
        "risk_level":        risk,
        "signals":           signals if signals else ["No suspicious signals detected."],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Axis 4 – Truth Retrieval
# ─────────────────────────────────────────────────────────────────────────────

_NEWS_ENTITY_RE = re.compile(
    r"\b([A-Z][a-z]+ (?:[A-Z][a-z]+ )?(?:said|says|announced|confirmed|denied|"
    r"killed|won|lost|signed|arrested|launched|declared|revealed))\b"
)
_DATE_RE  = re.compile(r"\b(\d{1,2}\s+\w+\s+\d{4}|\w+\s+\d{1,2},?\s+\d{4})\b")
_CLAIM_RE = re.compile(r"\b(is|are|was|were|has|have|will|would|can|claims?|"
                       r"alleges?|says?|states?|reports?|confirms?)\b", re.IGNORECASE)

TRUSTED_DOMAINS = [
    "en.wikipedia.org",
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "bbc.co.uk",
    "aljazeera.com",
    "theguardian.com",
    "nytimes.com",
    "washingtonpost.com",
]


def is_news_content(text: str) -> bool:
    news_kw = re.findall(
        r"\b(president|minister|attack|war|government|election|court|police|"
        r"military|killed|arrested|announced|confirmed|denied|breaking|report|"
        r"exclusive|according|official|signed|launched|declared)\b",
        text, re.IGNORECASE,
    )
    has_entity = bool(_NEWS_ENTITY_RE.search(text))
    has_date   = bool(_DATE_RE.search(text))
    has_claim  = bool(_CLAIM_RE.search(text))
    return len(news_kw) >= 2 or has_entity or (has_date and has_claim)


_NOISE_WORDS = re.compile(
    r"\b(breaking|exclusive|just\s+in|developing|report|allegedly|secretly|"
    r"confirmed|announced|shocking|unbelievable|bombshell|share\s+before|"
    r"deleted|viral|trending|they\s+don'?t|you\s+won'?t|must[\s-]?see|"
    r"last\s+night|right\s+now|this\s+morning|this\s+week|this\s+year)\b",
    re.IGNORECASE,
)

_CAPS_PHRASE = re.compile(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b")


def extract_query(text: str) -> str:
    """
    Extract a focused search query from the claim text.

    Strategy:
    1. Strip anonymizer placeholders and noise/clickbait words.
    2. Try to find the subject–verb chunk (what event is being claimed).
    3. Fall back to the longest sentence if no named-entity phrase found.
    """
    # Strip anonymizer PII placeholders
    text = re.sub(r'\[(NAME|EMAIL|PHONE)_\d+\]\s*', '', text)

    # Try to grab named-entity phrases (capitalised noun sequences)
    named = _CAPS_PHRASE.findall(text)
    # Keep only phrases that are 2+ words (more specific)
    named = [p for p in named if len(p.split()) >= 2][:3]

    if named:
        # Build query: entity phrases + first verb clause
        sentences = re.split(r"[.!?]", text)
        # Find the sentence containing most of the named entities
        best = max(sentences, key=lambda s: sum(1 for n in named if n in s), default=text)
        # Remove noise words from it
        best = _NOISE_WORDS.sub('', best)
        best = re.sub(r'["\']', '', best)
        best = re.sub(r' {2,}', ' ', best).strip()
        if len(best) > 15:
            return best[:120]

    # Fallback: longest sentence minus noise
    sentences = re.split(r"[.!?]", text)
    main = max(sentences, key=len, default=text).strip()
    main = _NOISE_WORDS.sub('', main)
    main = re.sub(r'["\']', '', main)
    main = re.sub(r' {2,}', ' ', main).strip()
    return main[:120]


# ── Wikipedia ─────────────────────────────────────────────────────────────────

_HEADERS = {
    "User-Agent": "MENACRAFT-DigitalSieve/1.0 (fact-checking research tool; contact@menacraft.local) python-httpx",
    "Accept": "application/json",
}


async def search_wikipedia(query: str, limit: int = 3) -> list[dict]:
    """Search Wikipedia and return article stubs."""
    try:
        params = urllib.parse.urlencode({
            "action":   "query",
            "list":     "search",
            "srsearch": query[:100],
            "format":   "json",
            "utf8":     1,
            "srlimit":  limit,
        })
        url = f"https://en.wikipedia.org/w/api.php?{params}"
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True, headers=_HEADERS) as client:
            resp = await client.get(url)
            data = resp.json()

        results = []
        for item in data.get("query", {}).get("search", []):
            snippet = re.sub(r"<[^>]+>", "", item.get("snippet", "")).strip()
            title   = item["title"]
            results.append({
                "title":   title,
                "url":     f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}",
                "snippet": snippet,
            })
        return results
    except Exception as exc:
        logger.warning("Wikipedia search failed: %s", exc)
        return []


async def get_wikipedia_extract(title: str) -> str:
    """Fetch the introductory paragraph of a Wikipedia article."""
    try:
        params = urllib.parse.urlencode({
            "action":      "query",
            "prop":        "extracts",
            "exintro":     1,
            "exsentences": 4,
            "explaintext": 1,
            "format":      "json",
            "titles":      title,
        })
        url = f"https://en.wikipedia.org/w/api.php?{params}"
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True, headers=_HEADERS) as client:
            resp = await client.get(url)
            data = resp.json()

        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            extract = page.get("extract", "").strip()
            if extract and extract != "":
                return extract
    except Exception as exc:
        logger.warning("Wikipedia extract failed: %s", exc)
    return ""


# ── DuckDuckGo (fallback) ─────────────────────────────────────────────────────

async def fetch_ddg_results(query: str, max_results: int = 4) -> list[dict]:
    results = []
    try:
        encoded = urllib.parse.quote_plus(query)
        url     = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(url)
            data = resp.json()

        if data.get("AbstractURL"):
            results.append({
                "title": data.get("Heading", "Abstract"),
                "url":   data["AbstractURL"],
                "snippet": data.get("AbstractText", "")[:200],
            })

        for topic in data.get("RelatedTopics", [])[:max_results]:
            if isinstance(topic, dict) and "FirstURL" in topic:
                results.append({
                    "title":   topic.get("Text", "")[:100],
                    "url":     topic["FirstURL"],
                    "snippet": topic.get("Text", "")[:200],
                })
    except Exception as exc:
        logger.warning("DuckDuckGo search failed: %s", exc)

    return results[:max_results]


# ── Sentence similarity ────────────────────────────────────────────────────────

def _sentence_similarity(a: str, b: str) -> float:
    """Cosine similarity via sentence-transformers."""
    try:
        import numpy as np
        try:
            from models import get_similarity_model
            model = get_similarity_model()
        except ImportError:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("paraphrase-MiniLM-L3-v2", device="cpu")

        embs = model.encode([a[:256], b[:256]])
        cos  = float(
            np.dot(embs[0], embs[1]) /
            (np.linalg.norm(embs[0]) * np.linalg.norm(embs[1]) + 1e-9)
        )
        return cos
    except Exception:
        return 0.5


def _rank_sources(sources: list[dict]) -> list[dict]:
    """Put trusted domains first."""
    def rank(s: dict) -> int:
        url = s.get("url", "")
        for i, d in enumerate(TRUSTED_DOMAINS):
            if d in url:
                return i
        return len(TRUSTED_DOMAINS)
    return sorted(sources, key=rank)


# ── Main truth verification ────────────────────────────────────────────────────

async def verify_truth(text: str) -> dict:
    """
    Full Axis 4 pipeline:
      1. Detect if content makes a verifiable real-world claim
      2. Search Wikipedia (primary) + DuckDuckGo (secondary)
      3. Compare claim vs sources via sentence similarity
      4. Generate corrected version from Wikipedia extract
    """
    if not is_news_content(text):
        return {
            "is_news":          False,
            "is_misinformation": False,
            "confidence":        0.0,
            "verdict":           "REAL",
            "explanation":       "Content does not appear to be a verifiable news claim.",
            "corrected_version": "",
            "sources":           [],
        }

    query = extract_query(text)
    logger.info("truth query: %s", query[:80])

    # ── Fetch sources ──────────────────────────────────────────────────────────
    wiki_results, ddg_results = [], []
    try:
        wiki_results = await search_wikipedia(query, limit=3)
    except Exception:
        pass
    try:
        ddg_results  = await fetch_ddg_results(query, max_results=3)
    except Exception:
        pass

    # Merge: Wikipedia preferred, deduplicate by URL
    seen    = set()
    sources = []
    for s in wiki_results + ddg_results:
        if s["url"] not in seen:
            seen.add(s["url"])
            sources.append(s)
    sources = _rank_sources(sources)[:5]

    if not sources:
        return {
            "is_news":          True,
            "is_misinformation": False,
            "confidence":        0.25,
            "verdict":           "UNVERIFIED",
            "explanation":       "Could not retrieve sources to verify this claim. Treat with caution.",
            "corrected_version": "",
            "sources":           [],
        }

    # ── Compare claim against sources ─────────────────────────────────────────
    # Prefer Wikipedia extract (richer than snippet/title)
    wiki_extract = ""
    if wiki_results:
        wiki_extract = await get_wikipedia_extract(wiki_results[0]["title"])

    # Build comparison corpus: extract > snippets > titles
    if wiki_extract:
        corpus = wiki_extract
    else:
        corpus = " ".join(
            s.get("snippet") or s.get("title", "") for s in sources[:3]
        )

    similarity = _sentence_similarity(text, corpus)
    logger.info("truth similarity=%.3f sources=%d", similarity, len(sources))

    # ── Verdict thresholds ────────────────────────────────────────────────────
    # similarity: 1.0 = identical, 0.0 = unrelated
    # Below 0.20 → likely contradicts sources (FAKE)
    # 0.20-0.32  → diverges meaningfully (SUSPICIOUS)
    # Above 0.32 → broadly consistent (REAL)

    if similarity < 0.20:
        is_misinfo  = True
        verdict     = "FAKE"
        confidence  = round(min(1.0, (0.20 - similarity) * 5 + 0.50), 4)
    elif similarity < 0.32:
        is_misinfo  = True
        verdict     = "SUSPICIOUS"
        confidence  = round(0.35 + (0.32 - similarity) * 2, 4)
    else:
        is_misinfo  = False
        verdict     = "REAL"
        confidence  = round(min(0.45, similarity * 0.4), 4)

    # ── Build explanation ─────────────────────────────────────────────────────
    if is_misinfo:
        explanation = (
            f"Low alignment with trusted sources (score: {similarity:.2f}/1.0). "
            f"The claim may contradict, exaggerate, or omit key facts. "
            f"Top source: \"{sources[0]['title']}\"."
        )
    else:
        explanation = (
            f"Claim broadly consistent with retrieved sources (score: {similarity:.2f}/1.0). "
            f"Verified against: \"{sources[0]['title']}\"."
        )

    # ── Corrected version ("Real Deal") ──────────────────────────────────────
    corrected = ""
    if is_misinfo:
        if wiki_extract:
            corrected = (
                f"According to Wikipedia — {wiki_results[0]['title']}:\n\n"
                f"{wiki_extract[:600].strip()}"
            )
        elif corpus:
            corrected = (
                f"What trusted sources actually say:\n\n"
                f"{corpus[:500].strip()}"
            )

    return {
        "is_news":          True,
        "is_misinformation": is_misinfo,
        "confidence":        confidence,
        "verdict":           verdict,
        "explanation":       explanation,
        "corrected_version": corrected,
        "sources":           sources,
    }
