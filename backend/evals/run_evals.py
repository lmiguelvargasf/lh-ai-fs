from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from analysis_service import analyze_documents, load_documents  # noqa: E402
from schemas import AnalyzeRequest, EvalMetricSummary, EvalResult  # noqa: E402


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 1.0
    return numerator / denominator


def _score_flags(
    expectations: list[dict[str, Any]],
    predicted_lookup: dict[str, bool],
    key_field: str,
) -> tuple[int, int, int, list[dict[str, Any]]]:
    tp = fp = fn = 0
    details: list[dict[str, Any]] = []

    for expected in expectations:
        key = expected[key_field]
        should_flag = bool(expected["should_flag"])
        predicted_flag = bool(predicted_lookup.get(key, False))

        if should_flag and predicted_flag:
            tp += 1
            outcome = "tp"
        elif not should_flag and predicted_flag:
            fp += 1
            outcome = "fp"
        elif should_flag and not predicted_flag:
            fn += 1
            outcome = "fn"
        else:
            outcome = "tn"

        details.append(
            {
                "key": key,
                "should_flag": should_flag,
                "predicted_flag": predicted_flag,
                "outcome": outcome,
                "note": expected.get("note"),
            }
        )

    return tp, fp, fn, details


def _build_quote_lookup(quote_findings: list[dict[str, Any]]) -> dict[str, bool]:
    lookup: dict[str, bool] = {}
    for finding in quote_findings:
        text = finding.get("quote_text", "")
        flagged = bool(finding.get("flagged"))
        lookup[text] = flagged
    return lookup


def _lookup_quote_flag(quote_lookup: dict[str, bool], needle: str) -> bool:
    for quote_text, flagged in quote_lookup.items():
        if needle in quote_text or quote_text in needle:
            return flagged
    return False


