from __future__ import annotations

from app.contextual_consistency.claim_parser import ClaimParser
from app.contextual_consistency.consistency_rules import ConsistencyRules
from app.contextual_consistency.entailment_scorer import EntailmentScorer
from app.contextual_consistency.evidence_extractor import EvidenceExtractor
from app.contextual_consistency.fusion import ContextFusion
from app.contextual_consistency.llm_judge import LLMJudge
from app.contextual_consistency.reference_retriever import ReferenceRetriever
from app.contextual_consistency.schemas import ContextAnalyzeResponse
from app.shared.schemas import NormalizedArtifacts


class ContextualConsistencyService:
    def __init__(
        self,
        claim_parser: ClaimParser,
        evidence_extractor: EvidenceExtractor,
        reference_retriever: ReferenceRetriever,
        rules: ConsistencyRules,
        entailment: EntailmentScorer,
        llm_judge: LLMJudge,
        fusion: ContextFusion,
    ) -> None:
        self.claim_parser = claim_parser
        self.evidence_extractor = evidence_extractor
        self.reference_retriever = reference_retriever
        self.rules = rules
        self.entailment = entailment
        self.llm_judge = llm_judge
        self.fusion = fusion

    def analyze(self, case_id: str, claim_text: str, artifacts: NormalizedArtifacts) -> ContextAnalyzeResponse:
        claim = self.claim_parser.parse(claim_text)
        evidence_summary = self.evidence_extractor.extract_summary(artifacts)
        references = self.reference_retriever.retrieve(claim_text)
        top_similarity = references[0].similarity if references else 0.0

        rules = self.rules.run(claim_text, evidence_summary, references_similarity=top_similarity)
        entailment = self.entailment.score(claim_text, evidence_summary_text=str(evidence_summary))
        llm = self.llm_judge.judge(claim_text, evidence_summary)

        consistency, confidence, verdict, signals, explanation = self.fusion.fuse(
            rules=rules,
            entailment=entailment,
            llm=llm,
            references_top_score=top_similarity,
        )

        suspicious = llm.get("suspicious_parts", []) if isinstance(llm, dict) else []
        if not isinstance(suspicious, list):
            suspicious = []

        return ContextAnalyzeResponse(
            case_id=case_id,
            consistency_score=consistency,
            confidence=confidence,
            verdict=verdict,
            signals=signals,
            suspicious_parts=[
                {"text": str(item.get("text", "")), "reason": str(item.get("reason", ""))}
                for item in suspicious[:8]
                if isinstance(item, dict)
            ],
            references=references,
            explanation=explanation,
            debug={
                "claim": claim.model_dump(),
                "entailment": entailment,
                "rules": rules,
                "llm": llm,
            },
        )
