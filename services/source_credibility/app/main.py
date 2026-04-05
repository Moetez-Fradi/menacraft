"""
Source Credibility Service — FastAPI entry-point.

Endpoints:
  POST /analyze   Assess source credibility
  GET  /health    Liveness / readiness probe
"""

from __future__ import annotations

import logging
import time

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from app.analyzers.account import analyze_account
from app.analyzers.explainability import build_explainability
from app.analyzers.links import analyze_links
from app.analyzers.writing_style import analyze_writing_style
from app.config import SERVICE_HOST, SERVICE_PORT
from app.models import CredibilityRequest, CredibilityResponse
from app.scorer import compute_score

# ── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("source_credibility")

# ── FastAPI app ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="Source Credibility Service",
    description=(
        "Analyses the credibility of a content source by evaluating "
        "account behaviour, writing style, and linked domains."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Middleware: request timer ───────────────────────────────────────────────

@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.1f}"
    logger.info("%s %s — %.1f ms", request.method, request.url.path, elapsed_ms)
    return response


# ── Endpoints ───────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serves the testing UI."""
    index_path = Path(__file__).parent.parent / "index.html"
    if index_path.exists():
        return index_path.read_text(encoding="utf-8")
    return "UI not found. Please create 'index.html' in the service root."


@app.get("/health")
async def health():
    """Liveness probe for Docker / orchestrator."""
    return {"status": "ok", "service": "source_credibility"}


@app.post("/analyze", response_model=CredibilityResponse)
async def analyze(req: CredibilityRequest):
    """
    Run the full credibility analysis pipeline:

    1. Account behaviour heuristics
    2. URL / domain analysis
    3. Writing-style consistency (LLM or heuristic)
    4. Score aggregation + risk mapping
    """

    logger.info(
        "Analysing source: @%s (%d links, text=%s)",
        req.author.username,
        len(req.links),
        "yes" if req.text else "no",
    )

    # ── 1. Account analysis (sync — pure computation) ───────────────────
    account_result = analyze_account(req.author)

    # ── 2. Link / domain analysis (sync — cached lookups) ──────────────
    links_result = analyze_links(req.links)

    # ── 3. Writing style (async — may call LLM) ────────────────────────
    writing_result = await analyze_writing_style(req.text)

    # ── 4. Score aggregation ────────────────────────────────────────────
    score_result = compute_score(account_result, links_result, writing_result)

    # ── 5. Explainability layer (LLM + deterministic fallback) ─────────
    explainability = await build_explainability(
        req=req,
        account=account_result,
        links=links_result,
        writing=writing_result,
        score=score_result,
    )

    # ── Build explanation ───────────────────────────────────────────────
    all_flags = list(
        dict.fromkeys(account_result.flags + links_result.flags)
    )
    if writing_result.inconsistent:
        all_flags.append("inconsistent_writing_style")

    explanation = _build_explanation(
        req, score_result.risk_level, all_flags, writing_result, links_result
    )

    return CredibilityResponse(
        credibility_score=score_result.score,
        risk_level=score_result.risk_level,
        flags=all_flags,
        explanation=explanation,
        explainability=explainability,
    )


# ── Helpers ─────────────────────────────────────────────────────────────────

def _build_explanation(
    req: CredibilityRequest,
    risk: str,
    flags: list[str],
    writing,
    links,
) -> str:
    """Compose a concise, human-readable explanation."""

    parts: list[str] = []

    if risk == "LOW":
        parts.append(
            f"The source @{req.author.username} appears credible."
        )
    elif risk == "MEDIUM":
        parts.append(
            f"The source @{req.author.username} shows some signs that warrant caution."
        )
    else:
        parts.append(
            f"The source @{req.author.username} raises significant credibility concerns."
        )

    if "new_account" in flags:
        parts.append(
            f"The account is only {req.author.account_age_days} days old."
        )
    if "low_followers" in flags:
        parts.append(
            f"The account has very few followers ({req.author.followers})."
        )
    if "high_follow_ratio" in flags:
        parts.append("The following-to-followers ratio is unusually high.")
    if "high_post_frequency" in flags:
        parts.append("The posting frequency is abnormally high.")
    if "suspicious_domain" in flags:
        domains = ", ".join(links.suspicious_domains[:3])
        parts.append(f"Suspicious domains detected: {domains}.")
    if "inconsistent_writing_style" in flags:
        parts.append(
            f"Writing style flagged ({writing.method}): {writing.detail}."
        )

    return " ".join(parts)


# ── Run directly ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=SERVICE_HOST,
        port=SERVICE_PORT,
        reload=True,
    )
