"""
ML Inference Engine – FastAPI
Handles:  POST /classify  (Axis 1)
          POST /context   (Axis 2)
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from detect import check_context, classify_image, classify_text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ml-engine")

app = FastAPI(title="MENACRAFT ML Engine", version="1.0.0")


# ---- request / response models ----

class AnalyzeRequest(BaseModel):
    session_id: str
    clean_text: str = ""
    clean_image_base64: Optional[str] = None
    content_type: str = "text"
    metadata: dict = {}


# ---- endpoints ----

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/classify")
def classify(req: AnalyzeRequest):
    """Axis 1 – classify content as real | ai_generated | altered."""
    try:
        if req.content_type == "image" and req.clean_image_base64:
            result = classify_image(req.clean_image_base64)
        else:
            result = classify_text(req.clean_text)
        logger.info("classify session=%s category=%s", req.session_id, result["category"])
        return result
    except Exception as exc:
        logger.exception("classify error")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/context")
def context(req: AnalyzeRequest):
    """Axis 2 – detect misleading caption/image mismatch."""
    try:
        result = check_context(req.clean_text, req.clean_image_base64)
        logger.info("context session=%s misleading=%s", req.session_id, result["is_misleading"])
        return result
    except Exception as exc:
        logger.exception("context error")
        raise HTTPException(status_code=500, detail=str(exc))
