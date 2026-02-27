from __future__ import annotations

import json
from pathlib import Path

import agents.judicial_memo_agent as memo_module
from analysis_service import analyze_documents, load_documents
from schemas import AnalyzeRequest


def test_pipeline_returns_structured_report_with_memo_and_confidence() -> None:
    fixture_path = (
        Path(__file__).resolve().parents[1]
        / "evals"
        / "fixtures"
        / "authority_overrides.json"
    )
    overrides = json.loads(fixture_path.read_text())

    report = analyze_documents(
        AnalyzeRequest(use_web_retrieval=False),
        documents=load_documents(),
        authority_overrides=overrides,
    )

    assert report.mode == "final"
    assert report.summary.citations_extracted > 0
    assert report.summary.fact_claims_checked > 0
    assert isinstance(report.citation_findings, list)
    assert isinstance(report.quote_findings, list)
    assert isinstance(report.cross_document_findings, list)
    assert report.judicial_memo.text
    assert report.judicial_memo.generation_mode in {"llm", "template"}

    for finding in report.findings:
        assert 0.0 <= finding.raw_confidence <= 1.0
        assert 0.0 <= finding.confidence <= 1.0
        assert finding.confidence_reason

    assert report.status in {"complete", "partial"}


def test_pipeline_uses_memo_template_fallback_on_error(monkeypatch) -> None:
    fixture_path = (
        Path(__file__).resolve().parents[1]
        / "evals"
        / "fixtures"
        / "authority_overrides.json"
    )
    overrides = json.loads(fixture_path.read_text())

    def _raise_memo_error(_self, _findings):
        raise RuntimeError("forced memo failure")

    monkeypatch.setattr(memo_module.JudicialMemoAgent, "run", _raise_memo_error)

    report = analyze_documents(
        AnalyzeRequest(use_web_retrieval=False),
        documents=load_documents(),
        authority_overrides=overrides,
    )

    assert report.judicial_memo.generation_mode == "template"
    assert report.judicial_memo.text
    assert any(error.step == "judicial_memo" for error in report.errors)
