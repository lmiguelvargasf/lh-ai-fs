from __future__ import annotations

from schemas import (
    AuthorityRecord,
    ConfidenceCalibration,
    CrossDocumentAssessment,
    QuoteAssessment,
    QuoteUnit,
    SupportAssessment,
)


class ConfidenceCalibrationAgent:
    """Apply deterministic confidence calibration across finding categories."""

    def run(
        self,
        *,
        support_assessments: list[SupportAssessment],
        quote_assessments: list[QuoteAssessment],
        cross_doc_assessments: list[CrossDocumentAssessment],
        authorities: list[AuthorityRecord],
        quotes: list[QuoteUnit],
    ) -> list[ConfidenceCalibration]:
        calibrations: list[ConfidenceCalibration] = []
        authority_by_citation = {record.citation_id: record for record in authorities}
        quote_by_id = {quote.id: quote for quote in quotes}

        for assessment in support_assessments:
            authority = authority_by_citation.get(assessment.citation_id)
            status = authority.retrieval_status if authority else "error"
            calibrated, reason = self._calibrate(
                raw=assessment.confidence,
                status=assessment.label,
                evidence_spans=assessment.evidence_spans,
                retrieval_status=status,
                finding_kind="citation_support",
            )
            calibrations.append(
                ConfidenceCalibration(
                    finding_kind="citation_support",
                    reference_id=assessment.citation_id,
                    raw_confidence=assessment.confidence,
                    calibrated_confidence=calibrated,
                    confidence_reason=reason,
                )
            )

        for assessment in quote_assessments:
            quote = quote_by_id.get(assessment.quote_id)
            retrieval_status = "disabled"
            if quote and quote.citation_id and quote.citation_id in authority_by_citation:
                retrieval_status = authority_by_citation[quote.citation_id].retrieval_status

            calibrated, reason = self._calibrate(
                raw=assessment.confidence,
                status=assessment.label,
                evidence_spans=assessment.evidence_spans,
                retrieval_status=retrieval_status,
                finding_kind="quote_accuracy",
            )
            calibrations.append(
                ConfidenceCalibration(
                    finding_kind="quote_accuracy",
                    reference_id=assessment.quote_id,
                    raw_confidence=assessment.confidence,
                    calibrated_confidence=calibrated,
                    confidence_reason=reason,
                )
            )

        for assessment in cross_doc_assessments:
            calibrated, reason = self._calibrate(
                raw=assessment.confidence,
                status=assessment.label,
                evidence_spans=assessment.evidence_spans,
                retrieval_status="found",
                finding_kind="cross_document_consistency",
            )
            calibrations.append(
                ConfidenceCalibration(
                    finding_kind="cross_document_consistency",
                    reference_id=assessment.claim_id,
                    raw_confidence=assessment.confidence,
                    calibrated_confidence=calibrated,
                    confidence_reason=reason,
                )
            )

        return calibrations

    def _calibrate(
        self,
        *,
        raw: float,
        status: str,
        evidence_spans: list,
        retrieval_status: str,
        finding_kind: str,
    ) -> tuple[float, str]:
        score = raw
        reasons = [f"start={raw:.2f}"]

        if not evidence_spans:
            score -= 0.12
            reasons.append("-0.12 missing_evidence")

        if status == "could_not_verify":
            score -= 0.25
            reasons.append("-0.25 could_not_verify")

        if finding_kind in {"citation_support", "quote_accuracy"} and retrieval_status in {
            "not_found",
            "error",
            "disabled",
        }:
            score -= 0.18
            reasons.append(f"-0.18 weak_retrieval:{retrieval_status}")

        unique_docs = {span.document_id for span in evidence_spans}
        external_docs = {doc for doc in unique_docs if doc != "motion_for_summary_judgment"}

        if finding_kind == "cross_document_consistency" and status == "contradicted" and external_docs:
            score += 0.12
            reasons.append("+0.12 explicit_contradiction")

        if len(external_docs) >= 2:
            score += 0.08
            reasons.append("+0.08 multi_source_evidence")

        score = max(0.05, min(0.99, score))
        reasons.append(f"final={score:.2f}")
        return score, "; ".join(reasons)
