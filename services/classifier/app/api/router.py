from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.contextual_consistency.schemas import ContextAnalyzeRequest
from app.services.pipeline import AnalysisPipelineService
from app.shared.config import settings
from app.shared.schemas import AnalyzeAcceptedResponse, CaseInput, FeedbackRequest, JobStatus, LegacyAnalyzeRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["v1"])
legacy_router = APIRouter(tags=["legacy"])
service = AnalysisPipelineService()


@router.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "env": settings.app_env,
    }


@router.get("/models")
def models() -> dict[str, Any]:
    return {
        "ollama_model": service.llm_client.model,
        "ollama_vision_model": settings.ollama_vision_model,
        "require_ollama_for_analyze": settings.require_ollama_for_analyze,
        "require_ollama_for_image_analyze": settings.require_ollama_for_image_analyze,
        "embedding_model": settings.embedding_model_name,
        "qdrant_enabled": settings.qdrant_enabled,
    }


@router.post("/analyze", response_model=AnalyzeAcceptedResponse)
def analyze(req: CaseInput, request: Request) -> AnalyzeAcceptedResponse:
    client_ip = request.client.host if request.client else "unknown"
    case_id, summary = service.accept_case(req, client_ip=client_ip, endpoint="/v1/analyze")

    try:
        service.run_authenticity(case_id)
    except Exception as exc:
        logger.exception("analysis failed for case=%s", case_id)
        raise HTTPException(status_code=500, detail=f"analysis_failed:{exc}")

    return AnalyzeAcceptedResponse(
        case_id=case_id,
        job_status=JobStatus.COMPLETED,
        accepted_at=datetime.now(timezone.utc),
        input_summary=summary,
    )


@router.get("/cases/{case_id}")
def get_case(case_id: str) -> dict[str, Any]:
    row = service.repo.get_case(case_id)
    if not row:
        raise HTTPException(status_code=404, detail="case_not_found")
    return {
        "case_id": row.case_id,
        "status": row.status,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


@router.get("/cases/{case_id}/report")
def get_case_report(case_id: str) -> dict[str, Any]:
    report = service.repo.get_report(case_id)
    if not report:
        raise HTTPException(status_code=404, detail="report_not_found")
    return report


@router.post("/feedback")
def feedback(req: FeedbackRequest) -> dict[str, str]:
    service.repo.add_feedback(req.case_id, req.label, req.note, req.metadata)
    return {"status": "recorded"}


@router.post("/context/analyze")
def context_analyze(req: ContextAnalyzeRequest) -> dict[str, Any]:
    try:
        report = service.run_context(case_id=req.case_id, claim_text=req.claim_text)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("context analysis failed")
        raise HTTPException(status_code=500, detail=f"context_analysis_failed:{exc}")
    return report.model_dump(mode="json")


@router.get("/context/cases/{case_id}")
def context_case(case_id: str) -> dict[str, Any]:
    return get_case(case_id)


@router.get("/context/cases/{case_id}/report")
def context_report(case_id: str) -> dict[str, Any]:
    return get_case_report(case_id)


@legacy_router.get("/health")
def legacy_health() -> dict[str, str]:
    return {"status": "ok"}


@legacy_router.post("/classify")
def legacy_classify(req: LegacyAnalyzeRequest, request: Request) -> dict[str, Any]:
    case_input = CaseInput(
        session_id=req.session_id,
        clean_text=req.clean_text,
        clean_image_base64=req.clean_image_base64,
        content_type=req.content_type,
        metadata=req.metadata,
    )
    client_ip = request.client.host if request.client else "unknown"
    case_id, _ = service.accept_case(case_input, client_ip=client_ip, endpoint="/classify")
    report = service.run_authenticity(case_id)
    scores = report.scores
    if not scores:
        raise HTTPException(status_code=500, detail="no_scores_generated")

    category = "real"
    if scores.ai_generated_score > 0.7:
        category = "ai_generated"
    elif scores.manipulation_score > 0.55:
        category = "altered"

    return {
        "category": category,
        "confidence": round(max(scores.ai_generated_score, scores.manipulation_score, scores.authenticity_score), 4),
        "highlights": [e.reason for e in report.evidence[:5]],
        "reasoning": report.explanation,
        "is_news": False,
        "case_id": case_id,
        "scores": scores.model_dump(),
        "debug": report.debug,
    }


@legacy_router.post("/context")
def legacy_context(req: LegacyAnalyzeRequest) -> dict[str, Any]:
    claim = req.clean_text
    if not req.session_id:
        raise HTTPException(status_code=400, detail="session_id_required")

    row = service.repo.get_case(req.session_id)
    case_id = req.session_id
    if not row:
        case_input = CaseInput(
            session_id=req.session_id,
            clean_text=req.clean_text,
            clean_image_base64=req.clean_image_base64,
            content_type=req.content_type,
            metadata=req.metadata,
        )
        case_id, _ = service.accept_case(case_input, client_ip="legacy", endpoint="/context")

    report = service.run_context(case_id=case_id, claim_text=claim)
    context_scores = report.context_scores
    if not context_scores:
        raise HTTPException(status_code=500, detail="context_scores_missing")

    is_misleading = context_scores.verdict.value == "likely_miscontexted"
    return {
        "is_misleading": is_misleading,
        "confidence": context_scores.confidence,
        "explanation": report.explanation,
        "case_id": case_id,
        "context": context_scores.model_dump(),
        "signals": report.debug.get("context", {}).get("rules", []),
    }
