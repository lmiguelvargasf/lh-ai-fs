from __future__ import annotations

import json
from pathlib import Path

from analysis_service import analyze_documents, load_documents
from schemas import AnalyzeRequest


def test_tier1_pipeline_returns_structured_report() -> None:
    fixture_path = (
        Path(__file__).resolve().parents[1]
        / "evals"
        / "fixtures"
        / "tier1_authority_overrides.json"
    )
    overrides = json.loads(fixture_path.read_text())

    report = analyze_documents(
        AnalyzeRequest(mode="tier1", use_web_retrieval=False),
        documents=load_documents(),
        authority_overrides=overrides,
    )

    assert report.mode == "tier1"
    assert report.summary.citations_extracted > 0
    assert isinstance(report.citation_findings, list)
    assert isinstance(report.quote_findings, list)
    assert report.status in {"complete", "partial"}
