from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from PIL import Image

from app.analyzers.audio_analyzer import AudioAnalyzer
from app.analyzers.image_analyzer import ImageAnalyzer
from app.analyzers.text_analyzer import TextAnalyzer
from app.analyzers.video_analyzer import VideoAnalyzer
from app.clients.ollama_client import OllamaLLMClient
from app.contextual_consistency.claim_parser import ClaimParser
from app.contextual_consistency.consistency_rules import ConsistencyRules
from app.contextual_consistency.entailment_scorer import EntailmentScorer
from app.contextual_consistency.evidence_extractor import EvidenceExtractor
from app.contextual_consistency.fusion import ContextFusion
from app.contextual_consistency.llm_judge import LLMJudge
from app.contextual_consistency.reference_retriever import ReferenceRetriever
from app.contextual_consistency.service import ContextualConsistencyService
from app.db.rate_limiter import SQLiteSlidingWindowRateLimiter
from app.embedders.embeddings import EmbedderService
from app.fusion.fusion import FusionScorer
from app.normalizers.case_normalizer import CaseNormalizer
from app.qdrant.store import QdrantEvidenceStore
from app.services.evidence import EvidenceBuilder
from app.shared.config import settings
from app.shared.db import SQLiteRepository
from app.shared.schemas import AnalysisReport, CaseInput, ContextScoreBundle, JobStatus, SuspiciousSpan, SuspiciousTimestamp
from app.shared.storage import LocalStorage

logger = logging.getLogger(__name__)


