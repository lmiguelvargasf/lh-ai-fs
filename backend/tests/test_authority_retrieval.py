from __future__ import annotations

from agents.authority_retrieval_agent import AuthorityRetrievalAgent
from agents.citation_extraction_agent import CitationExtractionAgent
from agents.document_ingest_agent import DocumentIngestAgent
from analysis_service import load_documents


def test_retrieval_disabled_returns_could_not_fetch_record() -> None:
    bundle = DocumentIngestAgent().run(load_documents())
    extraction = CitationExtractionAgent().run(bundle)

    agent = AuthorityRetrievalAgent()
    records = agent.run(extraction.citations[:1], use_web_retrieval=False)

    assert len(records) == 1
    assert records[0].retrieval_status in {"disabled", "found", "not_found", "error"}


def test_override_takes_precedence() -> None:
    bundle = DocumentIngestAgent().run(load_documents())
    extraction = CitationExtractionAgent().run(bundle)
    citation = extraction.citations[0]

    agent = AuthorityRetrievalAgent()
    records = agent.run(
        [citation],
        use_web_retrieval=False,
        authority_overrides={
            citation.normalized_citation: {
                "retrieval_status": "found",
                "source_url": "https://example.com/case",
                "authority_text": "Test authority text",
            }
        },
    )

    assert records[0].retrieval_status == "found"
    assert records[0].authority_text == "Test authority text"
