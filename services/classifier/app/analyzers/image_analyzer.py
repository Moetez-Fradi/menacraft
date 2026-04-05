from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from app.analyzers.base import AnalyzerResult, BaseAnalyzer
from app.clients.ollama_client import OllamaLLMClient
from app.embedders.embeddings import EmbedderService
from app.qdrant.http_similarity import QdrantHTTPSimilaritySearch
from app.qdrant.store import QdrantEvidenceStore
from app.shared.config import settings
from app.shared.constants import IMAGE_EMBEDDINGS_COLLECTION
from app.shared.schemas import EvidenceItem, LLMMessage
from app.shared.scoring import clamp01


class ImageAnalyzer(BaseAnalyzer):
    name = "image"

    def __init__(self, embedder: EmbedderService, qdrant: QdrantEvidenceStore, llm_client: OllamaLLMClient) -> None:
        self.embedder = embedder
        self.qdrant = qdrant
        self.llm_client = llm_client
        self.qdrant_http_similarity = QdrantHTTPSimilaritySearch()

    def analyze(self, image_paths: list[str], case_id: str) -> AnalyzerResult:
        if not image_paths:
            return AnalyzerResult(score=0.0, confidence=0.0, debug={"reason": "no_images"})

        scores: list[float] = []
        confidences: list[float] = []
        evidence: list[EvidenceItem] = []
        debug_items: list[dict[str, Any]] = []
        llm_success_count = 0
        llm_error_messages: list[str] = []

        for idx, path in enumerate(image_paths):
            started = time.perf_counter()
            img = Image.open(path).convert("RGB")
            heuristic_signals = self._heuristic_signals(img)
            heuristic_score = heuristic_signals["anomaly_score"]
            emb = self.embedder.embed_image(img)

            point_id = abs(hash(f"{case_id}:{idx}:{path}")) % (10**9)
            current_artifact_id = f"{case_id}:image:{idx}"
            self.qdrant.upsert_vector(
                IMAGE_EMBEDDINGS_COLLECTION,
                point_id=point_id,
                vector=emb,
                payload={
                    "case_id": case_id,
                    "artifact_id": current_artifact_id,
                    "modality": "image",
                    "label": "unknown",
                    "path": path,
                    "model_name": f"image-forensics-v2+{settings.ollama_vision_model}",
                    "confidence": round(0.45 + 0.5 * heuristic_score, 4),
                },
            )
            similar = self.qdrant.search(IMAGE_EMBEDDINGS_COLLECTION, query_vector=emb, limit=3)
            http_similar = self._search_http_similar(
                query_vector=emb,
                case_id=case_id,
                artifact_id=current_artifact_id,
            )

            similarity_top = float(similar[0]["similarity"]) if similar else 0.0
            retrieval_anomaly = clamp01(1.0 - similarity_top)
            llm_assessment = self._normalize_vision_assessment(self._vision_assessment(path))

            if llm_assessment["status"] == "ok":
                llm_success_count += 1
            else:
                llm_error_messages.append(str(llm_assessment.get("error", "vision_unavailable")))

            llm_ai_prob = float(llm_assessment.get("ai_generated_probability", 0.0))
            llm_manip_prob = float(llm_assessment.get("manipulation_probability", 0.0))
            llm_auth_prob = float(llm_assessment.get("authenticity_probability", 0.0))
            llm_conf = float(llm_assessment.get("confidence", 0.0))

            llm_suspicious = clamp01(0.6 * llm_ai_prob + 0.4 * llm_manip_prob)
            llm_bias_correction = clamp01(1.0 - llm_auth_prob)
            llm_signal = clamp01(0.8 * llm_suspicious + 0.2 * llm_bias_correction)

            if llm_assessment["status"] == "ok":
                score = clamp01(
                    0.62 * llm_signal
                    + 0.23 * heuristic_score
                    + 0.15 * retrieval_anomaly
                )
                confidence = clamp01(0.7 * llm_conf + 0.2 * heuristic_signals["confidence"] + 0.1 * (1.0 - retrieval_anomaly * 0.5))
            else:
                score = clamp01(0.75 * heuristic_score + 0.25 * retrieval_anomaly)
                confidence = clamp01(0.25 + 0.45 * heuristic_signals["confidence"])

            primary_reason = self._reason_for(score, llm_assessment, heuristic_signals)
            if score >= 0.45 and confidence >= 0.5:
                evidence.append(
                    EvidenceItem(
                        type="image",
                        reason=primary_reason,
                        confidence=confidence,
                        artifact_id=f"{case_id}:image:{idx}",
                        debug={
                            "llm_verdict": llm_assessment.get("verdict", "unknown"),
                            "llm_reason": llm_assessment.get("rationale", ""),
                            "llm_explanation": llm_assessment.get("final_explanation", ""),
                            "ai_indicators": llm_assessment.get("ai_indicators", []),
                            "counter_indicators": llm_assessment.get("counter_indicators", []),
                            "suspicious_regions": llm_assessment.get("suspicious_regions", []),
                            "heuristic_signals": heuristic_signals,
                            "http_qdrant_similarity": http_similar,
                        },
                    )
                )

            if (
                http_similar
                and float(http_similar.get("similarity", 0.0)) >= settings.qdrant_http_similarity_threshold
            ):
                evidence.append(
                    EvidenceItem(
                        type="image_similarity",
                        reason=str(http_similar.get("why_similar", "High similarity image match from Qdrant HTTP search.")),
                        confidence=clamp01(float(http_similar.get("similarity", 0.0))),
                        artifact_id=str(http_similar.get("artifact_id", "")) or None,
                        debug={
                            "source": "qdrant_http_search",
                            "matched_case_id": http_similar.get("case_id"),
                            "match_payload": http_similar.get("payload", {}),
                        },
                    )
                )

            debug_items.append(
                {
                    "path": path,
                    "runtime_ms": round((time.perf_counter() - started) * 1000, 2),
                    "score": score,
                    "confidence": confidence,
                    "similar_top": similarity_top,
                    "retrieval_anomaly": retrieval_anomaly,
                    "heuristic": heuristic_signals,
                    "llm": llm_assessment,
                    "qdrant_http_similarity": http_similar,
                }
            )
            scores.append(score)
            confidences.append(confidence)

        final_score = float(np.mean(scores)) if scores else 0.0
        confidence = float(np.mean(confidences)) if confidences else 0.0

        if llm_success_count == len(image_paths):
            ai_feature_status = "ok"
        elif llm_success_count > 0:
            ai_feature_status = "partial"
        else:
            ai_feature_status = "unavailable"

        return AnalyzerResult(
            score=final_score,
            confidence=confidence,
            evidence=evidence,
            debug={
                "ai_feature_status": ai_feature_status,
                "llm_used": llm_success_count > 0,
                "llm_success_count": llm_success_count,
                "errors": llm_error_messages,
                "items": debug_items,
            },
        )

    def _search_http_similar(
        self,
        query_vector: list[float],
        case_id: str,
        artifact_id: str,
    ) -> dict[str, Any] | None:
        try:
            return self.qdrant_http_similarity.search_similar_image(
                IMAGE_EMBEDDINGS_COLLECTION,
                query_vector,
                limit=6,
                exclude_case_id=case_id,
                exclude_artifact_id=artifact_id,
            )
        except Exception as exc:
            return {
                "error": str(exc),
                "source": "qdrant_http_search",
            }

    def _heuristic_signals(self, image: Image.Image) -> dict[str, float]:
        gray = np.array(image.convert("L").resize((192, 192)), dtype=np.float32)

        fft = np.fft.fftshift(np.fft.fft2(gray))
        mag = np.abs(fft)
        h, w = mag.shape
        cy, cx = h // 2, w // 2
        y, x = np.ogrid[:h, :w]

        low_mask = ((y - cy) ** 2 + (x - cx) ** 2) <= (min(h, w) // 6) ** 2
        high_mask = ((y - cy) ** 2 + (x - cx) ** 2) >= (min(h, w) // 3) ** 2
        low_ratio = float(mag[low_mask].sum() / (mag.sum() + 1e-9))
        high_ratio = float(mag[high_mask].sum() / (mag.sum() + 1e-9))

        ela_score = self._ela_score(image)
        blockiness = self._blockiness_score(gray)

        anomaly = clamp01(
            0.42 * clamp01(low_ratio * 1.45)
            + 0.28 * clamp01(high_ratio * 2.6)
            + 0.2 * ela_score
            + 0.1 * blockiness
        )
        confidence = clamp01(0.35 + 0.55 * max(ela_score, high_ratio * 2.2, blockiness))
        return {
            "anomaly_score": anomaly,
            "confidence": confidence,
            "fft_low_ratio": low_ratio,
            "fft_high_ratio": high_ratio,
            "ela_score": ela_score,
            "blockiness": blockiness,
        }

    def _ela_score(self, image: Image.Image) -> float:
        import io

        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=90)
        buffer.seek(0)
        recompressed = Image.open(buffer).convert("RGB")

        base_arr = np.array(image.convert("RGB"), dtype=np.float32)
        recompressed_arr = np.array(recompressed, dtype=np.float32)
        diff = np.abs(base_arr - recompressed_arr)
        mean_diff = float(diff.mean() / 255.0)
        p95 = float(np.percentile(diff, 95) / 255.0)
        return clamp01(0.55 * mean_diff + 0.45 * p95)

    def _blockiness_score(self, gray: np.ndarray) -> float:
        if gray.shape[0] < 16 or gray.shape[1] < 16:
            return 0.0
        if gray.shape[1] > 8:
            vertical_a = gray[:, 8::8]
            vertical_b = gray[:, 7::8][:, : vertical_a.shape[1]]
            vertical = float(np.abs(vertical_a - vertical_b).mean())
        else:
            vertical = 0.0

        if gray.shape[0] > 8:
            horizontal_a = gray[8::8, :]
            horizontal_b = gray[7::8, :][: horizontal_a.shape[0], :]
            horizontal = float(np.abs(horizontal_a - horizontal_b).mean())
        else:
            horizontal = 0.0

        local = np.abs(np.diff(gray, axis=0)).mean() + np.abs(np.diff(gray, axis=1)).mean() + 1e-9
        ratio = float((vertical + horizontal) / local)
        return clamp01(ratio * 0.5)

    def _vision_assessment(self, image_path: str) -> dict[str, Any]:
        started = time.perf_counter()
        if not self.llm_client.is_configured() or not settings.ollama_vision_model:
            return {
                "status": "unavailable",
                "error": "ollama_vision_not_configured",
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            }

        try:
            image_b64 = base64.b64encode(Path(image_path).read_bytes()).decode("utf-8")
            response = self.llm_client.chat_json(
                messages=[
                    LLMMessage(
                        role="system",
                        content=(
                            "You are an image forensics model focused on AI-generated image detection first."
                            " Treat digital artwork, CGI renders, synthetic composites, and model-generated visuals"
                            " as AI-generated/synthetic content unless strong evidence says camera-authentic."
                            " Also analyze signs of splicing, inpainting, relighting inconsistency, texture repetition,"
                            " edge artifacts, and compression anomalies."
                            " Return strict JSON only."
                        ),
                    ),
                    LLMMessage(
                        role="user",
                        content=(
                            "Return JSON with keys: ai_generated_probability, manipulation_probability,"
                            " authenticity_probability, confidence, verdict, rationale, final_explanation,"
                            " ai_indicators, counter_indicators, suspicious_regions."
                            " ai_indicators and counter_indicators must be string arrays."
                            " suspicious_regions must be an array of objects with keys x,y,width,height,reason"
                            " normalized 0-1 if any region exists."
                        ),
                        images=[image_b64],
                    ),
                ],
                temperature=0.0,
                model_override=settings.ollama_vision_model,
            )
            return {
                "status": "ok",
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                "ai_generated_probability": clamp01(float(response.get("ai_generated_probability", 0.0))),
                "manipulation_probability": clamp01(float(response.get("manipulation_probability", 0.0))),
                "authenticity_probability": clamp01(float(response.get("authenticity_probability", 0.0))),
                "confidence": clamp01(float(response.get("confidence", 0.0))),
                "verdict": str(response.get("verdict", "unknown")),
                "rationale": str(response.get("rationale", "")),
                "final_explanation": str(response.get("final_explanation", "")),
                "ai_indicators": response.get("ai_indicators", []) if isinstance(response.get("ai_indicators", []), list) else [],
                "counter_indicators": response.get("counter_indicators", []) if isinstance(response.get("counter_indicators", []), list) else [],
                "suspicious_regions": response.get("suspicious_regions", [])
                if isinstance(response.get("suspicious_regions", []), list)
                else [],
            }
        except Exception as exc:
            return {
                "status": "unavailable",
                "error": str(exc),
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            }

    def _normalize_vision_assessment(self, llm_assessment: dict[str, Any]) -> dict[str, Any]:
        if llm_assessment.get("status") != "ok":
            return llm_assessment

        verdict = str(llm_assessment.get("verdict", "")).lower()
        rationale = str(llm_assessment.get("rationale", "")).lower()

        ai_prob = clamp01(float(llm_assessment.get("ai_generated_probability", 0.0)))
        manip_prob = clamp01(float(llm_assessment.get("manipulation_probability", 0.0)))
        auth_prob = clamp01(float(llm_assessment.get("authenticity_probability", 0.0)))

        synthetic_markers = (
            "ai", "generated", "synthetic", "digital artwork", "illustration", "render", "composite", "cgi"
        )
        manipulation_markers = (
            "manipulat", "splic", "inpaint", "tamper", "edited", "altered"
        )

        mentions_synthetic = any(token in verdict or token in rationale for token in synthetic_markers)
        mentions_manip = any(token in verdict or token in rationale for token in manipulation_markers)

        if mentions_synthetic:
            ai_prob = max(ai_prob, 0.7)
            auth_prob = min(auth_prob, 0.3)
            if "authentic" in verdict:
                llm_assessment["verdict"] = "inconclusive_with_synthetic_indicators"

        if mentions_manip:
            manip_prob = max(manip_prob, 0.55)
            auth_prob = min(auth_prob, 0.45)

        llm_assessment["ai_generated_probability"] = ai_prob
        llm_assessment["manipulation_probability"] = manip_prob
        llm_assessment["authenticity_probability"] = auth_prob

        if not llm_assessment.get("final_explanation"):
            indicators = llm_assessment.get("ai_indicators", [])
            if isinstance(indicators, list) and indicators:
                llm_assessment["final_explanation"] = "AI indicators: " + ", ".join(str(item) for item in indicators[:4])
            else:
                llm_assessment["final_explanation"] = str(llm_assessment.get("rationale", ""))

        return llm_assessment

    def _reason_for(self, score: float, llm_assessment: dict[str, Any], heuristic: dict[str, float]) -> str:
        explanation = str(llm_assessment.get("final_explanation", "")).strip()
        if llm_assessment.get("status") == "ok" and explanation:
            return explanation
        if llm_assessment.get("status") == "ok" and llm_assessment.get("rationale"):
            return str(llm_assessment["rationale"])
        if heuristic.get("ela_score", 0.0) > 0.45:
            return "High recompression residual inconsistency suggests synthesis or editing."
        if heuristic.get("fft_high_ratio", 0.0) > 0.28:
            return "Abnormal high-frequency distribution suggests synthetic textures."
        if score > 0.65:
            return "Composite forensic signals indicate likely manipulation or generation."
        return "Moderate structural anomaly score from image forensics."
