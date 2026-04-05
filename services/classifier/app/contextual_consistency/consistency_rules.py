from __future__ import annotations

import re


class ConsistencyRules:
    def run(self, claim_text: str, evidence_summary: dict[str, object], references_similarity: float) -> list[dict[str, str]]:
        text = claim_text.lower()
        hits: list[dict[str, str]] = []

        if "today" in text and references_similarity > 0.90:
            hits.append(
                {
                    "rule_id": "time_reuse_001",
                    "severity": "high",
                    "reason": "Claim says today, but high-similarity references suggest prior usage.",
                }
            )

        place_claims = re.findall(r"\b(?:in|at)\s+([a-zA-Z]+)\b", text)
        summary_text = " ".join(
            [
                str(evidence_summary.get("text", "")),
                " ".join([str(x) for x in evidence_summary.get("ocr_text", [])]),
                " ".join([str(x) for x in evidence_summary.get("transcripts", [])]),
            ]
        ).lower()

        for place in place_claims[:3]:
            if place and place.lower() not in summary_text and len(place) > 3:
                hits.append(
                    {
                        "rule_id": "location_mismatch_001",
                        "severity": "medium",
                        "reason": f"Claimed location '{place}' not supported by extracted evidence.",
                    }
                )
                break

        if any(k in text for k in ["breaking", "live", "just happened"]) and references_similarity > 0.85:
            hits.append(
                {
                    "rule_id": "breaking_old_001",
                    "severity": "high",
                    "reason": "Breaking-news framing conflicts with near-duplicate prior references.",
                }
            )

        return hits
