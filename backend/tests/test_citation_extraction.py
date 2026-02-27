from __future__ import annotations

from agents.citation_extraction_agent import CitationExtractionAgent
from agents.document_ingest_agent import DocumentIngestAgent
from analysis_service import load_documents


def test_citation_and_quote_extraction_counts() -> None:
    bundle = DocumentIngestAgent().run(load_documents())
    extraction = CitationExtractionAgent().run(bundle)

    assert len(extraction.citations) == 10
    assert len(extraction.quotes) == 2


def test_citation_contains_privette() -> None:
    bundle = DocumentIngestAgent().run(load_documents())
    extraction = CitationExtractionAgent().run(bundle)

    raw_citations = {citation.raw_citation for citation in extraction.citations}
    assert "Privette v. Superior Court, 5 Cal.4th 689, 695 (1993)" in raw_citations
