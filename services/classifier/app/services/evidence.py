from __future__ import annotations

from typing import Any

from app.shared.schemas import EvidenceItem


class EvidenceBuilder:
    def build_debug_payload(
        self,
        analyzer_debug: dict[str, dict[str, Any]],
        errors: list[str],
    ) -> dict[str, Any]:
        return {
            "analyzers": analyzer_debug,
            "errors": errors,
        }

    def dedupe(self, evidence: list[EvidenceItem]) -> list[EvidenceItem]:
        seen: set[tuple[str, str, str | None, int | None]] = set()
        out: list[EvidenceItem] = []
        for item in evidence:
            key = (item.type, item.reason, item.span, item.timestamp_ms)
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out
