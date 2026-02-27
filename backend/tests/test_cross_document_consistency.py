from __future__ import annotations

from agents.cross_document_consistency_agent import CrossDocumentConsistencyAgent
from agents.document_ingest_agent import DocumentIngestAgent
from agents.fact_claim_extraction_agent import FactClaimExtractionAgent
from analysis_service import load_documents


def test_cross_document_agent_flags_known_contradictions() -> None:
    bundle = DocumentIngestAgent().run(load_documents())
    claims = FactClaimExtractionAgent(use_llm=False).run(bundle)
    assessments = CrossDocumentConsistencyAgent().run(claims, bundle)
    by_claim_id = {assessment.claim_id: assessment for assessment in assessments}

    date_claim = next(claim for claim in claims if "March 14, 2021" in claim.claim_text)
    ppe_claim = next(
        claim for claim in claims if "not wearing required personal protective equipment" in claim.claim_text
    )
    osha_claim = next(
        claim for claim in claims if "passed all OSHA inspections conducted at the site" in claim.claim_text
    )

    assert by_claim_id[date_claim.id].label == "contradicted"
    assert by_claim_id[ppe_claim.id].label == "contradicted"
    assert by_claim_id[osha_claim.id].label == "could_not_verify"

    for claim in [date_claim, ppe_claim]:
        assessment = by_claim_id[claim.id]
        assert assessment.evidence_spans
        assert any(span.document_id != "motion_for_summary_judgment" for span in assessment.evidence_spans)