def _build_cross_doc_lookup(cross_findings: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for finding in cross_findings:
        claim_text = str(finding.get("claim_text", ""))
        if claim_text:
            lookup[claim_text] = finding
    return lookup


def _lookup_cross_doc_finding(
    cross_lookup: dict[str, dict[str, Any]],
    needle: str,
) -> dict[str, Any] | None:
    for claim_text, finding in cross_lookup.items():
        if needle in claim_text or claim_text in needle:
            return finding
    return None


def _hallucination_rate(report: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
    findings = report.get("findings", [])
    citation_ids = {item["citation_id"] for item in report.get("citation_findings", [])}
    quote_ids = {item["quote_id"] for item in report.get("quote_findings", [])}
    cross_ids = {item["claim_id"] for item in report.get("cross_document_findings", [])}

    invalid: list[dict[str, Any]] = []
    for finding in findings:
        reference_id = finding.get("reference_id")
        kind = finding.get("kind")

        if kind == "citation_support" and reference_id not in citation_ids:
            invalid.append({"id": finding.get("id"), "reason": "invalid citation reference"})
            continue
        if kind == "quote_accuracy" and reference_id not in quote_ids:
            invalid.append({"id": finding.get("id"), "reason": "invalid quote reference"})
            continue
        if kind == "cross_document_consistency" and reference_id not in cross_ids:
            invalid.append({"id": finding.get("id"), "reason": "invalid cross-document claim reference"})
            continue

        spans = finding.get("evidence_spans", [])
        if not spans:
            invalid.append({"id": finding.get("id"), "reason": "missing evidence spans"})
            continue

        has_motion_span = any(span.get("document_id") == "motion_for_summary_judgment" for span in spans)
        if not has_motion_span:
            invalid.append({"id": finding.get("id"), "reason": "missing motion anchor"})

        if kind == "cross_document_consistency" and finding.get("status") != "could_not_verify":
            has_external_span = any(
                span.get("document_id") != "motion_for_summary_judgment" for span in spans
            )
            if not has_external_span:
                invalid.append(
                    {
                        "id": finding.get("id"),
                        "reason": "cross-document finding missing external evidence anchor",
                    }
                )

    rate = _safe_div(len(invalid), len(findings) or 1)
    return rate, invalid


def _task_metrics(tp: int, fp: int, fn: int) -> dict[str, Any]:
    return {
        "precision": round(_safe_div(tp, tp + fp), 4),
        "recall": round(_safe_div(tp, tp + fn), 4),
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
    }


def run() -> EvalResult:
    gold = _load_json(FIXTURES_DIR / "tier1_gold.json")
    cross_gold = _load_json(FIXTURES_DIR / "tier2_cross_doc_gold.json")
    overrides = _load_json(FIXTURES_DIR / "tier1_authority_overrides.json")

    report_model = analyze_documents(
        AnalyzeRequest(mode="tier2", use_web_retrieval=False),
        documents=load_documents(),
        authority_overrides=overrides,
    )
    report = report_model.model_dump()

    citation_lookup = {
        finding["raw_citation"]: bool(finding.get("flagged"))
        for finding in report.get("citation_findings", [])
    }
    citation_tp, citation_fp, citation_fn, citation_details = _score_flags(
        gold["citation_expectations"],
        citation_lookup,
        key_field="raw_citation",
    )

    quote_lookup = _build_quote_lookup(report.get("quote_findings", []))
    quote_expectations = []
    for expected in gold["quote_expectations"]:
        quote_expectations.append(
            {
                "quote_contains": expected["quote_contains"],
                "should_flag": expected["should_flag"],
                "note": expected.get("note"),
            }
        )

    quote_tp = quote_fp = quote_fn = 0
    quote_details: list[dict[str, Any]] = []
    for expected in quote_expectations:
        key = expected["quote_contains"]
        should_flag = bool(expected["should_flag"])
        predicted_flag = _lookup_quote_flag(quote_lookup, key)

        if should_flag and predicted_flag:
            quote_tp += 1
            outcome = "tp"
        elif not should_flag and predicted_flag:
            quote_fp += 1
            outcome = "fp"
        elif should_flag and not predicted_flag:
            quote_fn += 1
            outcome = "fn"
        else:
            outcome = "tn"

        quote_details.append(
            {
                "key": key,
                "should_flag": should_flag,
                "predicted_flag": predicted_flag,
                "outcome": outcome,
                "note": expected.get("note"),
            }
        )

    cross_lookup = _build_cross_doc_lookup(report.get("cross_document_findings", []))
    cross_tp = cross_fp = cross_fn = 0
    cross_details: list[dict[str, Any]] = []
    cross_label_mismatches: list[dict[str, Any]] = []
    for expected in cross_gold["cross_doc_expectations"]:
        key = expected["claim_contains"]
        should_flag = bool(expected["should_flag"])
        expected_label = expected["expected_label"]
        finding = _lookup_cross_doc_finding(cross_lookup, key)

        predicted_flag = bool(finding and finding.get("flagged"))
        predicted_label = finding.get("label") if finding else "missing"

        if should_flag and predicted_flag:
            cross_tp += 1
            outcome = "tp"
        elif not should_flag and predicted_flag:
            cross_fp += 1
            outcome = "fp"
        elif should_flag and not predicted_flag:
            cross_fn += 1
            outcome = "fn"
        else:
            outcome = "tn"

        if finding and predicted_label != expected_label:
            cross_label_mismatches.append(
                {
                    "claim_contains": key,
                    "expected_label": expected_label,
                    "predicted_label": predicted_label,
                }
            )

        cross_details.append(
            {
                "key": key,
                "should_flag": should_flag,
                "predicted_flag": predicted_flag,
                "expected_label": expected_label,
                "predicted_label": predicted_label,
                "outcome": outcome,
                "note": expected.get("note"),
            }
        )

    tier1_tp = citation_tp + quote_tp
    tier1_fp = citation_fp + quote_fp
    tier1_fn = citation_fn + quote_fn

    total_tp = tier1_tp + cross_tp
    total_fp = tier1_fp + cross_fp
    total_fn = tier1_fn + cross_fn

    overall_precision = _safe_div(total_tp, total_tp + total_fp)
    overall_recall = _safe_div(total_tp, total_tp + total_fn)

    citation_quote_metrics = _task_metrics(tier1_tp, tier1_fp, tier1_fn)
    cross_metrics = _task_metrics(cross_tp, cross_fp, cross_fn)

    combined_precision = (citation_quote_metrics["precision"] + cross_metrics["precision"]) / 2
    combined_recall = (citation_quote_metrics["recall"] + cross_metrics["recall"]) / 2

    hallucination_rate, hallucination_details = _hallucination_rate(report)

    metrics = EvalMetricSummary(
        precision=round(overall_precision, 4),
        recall=round(overall_recall, 4),
        hallucination_rate=round(hallucination_rate, 4),
        true_positive=total_tp,
        false_positive=total_fp,
        false_negative=total_fn,
        task_breakdown={
            "citation_quote": citation_quote_metrics,
            "cross_document": cross_metrics,
        },
        combined={
            "macro_precision": round(combined_precision, 4),
            "macro_recall": round(combined_recall, 4),
        },
    )

    details = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "report_summary": report.get("summary"),
        "status": report.get("status"),
        "citation_scoring": {
            "tp": citation_tp,
            "fp": citation_fp,
            "fn": citation_fn,
            "details": citation_details,
        },
        "quote_scoring": {
            "tp": quote_tp,
            "fp": quote_fp,
            "fn": quote_fn,
            "details": quote_details,
        },
        "cross_document_scoring": {
            "tp": cross_tp,
            "fp": cross_fp,
            "fn": cross_fn,
            "details": cross_details,
            "label_mismatches": cross_label_mismatches,
        },
        "hallucination_checks": {
            "count": len(hallucination_details),
            "details": hallucination_details,
        },
    }

    result = EvalResult(metrics=metrics, details=details)

    output_path = RESULTS_DIR / "latest.json"
    output_path.write_text(json.dumps(result.model_dump(), indent=2))

    print("Eval metrics")
    print(json.dumps(metrics.model_dump(), indent=2))
    print(f"Detailed results written to: {output_path}")

    return result


def main() -> int:
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
