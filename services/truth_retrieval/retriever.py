"""
Axis 3 – Source Credibility
Axis 4 – Truth Retrieval

Rebuilt pipeline with:
  - Better query extraction and news detection
  - Multi-source evidence ranking
  - Weighted similarity scoring
  - Clearer verdicts and explanations
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import urllib.parse
from dataclasses import dataclass
from typing import Iterable, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("truth-service")

# ─────────────────────────────────────────────────────────────────────────────
# Axis 3 – Source Credibility
# ─────────────────────────────────────────────────────────────────────────────

BLACKLISTED_DOMAINS = {
    "fakenewssite.com", "propaganda.ru", "disinfo.net",
    "clickbait.io", "conspiracyhub.org", "infowars.com",
    "naturalcure.biz", "worldnewsdailyreport.com", "empirenews.net",
}

_BOT_PATTERNS = re.compile(
    r"(bot\d+|[a-z]{1,4}\d{5,}|[A-Z]{2,}\d{3,}|user_\d+|account_\d+|"
    r"temp_[a-z]+|rand[a-z]*\d+|[a-z]+_[a-z]+\d{4,})",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"https?://([^/\s]+)")


def evaluate_source(username: str = "", bio: str = "", links: list[str] | None = None) -> dict:
    links = links or []
    signals: list[str] = []
    score = 1.0

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

    # Bio heuristics
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
    risk = "low" if score > 0.65 else "medium" if score > 0.35 else "high"

    return {
        "credibility_score": score,
        "risk_level": risk,
        "signals": signals if signals else ["No suspicious signals detected."],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Axis 4 – Truth Retrieval
# ─────────────────────────────────────────────────────────────────────────────

TRUSTED_DOMAIN_WEIGHTS = {
    "reuters.com": 1.00,
    "apnews.com": 0.98,
    "bbc.com": 0.96,
    "bbc.co.uk": 0.96,
    "aljazeera.com": 0.94,
    "theguardian.com": 0.92,
    "nytimes.com": 0.92,
    "washingtonpost.com": 0.92,
    "cnn.com": 0.90,
    "npr.org": 0.90,
    "en.wikipedia.org": 0.88,
    "wikipedia.org": 0.86,
}


def _env_float(key: str, default: float) -> float:
    raw = os.getenv(key, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "y", "on"}


def _env_str(key: str, default: str) -> str:
    raw = os.getenv(key, "").strip()
    return raw if raw else default


# Verdict thresholds (score = similarity * domain_weight)
FAKE_MAX = _env_float("TRUTH_SCORE_FAKE_MAX", 0.25)
SUSPICIOUS_MAX = _env_float("TRUTH_SCORE_SUSPICIOUS_MAX", 0.38)
UNVERIFIED_MAX = _env_float("TRUTH_SCORE_UNVERIFIED_MAX", 0.50)

# RAG configuration
RAG_ENABLED = _env_bool("TRUTH_RAG_ENABLED", True)
GDELT_MAX_RESULTS = int(_env_float("GDELT_MAX_RESULTS", 6))
OLLAMA_BASE_URL = _env_str("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = _env_str("OLLAMA_MODEL", "llama3.1:8b")

_NEWS_KW = re.compile(
    r"\b(president|minister|attack|war|government|election|court|police|"
    r"military|killed|arrested|announced|confirmed|denied|breaking|report|"
    r"exclusive|according|official|signed|launched|declared|sanction|strike|"
    r"ceasefire|protest|verdict|investigation|airstrike)\b",
    re.IGNORECASE,
)
_DATE_RE = re.compile(r"\b(\d{1,2}\s+\w+\s+\d{4}|\w+\s+\d{1,2},?\s+\d{4}|\d{4})\b")
_CLAIM_RE = re.compile(
    r"\b(is|are|was|were|has|have|will|would|can|claims?|alleges?|says?|"
    r"states?|reports?|confirms?|denies?)\b",
    re.IGNORECASE,
)
_RECENCY_RE = re.compile(
    r"\b(today|yesterday|last night|this morning|this week|this month|"
    r"last week|last month|just now|right now|breaking)\b",
    re.IGNORECASE,
)

_NOISE_WORDS = re.compile(
    r"\b(breaking|exclusive|just\s+in|developing|report|allegedly|secretly|"
    r"confirmed|announced|shocking|unbelievable|bombshell|share\s+before|"
    r"deleted|viral|trending|they\s+don'?t|you\s+won'?t|must[\s-]?see|"
    r"last\s+night|right\s+now|this\s+morning|this\s+week|this\s+year)\b",
    re.IGNORECASE,
)

_CAPS_PHRASE = re.compile(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,4})\b")
_URL_IN_TEXT = re.compile(r"https?://\S+")

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "so", "for", "to", "of",
    "in", "on", "at", "by", "with", "from", "as", "is", "are", "was", "were",
    "be", "been", "it", "this", "that", "these", "those", "he", "she", "they",
    "we", "you", "i", "has", "have", "had", "will", "would", "can", "could",
    "should", "about", "into", "over", "under", "after", "before", "during",
}


@dataclass
class Evidence:
    title: str
    url: str
    snippet: str
    domain: str
    weight: float
    similarity: float = 0.0
    source_type: str = "web"


def _normalize_text(text: str) -> str:
    text = _URL_IN_TEXT.sub("", text)
    text = re.sub(r'\[(NAME|EMAIL|PHONE)_\d+\]\s*', '', text)
    text = text.replace("\n", " ").strip()
    text = re.sub(r"\s{2,}", " ", text)
    return text[:2000]


def is_news_content(text: str) -> bool:
    if not text:
        return False
    has_news_kw = bool(_NEWS_KW.search(text))
    has_date = bool(_DATE_RE.search(text))
    has_claim = bool(_CLAIM_RE.search(text))
    caps = _CAPS_PHRASE.findall(text)
    has_named_entity = any(len(c.split()) >= 2 for c in caps)
    return (has_news_kw and has_claim) or (has_date and has_claim) or has_named_entity


def _score_sentence(s: str) -> int:
    score = 0
    score += len(_NEWS_KW.findall(s)) * 2
    score += len(_DATE_RE.findall(s)) * 2
    score += len([c for c in _CAPS_PHRASE.findall(s) if len(c.split()) >= 2]) * 2
    score += len(_CLAIM_RE.findall(s))
    return score


def extract_query(text: str) -> str:
    """
    Extract a focused search query from the claim text.

    Strategy:
    1. Strip anonymizer placeholders and URLs.
    2. Pick the most "news-like" sentence.
    3. For short claims, use the sentence directly (it's already a good query).
    4. For long texts, distill to key named entities + keywords.
    """
    text = _normalize_text(text)
    sentences = [s.strip() for s in re.split(r"[.!?]", text) if s.strip()]
    if not sentences:
        return text[:140]

    best = max(sentences, key=_score_sentence)
    best = _NOISE_WORDS.sub("", best)
    best = re.sub(r'["\']', "", best)
    best = re.sub(r"\s{2,}", " ", best).strip()

    # Short claims are already good search queries — use as-is
    if len(best.split()) <= 15:
        return best[:140]

    named = [p for p in _CAPS_PHRASE.findall(best) if len(p.split()) >= 2]
    named = named[:3]

    keywords = [
        w for w in re.findall(r"[A-Za-z]{4,}", best)
        if w.lower() not in _STOPWORDS
    ][:6]

    # Always include years found in the claim
    years = re.findall(r"\b(20\d{2}|19\d{2})\b", best)

    parts = []
    if named:
        parts.extend(named)
    if keywords:
        parts.extend(keywords)
    parts.extend(years)

    query = " ".join(dict.fromkeys(parts)) or best
    return query[:140]


def _domain_weight(url: str) -> float:
    domain = _domain_from_url(url)
    for d, w in TRUSTED_DOMAIN_WEIGHTS.items():
        if domain.endswith(d):
            return w
    return 0.80


def _domain_from_url(url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(url)
        return parsed.netloc.lower().replace("www.", "")
    except Exception:
        return ""


_HEADERS = {
    "User-Agent": "MENACRAFT-DigitalSieve/2.0 (fact-checking research tool) python-httpx",
    "Accept": "application/json",
}


async def _fetch_json(client: httpx.AsyncClient, url: str) -> dict:
    resp = await client.get(url)
    resp.raise_for_status()
    return resp.json()


async def search_wikipedia(client: httpx.AsyncClient, query: str, limit: int = 3) -> list[dict]:
    """Search Wikipedia and return article stubs."""
    params = urllib.parse.urlencode({
        "action": "query",
        "list": "search",
        "srsearch": query[:100],
        "format": "json",
        "utf8": 1,
        "srlimit": limit,
    })
    url = f"https://en.wikipedia.org/w/api.php?{params}"
    data = await _fetch_json(client, url)

    results = []
    for item in data.get("query", {}).get("search", []):
        snippet = re.sub(r"<[^>]+>", "", item.get("snippet", "")).strip()
        title = item["title"]
        results.append({
            "title": title,
            "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}",
            "snippet": snippet,
        })
    return results


_EXTRACT_CACHE: dict[str, str] = {}


async def get_wikipedia_extract(client: httpx.AsyncClient, title: str) -> str:
    """Fetch the introductory paragraph of a Wikipedia article."""
    cached = _EXTRACT_CACHE.get(title)
    if cached:
        return cached

    params = urllib.parse.urlencode({
        "action": "query",
        "prop": "extracts",
        "exintro": 1,
        "exsentences": 4,
        "explaintext": 1,
        "format": "json",
        "titles": title,
    })
    url = f"https://en.wikipedia.org/w/api.php?{params}"
    data = await _fetch_json(client, url)

    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        extract = page.get("extract", "").strip()
        if extract:
            _EXTRACT_CACHE[title] = extract
            return extract
    return ""


async def fetch_ddg_results(client: httpx.AsyncClient, query: str, max_results: int = 4) -> list[dict]:
    """Real DuckDuckGo web search via duckduckgo-search library, with retry on rate-limit."""
    def _search() -> list[dict]:
        import time
        from duckduckgo_search import DDGS
        from duckduckgo_search.exceptions import RatelimitException, DuckDuckGoSearchException

        backoff = 2.0
        for attempt in range(3):
            try:
                with DDGS() as ddgs:
                    hits = list(ddgs.text(query[:120], max_results=max_results))
                return [
                    {"title": h.get("title", ""), "url": h.get("href", ""), "snippet": h.get("body", "")[:240]}
                    for h in hits
                ]
            except RatelimitException:
                if attempt == 2:
                    logger.warning("ddg search rate-limited after %d attempts", attempt + 1)
                    return []
                time.sleep(backoff)
                backoff *= 2
            except DuckDuckGoSearchException as exc:
                logger.warning("ddg search failed: %s", exc)
                return []
            except Exception as exc:
                logger.warning("ddg search unexpected error: %s", exc)
                return []
        return []

    return await asyncio.to_thread(_search)


async def search_gdelt(client: httpx.AsyncClient, query: str, limit: int = 6) -> list[dict]:
    # Free, no-key GDELT 2.1 Doc API with retry/backoff on rate limit
    params = urllib.parse.urlencode({
        "query": query[:80],
        "mode": "ArtList",
        "maxrecords": max(1, min(50, limit)),
        "format": "json",
        "sort": "HybridRel",
    })
    url = f"https://api.gdeltproject.org/api/v2/doc/doc?{params}"
    backoff = 0.6
    for attempt in range(3):
        try:
            resp = await client.get(url, headers=_HEADERS)
            if resp.status_code == 429:
                await asyncio.sleep(backoff)
                backoff *= 2
                continue
            resp.raise_for_status()
            data = resp.json()
            items = []
            for r in data.get("articles", [])[:limit]:
                title = r.get("title") or "Untitled"
                url = r.get("url") or ""
                snippet = (r.get("seendate") or "")
                if r.get("sourceCountry"):
                    snippet = f"{snippet} · {r.get('sourceCountry')}"
                items.append({
                    "title": title,
                    "url": url,
                    "snippet": snippet[:240],
                })
            return items
        except Exception as exc:
            if attempt == 2:
                raise exc
            await asyncio.sleep(backoff)
            backoff *= 2
    return []


# ── Sentence similarity ──────────────────────────────────────────────────────

_SIMILARITY_MODEL = None


def _get_similarity_model():
    global _SIMILARITY_MODEL
    if _SIMILARITY_MODEL is None:
        from sentence_transformers import SentenceTransformer
        _SIMILARITY_MODEL = SentenceTransformer("paraphrase-MiniLM-L3-v2", device="cpu")
    return _SIMILARITY_MODEL


def _sentence_similarity(a: str, b: str) -> float:
    """Cosine similarity via sentence-transformers."""
    try:
        import numpy as np
        model = _get_similarity_model()
        embs = model.encode([a[:256], b[:256]])
        cos = float(
            np.dot(embs[0], embs[1]) /
            (np.linalg.norm(embs[0]) * np.linalg.norm(embs[1]) + 1e-9)
        )
        return max(0.0, min(1.0, cos))
    except Exception:
        return 0.45


def _rank_sources(sources: Iterable[Evidence]) -> list[Evidence]:
    return sorted(sources, key=lambda s: (-s.weight, s.title))


def _build_evidence(raw: list[dict], source_type: str) -> list[Evidence]:
    items: list[Evidence] = []
    for s in raw:
        url = s.get("url", "")
        domain = _domain_from_url(url)
        items.append(Evidence(
            title=s.get("title", "Untitled"),
            url=url,
            snippet=s.get("snippet", ""),
            domain=domain,
            weight=_domain_weight(url),
            source_type=source_type,
        ))
    return items


async def _best_similarity(claim: str, evidences: list[Evidence]) -> tuple[float, Optional[Evidence]]:
    """Run CPU-bound similarity scoring in a thread to avoid blocking the event loop."""
    def _compute() -> tuple[float, Optional[Evidence]]:
        best = None
        best_score = 0.0
        for ev in evidences:
            if not ev.snippet and not ev.title:
                continue
            text = ev.snippet or ev.title
            ev.similarity = _sentence_similarity(claim, text)
            score = ev.similarity * ev.weight
            if score > best_score:
                best_score = score
                best = ev
        return best_score, best

    return await asyncio.to_thread(_compute)


def _confidence(score: float, sources: list[Evidence]) -> float:
    if not sources:
        return 0.25
    quality = sum(s.weight for s in sources[:3]) / min(3, len(sources))
    coverage = min(1.0, len(sources) / 4.0)
    conf = (score * 0.65 + 0.35 * quality) * (0.6 + 0.4 * coverage)
    return max(0.0, min(1.0, round(conf, 4)))


def _has_only_encyclopedia_sources(sources: list[Evidence]) -> bool:
    if not sources:
        return True
    for s in sources:
        if "wikipedia.org" not in s.domain:
            return False
    return True


def _safe_json_from_text(text: str) -> dict:
    try:
        return json.loads(text)
    except Exception:
        pass
    # Try to extract the first JSON object
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return {}
    return {}


async def _ollama_summarize(
    client: httpx.AsyncClient,
    claim: str,
    sources: list[Evidence],
) -> dict:
    top = sources[:4]
    if not top:
        return {}
    source_lines = []
    for i, s in enumerate(top, start=1):
        snippet = (s.snippet or s.title).replace("\n", " ").strip()
        snippet = snippet[:240]
        source_lines.append(f"{i}. {s.title} ({s.url}) — {snippet}")

    prompt = (
        "You are a strict fact-checking assistant. Your job is to verify whether a specific claim is true.\n\n"
        "Instructions:\n"
        "- SUPPORTED: the sources explicitly confirm the claim's specific facts.\n"
        "- REFUTED: the sources contradict the claim, or the claim makes an implausible/unsupported assertion.\n"
        "- UNVERIFIED: the sources discuss related topics but do not confirm or deny the specific claim.\n"
        "- Do NOT mark a claim SUPPORTED just because the sources mention related topics.\n"
        "- Statistical claims (rankings, 'leading country', percentages) require explicit data to be SUPPORTED.\n"
        "- If sources are only tangentially related, use REFUTED or UNVERIFIED.\n\n"
        "Return ONLY valid JSON with these keys:\n"
        "  verdict: SUPPORTED | REFUTED | UNVERIFIED\n"
        "  confidence: float 0-1\n"
        "  summary: 2-4 sentences explaining your reasoning\n"
        "  key_sources: list of URLs used\n\n"
        f"Claim: {claim}\n\n"
        "Sources:\n"
        + "\n".join(source_lines)
    )

    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.2},
    }
    try:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        result = _safe_json_from_text(data.get("response", ""))
        return result if isinstance(result, dict) else {}
    except Exception as exc:
        logger.warning("ollama summarize failed (%s): %s", type(exc).__name__, exc)
        return {}


# ── Main truth verification ──────────────────────────────────────────────────

async def verify_truth(text: str) -> dict:
    """
    Full Axis 4 pipeline:
      1. Detect if content makes a verifiable real-world claim
      2. Search Wikipedia (primary) + DuckDuckGo (secondary)
      3. Compare claim vs sources via sentence similarity
      4. Generate corrected version from Wikipedia extract (if needed)
    """
    claim = _normalize_text(text)
    if not is_news_content(claim):
        return {
            "is_news": False,
            "is_misinformation": False,
            "confidence": 0.0,
            "verdict": "REAL",
            "explanation": "Content does not appear to be a verifiable news claim.",
            "corrected_version": "",
            "sources": [],
        }

    query = extract_query(claim)
    logger.info("truth query: %s", query[:80])

    search_timeout = httpx.Timeout(10.0, connect=3.0, read=7.0)
    ollama_timeout = httpx.Timeout(180.0, connect=5.0, read=170.0)
    async with httpx.AsyncClient(timeout=search_timeout, follow_redirects=True, headers=_HEADERS) as client:
        wiki_task = asyncio.create_task(search_wikipedia(client, query, limit=3))
        ddg_task = asyncio.create_task(fetch_ddg_results(client, query, max_results=3))
        gdelt_task = None
        use_rag = RAG_ENABLED
        if use_rag:
            gdelt_task = asyncio.create_task(search_gdelt(client, query, limit=GDELT_MAX_RESULTS))
        try:
            if gdelt_task:
                wiki_results, ddg_results, gdelt_results = await asyncio.gather(
                    wiki_task, ddg_task, gdelt_task
                )
            else:
                wiki_results, ddg_results = await asyncio.gather(wiki_task, ddg_task)
                gdelt_results = []
        except Exception as exc:
            logger.warning("source search failed: %s", exc)
            wiki_results, ddg_results, gdelt_results = [], [], []

        wiki_extract = ""
        if wiki_results:
            try:
                wiki_extract = await get_wikipedia_extract(client, wiki_results[0]["title"])
            except Exception:
                wiki_extract = ""

    sources: list[Evidence] = []
    sources.extend(_build_evidence(wiki_results, "wikipedia"))
    sources.extend(_build_evidence(ddg_results, "ddg"))
    sources.extend(_build_evidence(gdelt_results, "gdelt"))
    sources = _rank_sources(sources)[:6]

    if not sources:
        return {
            "is_news": True,
            "is_misinformation": False,
            "confidence": 0.25,
            "verdict": "UNVERIFIED",
            "explanation": "Could not retrieve sources to verify this claim. Treat with caution.",
            "corrected_version": "",
            "sources": [],
        }

    # Prefer richer corpus when available
    if wiki_extract and wiki_results:
        top_title = wiki_results[0]["title"]
        for ev in sources:
            if ev.source_type == "wikipedia" and ev.title == top_title:
                ev.snippet = wiki_extract
                break

    best_score, best_ev = await _best_similarity(claim, sources)
    conf = _confidence(best_score, sources)

    rag_result: dict = {}
    if use_rag and sources:
        async with httpx.AsyncClient(timeout=ollama_timeout) as rag_client:
            rag_result = await _ollama_summarize(rag_client, claim, sources)

    # Recency-aware fallback: current-events claim but only encyclopedia sources
    if _RECENCY_RE.search(claim) and _has_only_encyclopedia_sources(sources):
        return {
            "is_news": True,
            "is_misinformation": False,
            "confidence": 0.30,
            "verdict": "UNVERIFIED",
            "explanation": "Claim appears time-sensitive, but only encyclopedia sources were found.",
            "corrected_version": "",
            "sources": [{"title": s.title, "url": s.url} for s in sources],
        }

    rag_failed = use_rag and not rag_result

    if best_score < FAKE_MAX:
        is_misinfo = True
        verdict = "FAKE"
    elif best_score < SUSPICIOUS_MAX:
        is_misinfo = True
        verdict = "SUSPICIOUS"
    elif best_score < UNVERIFIED_MAX:
        # If RAG was supposed to run but failed, don't upgrade to REAL — keep UNVERIFIED
        is_misinfo = False
        verdict = "UNVERIFIED"
    else:
        if rag_failed:
            # High similarity means the topic was found, but without LLM we can't
            # confirm the specific fact — stay conservative
            is_misinfo = False
            verdict = "UNVERIFIED"
        else:
            is_misinfo = False
            verdict = "REAL"

    if best_ev:
        if is_misinfo:
            explanation = (
                f"Low alignment with trusted sources (score: {best_score:.2f}/1.0). "
                f"Top match: \"{best_ev.title}\"."
            )
        elif rag_failed:
            explanation = (
                f"Could not reach Ollama for fact analysis (score: {best_score:.2f}/1.0). "
                f"Nearest source: \"{best_ev.title}\". Treat result as unverified."
            )
        else:
            explanation = (
                f"Claim broadly consistent with retrieved sources (score: {best_score:.2f}/1.0). "
                f"Top match: \"{best_ev.title}\"."
            )
    else:
        explanation = "Insufficient evidence to compare this claim."

    corrected = ""
    if is_misinfo:
        if wiki_extract:
            corrected = (
                f"According to Wikipedia — {wiki_results[0]['title']}:\n\n"
                f"{wiki_extract[:600].strip()}"
            )
        elif best_ev and best_ev.snippet:
            corrected = (
                "What reliable sources say:\n\n"
                f"{best_ev.snippet[:500].strip()}"
            )

    rag_summary = ""
    rag_verdict = ""
    if rag_result:
        rag_summary = str(rag_result.get("summary", "")).strip()
        rag_verdict = str(rag_result.get("verdict", "")).strip().upper()
        rag_conf_raw = rag_result.get("confidence")
        try:
            rag_conf = float(rag_conf_raw)
            rag_conf = max(0.0, min(1.0, rag_conf))
        except Exception:
            rag_conf = None

        if rag_verdict in {"SUPPORTED", "REFUTED", "UNVERIFIED"}:
            if rag_verdict == "SUPPORTED":
                verdict = "REAL"
                is_misinfo = False
            elif rag_verdict == "REFUTED":
                verdict = "FAKE"
                is_misinfo = True
            else:
                verdict = "UNVERIFIED"
                is_misinfo = False
            if rag_conf is not None:
                conf = rag_conf
            if rag_summary:
                explanation = rag_summary
                if is_misinfo:
                    corrected = rag_summary

    return {
        "is_news": True,
        "is_misinformation": is_misinfo,
        "confidence": conf if is_misinfo else round(min(conf, 0.55), 4),
        "verdict": verdict,
        "explanation": explanation,
        "corrected_version": corrected,
        "rag_summary": rag_summary,
        "rag_used": bool(rag_result),
        "sources": [{"title": s.title, "url": s.url} for s in sources],
    }
