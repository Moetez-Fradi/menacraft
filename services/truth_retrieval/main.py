"""
Intelligence & Truth Service — FastAPI

Endpoints:
  POST /source  (Axis 3 – Source Credibility)
  POST /truth   (Axis 4 – Truth Retrieval)
  GET  /health
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from retriever import evaluate_source, verify_truth

# ── Logging ────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("truth-service")

# ── App ────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="MENACRAFT Truth Service",
    description="Truth retrieval and source credibility scoring.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.1f}"
    logger.info("%s %s — %.1f ms", request.method, request.url.path, elapsed_ms)
    return response


# ── Request models ─────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    session_id: str
    clean_text: str = ""
    clean_image_base64: Optional[str] = None
    content_type: str = "text"
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceRequest(BaseModel):
    session_id: str
    username: str = ""
    bio: str = ""
    links: list[str] = Field(default_factory=list)
    # Also accept unified payload (metadata may carry account info)
    metadata: dict[str, Any] = Field(default_factory=dict)
    clean_text: str = ""


# ── Endpoints ──────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "truth_retrieval"}


@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    index_path = Path(__file__).parent / "index.html"
    if index_path.exists():
        return index_path.read_text(encoding="utf-8")
    return "UI not found. Please create 'index.html' in the service root."


@app.post("/source")
async def source(req: SourceRequest):
    """Axis 3 – evaluate source credibility."""
    username = req.username or str(req.metadata.get("username", ""))
    bio = req.bio or str(req.metadata.get("bio", ""))
    links_raw = req.links or req.metadata.get("links", [])
    links = [str(l) for l in links_raw] if isinstance(links_raw, list) else []

    try:
        result = evaluate_source(username=username, bio=bio, links=links)
        logger.info("source session=%s risk=%s", req.session_id, result["risk_level"])
        return result
    except Exception as exc:
        logger.exception("source error")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/truth")
async def truth(req: AnalyzeRequest):
    """Axis 4 – verify claim against live sources (news-only)."""
    if not req.clean_text:
        raise HTTPException(status_code=400, detail="clean_text is required for truth verification.")
    try:
        result = await verify_truth(req.clean_text)
        logger.info(
            "truth session=%s verdict=%s misinfo=%s",
            req.session_id, result["verdict"], result["is_misinformation"],
        )
        return result
    except Exception as exc:
        logger.exception("truth error")
        raise HTTPException(status_code=500, detail=str(exc))