class AnalysisPipelineService:
    def __init__(self) -> None:
        self.repo = SQLiteRepository()
        self.storage = LocalStorage()
        self.normalizer = CaseNormalizer(self.storage)

        self.llm_client = OllamaLLMClient()
        self.embedder = EmbedderService()
        self.qdrant = QdrantEvidenceStore()

        self.text_analyzer = TextAnalyzer(self.llm_client)
        self.image_analyzer = ImageAnalyzer(self.embedder, self.qdrant, self.llm_client)
        self.audio_analyzer = AudioAnalyzer()
        self.video_analyzer = VideoAnalyzer(self.image_analyzer)

        self.fusion = FusionScorer()
        self.evidence_builder = EvidenceBuilder()

        self.context_service = ContextualConsistencyService(
            claim_parser=ClaimParser(),
            evidence_extractor=EvidenceExtractor(),
            reference_retriever=ReferenceRetriever(self.embedder, self.qdrant),
            rules=ConsistencyRules(),
            entailment=EntailmentScorer(self.embedder),
            llm_judge=LLMJudge(self.llm_client),
            fusion=ContextFusion(),
        )
        self.rate_limiter = SQLiteSlidingWindowRateLimiter(self.repo)

    def accept_case(self, case_input: CaseInput, client_ip: str, endpoint: str = "/v1/analyze") -> tuple[str, dict[str, Any]]:
        self.rate_limiter.check(client_ip, endpoint, limit_per_minute=12)
        normalized = self.normalizer.normalize(case_input)

        payload = {
            "case_input": case_input.model_dump(),
            "normalized": normalized.model_dump(),
        }
        self.repo.create_case(normalized.case_id, payload, status=JobStatus.ACCEPTED.value)
        self.repo.insert_job_event(normalized.case_id, JobStatus.ACCEPTED.value, stage="ingest", message="Case accepted")

        summary = {
            "content_type": case_input.content_type,
            "text_length": len(normalized.normalized_text),
            "image_count": len(normalized.image_artifacts),
            "video_frame_count": len(normalized.video_frame_artifacts),
            "audio_count": len(normalized.audio_artifacts),
        }
        return normalized.case_id, summary

    def run_authenticity(self, case_id: str) -> AnalysisReport:
        row = self.repo.get_case(case_id)
        if not row:
            raise ValueError(f"Unknown case_id: {case_id}")

        payload = json.loads(row.payload_json)
        normalized_payload = payload["normalized"]
        case_input_payload = payload["case_input"]

        from app.shared.schemas import NormalizedArtifacts

        artifacts = NormalizedArtifacts.model_validate(normalized_payload)
        self.repo.update_case_status(case_id, JobStatus.PROCESSING.value)
        self.repo.insert_job_event(case_id, JobStatus.PROCESSING.value, stage="analyze", message="Authenticity analysis started")

        text_result = self.text_analyzer.analyze(artifacts.normalized_text)
        if artifacts.normalized_text and settings.require_ollama_for_analyze:
            status = str(text_result.debug.get("ai_feature_status", "unavailable"))
            if status != "ok":
                errors = text_result.debug.get("errors", [])
                details = ", ".join(str(item) for item in errors) if isinstance(errors, list) else str(errors)
                raise RuntimeError(
                    f"ollama_required_for_text_analysis:{details or 'ollama_unavailable'}"
                )

        image_result = self.image_analyzer.analyze([a.path for a in artifacts.image_artifacts], case_id=case_id)
        if artifacts.image_artifacts and settings.require_ollama_for_image_analyze:
            image_status = str(image_result.debug.get("ai_feature_status", "unavailable"))
            if image_status != "ok":
                errors = image_result.debug.get("errors", [])
                details = ", ".join(str(item) for item in errors) if isinstance(errors, list) else str(errors)
                raise RuntimeError(
                    f"ollama_vision_required_for_image_analysis:{details or 'ollama_vision_unavailable'}"
                )

        video_result = self.video_analyzer.analyze([a.path for a in artifacts.video_frame_artifacts], case_id=case_id)
        audio_result = self.audio_analyzer.analyze([a.path for a in artifacts.audio_artifacts])

        cross_modal_consistency = 1.0
        if artifacts.normalized_text and artifacts.image_artifacts:
            text_emb = self.embedder.embed_text(artifacts.normalized_text)
            img = self.image_analyzer.embedder.embed_image(Image.open(artifacts.image_artifacts[0].path).convert("RGB"))
            n = min(len(text_emb), len(img))
            dot = sum(text_emb[i] * img[i] for i in range(n))
            cross_modal_consistency = max(0.0, min(1.0, (dot + 1) / 2))

        qdrant_signal = 0.0
        if artifacts.normalized_text:
            refs = self.qdrant.search("text_embeddings", self.embedder.embed_text(artifacts.normalized_text), limit=1)
            if refs:
                qdrant_signal = float(refs[0]["similarity"])

        scores, evidence, explanation = self.fusion.score(
            text=text_result,
            image=image_result,
            video=video_result,
            audio=audio_result,
            metadata_anomaly_score=0.1 if case_input_payload.get("metadata") else 0.0,
            qdrant_signal=qdrant_signal,
            cross_modal_consistency=cross_modal_consistency,
        )

        model_versions = {
            "ollama_model": self.llm_client.model,
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "image_model": f"image-forensics-v2+{settings.ollama_vision_model}",
            "video_model": "video-keyframe-v1",
        }

        suspicious_parts = [
            SuspiciousSpan(text=e.span or "", reason=e.reason)
            for e in evidence
            if e.type in {"text_span", "image"}
        ]
        suspicious_ts = [
            SuspiciousTimestamp(timestamp_ms=e.timestamp_ms or 0, reason=e.reason, frame_artifact_id=e.artifact_id)
            for e in evidence
            if e.timestamp_ms is not None
        ]

        debug_payload = self.evidence_builder.build_debug_payload(
            {
                "text": text_result.debug,
                "image": image_result.debug,
                "video": video_result.debug,
                "audio": audio_result.debug,
            },
            errors=[],
        )
        clean_evidence = self.evidence_builder.dedupe(evidence)

        report = AnalysisReport(
            case_id=case_id,
            status=JobStatus.COMPLETED.value,
            created_at=datetime.fromisoformat(row.created_at),
            updated_at=datetime.now(timezone.utc),
            scores=scores,
            verdict=scores.verdict.value,
            suspicious_parts=suspicious_parts,
            suspicious_timestamps=suspicious_ts,
            evidence=clean_evidence,
            explanation=explanation,
            debug=debug_payload,
            model_versions=model_versions,
        )

        self.repo.upsert_report(case_id, report.model_dump(mode="json"))
        self.repo.insert_evidence(case_id, [e.model_dump() for e in clean_evidence])
        self.repo.insert_model_run(case_id, "text", self.llm_client.model, text_result.score, text_result.confidence, text_result.debug)
        self.repo.insert_model_run(
            case_id,
            "image",
            f"image-forensics-v2+{settings.ollama_vision_model}",
            image_result.score,
            image_result.confidence,
            image_result.debug,
        )
        self.repo.insert_model_run(case_id, "video", "video-keyframe-v1", video_result.score, video_result.confidence, video_result.debug)
        self.repo.insert_model_run(case_id, "audio", "audio-v1", audio_result.score, audio_result.confidence, audio_result.debug)
        self.repo.update_case_status(case_id, JobStatus.COMPLETED.value)

        return report

    def run_context(self, case_id: str, claim_text: str) -> AnalysisReport:
        row = self.repo.get_case(case_id)
        if not row:
            raise ValueError(f"Unknown case_id: {case_id}")

        payload = json.loads(row.payload_json)
        from app.shared.schemas import NormalizedArtifacts

        artifacts = NormalizedArtifacts.model_validate(payload["normalized"])
        result = self.context_service.analyze(case_id=case_id, claim_text=claim_text, artifacts=artifacts)

        existing = self.repo.get_report(case_id)
        if existing:
            report = AnalysisReport.model_validate(existing)
        else:
            report = AnalysisReport(
                case_id=case_id,
                status=JobStatus.COMPLETED.value,
                created_at=datetime.fromisoformat(row.created_at),
                updated_at=datetime.now(timezone.utc),
            )

        report.context_scores = ContextScoreBundle(
            consistency_score=result.consistency_score,
            confidence=result.confidence,
            verdict=result.verdict,
        )
        report.updated_at = datetime.now(timezone.utc)
        report.references = result.references
        report.debug["context"] = result.debug
        report.explanation = result.explanation

        for item in result.suspicious_parts:
            report.suspicious_parts.append(SuspiciousSpan(text=item.get("text", ""), reason=item.get("reason", "")))

        self.repo.upsert_report(case_id, report.model_dump(mode="json"))
        return report
