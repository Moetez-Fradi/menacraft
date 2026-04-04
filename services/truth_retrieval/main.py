"""
Intelligence & Truth Service – FastAPI
Handles:  POST /source  (Axis 3 – Source Credibility)
          POST /truth   (Axis 4 – Truth Retrieval)
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from retriever import evaluate_source, verify_truth

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("truth-service")

app = FastAPI(title="MENACRAFT Truth Service", version="1.0.0")


# ---- request models ----

class AnalyzeRequest(BaseModel):
    session_id: str
    clean_text: str = ""
    clean_image_base64: Optional[str] = None
    content_type: str = "text"
    metadata: dict = {}


class SourceRequest(BaseModel):
    session_id: str
    username: str = ""
    bio: str = ""
    links: List[str] = []
    # Also accept unified payload (metadata may carry account info)
    metadata: dict = {}
    clean_text: str = ""


# ---- endpoints ----

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/source")
def source(req: SourceRequest):
    """Axis 3 – evaluate source credibility."""
    # Support both dedicated SourceRequest and AnalyzeRequest-shaped payloads
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
    """Axis 4 – verify claim against live sources (only for news content)."""
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
