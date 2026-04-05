from __future__ import annotations

from app.contextual_consistency.claim_parser import ClaimParser


def test_claim_parser_extracts_basic_fields():
    parser = ClaimParser()
    claim = parser.parse("This happened today in Paris during a protest")

    assert "today" in [d.lower() for d in claim.dates]
    assert "Paris" in claim.places
    assert "protest" in [e.lower() for e in claim.events]
