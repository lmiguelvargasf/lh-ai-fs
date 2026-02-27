from __future__ import annotations

from agents.document_ingest_agent import DocumentIngestAgent
from agents.fact_claim_extraction_agent import FactClaimExtractionAgent
from analysis_service import load_documents


def test_extracts_core_fact_claims_from_motion() -> None:
    bundle = DocumentIngestAgent().run(load_documents())
    claims = FactClaimExtractionAgent(use_llm=False).run(bundle)

    claim_texts = [claim.claim_text for claim in claims]

    assert any("March 14, 2021" in text for text in claim_texts)
    assert any("not wearing required personal protective equipment" in text for text in claim_texts)
    assert any(claim.source_section == "statement_of_undisputed_material_facts" for claim in claims)
    assert all(claim.motion_span.document_id == "motion_for_summary_judgment" for claim in claims)
