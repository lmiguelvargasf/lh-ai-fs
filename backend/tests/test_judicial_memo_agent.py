from __future__ import annotations

import agents.judicial_memo_agent as memo_module
from agents.judicial_memo_agent import JudicialMemoAgent
from schemas import Finding, TextSpan


def _sample_finding(find_id: str, severity: str, confidence: float, kind: str, status: str, flag: bool) -> Finding:
    return Finding(
        id=find_id,
        kind=kind,
        severity=severity,
        raw_confidence=confidence,
        confidence=confidence,
        confidence_reason="test",
        status=status,
        supports_flag=flag,
        reference_id=find_id.replace("finding_", ""),
        message="test finding",
        evidence_spans=[TextSpan(document_id="motion_for_summary_judgment", start=0, end=10, excerpt="test")],
    )


def test_judicial_memo_template_fallback(monkeypatch) -> None:
    monkeypatch.setattr(memo_module, "is_llm_configured", lambda: False)

    agent = JudicialMemoAgent()
    memo = agent.run(
        [
            _sample_finding("finding_1", "high", 0.91, "cross_document_consistency", "contradicted", True),
            _sample_finding("finding_2", "medium", 0.77, "quote_accuracy", "material_difference", True),
        ]
    )

    assert memo.text
    assert memo.generation_mode == "template"
    assert memo.supporting_finding_ids


def test_judicial_memo_llm_path(monkeypatch) -> None:
    monkeypatch.setattr(memo_module, "is_llm_configured", lambda: True)
    monkeypatch.setattr(
        memo_module,
        "call_llm_json",
        lambda _messages: {
            "memo_text": "This is a one paragraph memo for judicial review based on top findings.",
            "uncertainty_note": "LLM synthesis used.",
        },
    )

    agent = JudicialMemoAgent()
    memo = agent.run(
        [
            _sample_finding("finding_1", "high", 0.95, "citation_support", "does_not_support", True),
            _sample_finding("finding_2", "medium", 0.80, "cross_document_consistency", "contradicted", True),
        ]
    )

    assert memo.generation_mode == "llm"
    assert memo.text.startswith("This is a one paragraph memo")
    assert set(memo.supporting_finding_ids).issubset({"finding_1", "finding_2"})
