from __future__ import annotations

from agents.confidence_calibration_agent import ConfidenceCalibrationAgent
from schemas import (
    AuthorityRecord,
    CrossDocumentAssessment,
    QuoteAssessment,
    QuoteUnit,
    SupportAssessment,
    TextSpan,
)


def test_confidence_calibration_penalties_and_bonuses() -> None:
    agent = ConfidenceCalibrationAgent()

    support_assessments = [
        SupportAssessment(
            citation_id="citation_001",
            label="could_not_verify",
            confidence=0.8,
            reason="No authority text",
            evidence_spans=[],
            uncertainty_reason="missing",
        )
    ]
    quote_assessments = [
        QuoteAssessment(
            quote_id="quote_001",
            label="minor_difference",
            confidence=0.7,
            reason="Minor mismatch",
            evidence_spans=[],
        )
    ]
    cross_doc_assessments = [
        CrossDocumentAssessment(
            claim_id="claim_001",
            label="contradicted",
            confidence=0.6,
            reason="Conflicting dates",
            evidence_spans=[
                TextSpan(document_id="police_report", start=0, end=20, excerpt="March 12, 2021"),
                TextSpan(document_id="witness_statement", start=10, end=35, excerpt="March 12, 2021"),
            ],
        )
    ]
    authorities = [
        AuthorityRecord(
            citation_id="citation_001",
            normalized_citation="Test v. Test",
            retrieval_status="disabled",
            error="disabled",
        )
    ]
    quotes = [
        QuoteUnit(
            id="quote_001",
            quote_text="test",
            citation_id="citation_001",
            proposition_text="test",
            motion_span=TextSpan(document_id="motion_for_summary_judgment", start=0, end=5, excerpt="test"),
        )
    ]

    calibrations = agent.run(
        support_assessments=support_assessments,
        quote_assessments=quote_assessments,
        cross_doc_assessments=cross_doc_assessments,
        authorities=authorities,
        quotes=quotes,
    )

    by_key = {(item.finding_kind, item.reference_id): item for item in calibrations}

    citation_cal = by_key[("citation_support", "citation_001")]
    assert citation_cal.calibrated_confidence < citation_cal.raw_confidence
    assert "could_not_verify" in citation_cal.confidence_reason

    quote_cal = by_key[("quote_accuracy", "quote_001")]
    assert quote_cal.calibrated_confidence < quote_cal.raw_confidence
    assert "weak_retrieval" in quote_cal.confidence_reason

    cross_cal = by_key[("cross_document_consistency", "claim_001")]
    assert cross_cal.calibrated_confidence > cross_cal.raw_confidence
    assert "+0.12 explicit_contradiction" in cross_cal.confidence_reason
    assert 0.05 <= cross_cal.calibrated_confidence <= 0.99
