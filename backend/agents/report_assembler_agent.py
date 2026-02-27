from __future__ import annotations

from schemas import (
    AuthorityRecord,
    CitationFinding,
    CitationUnit,
    ConfidenceCalibration,
    CrossDocumentAssessment,
    CrossDocumentFinding,
    FactClaim,
    Finding,
    JudicialMemo,
    PipelineError,
    QuoteAssessment,
    QuoteFinding,
    QuoteUnit,
    ReportSummary,
    SupportAssessment,
    VerificationReport,
)


class ReportAssemblerAgent:
    """Build final structured verification report."""

    def run(
        self,
        *,
        run_id: str,
        citations: list[CitationUnit],
        quotes: list[QuoteUnit],
        authorities: list[AuthorityRecord],
        support_assessments: list[SupportAssessment],
        quote_assessments: list[QuoteAssessment],
        fact_claims: list[FactClaim],
        cross_doc_assessments: list[CrossDocumentAssessment],
        calibrations: list[ConfidenceCalibration],
        judicial_memo: JudicialMemo,
        errors: list[PipelineError],
        timings_ms: dict[str, int],
    ) -> VerificationReport:
        authority_by_citation = {record.citation_id: record for record in authorities}
        support_by_citation = {assessment.citation_id: assessment for assessment in support_assessments}
        quote_by_id = {quote.id: quote for quote in quotes}
        quote_assessment_by_id = {assessment.quote_id: assessment for assessment in quote_assessments}
        claim_by_id = {claim.id: claim for claim in fact_claims}
        calibration_map = {(item.finding_kind, item.reference_id): item for item in calibrations}

        citation_findings: list[CitationFinding] = []
        findings: list[Finding] = []

        for citation in citations:
            support = support_by_citation.get(citation.id)
            authority = authority_by_citation.get(citation.id)
            if support is None:
                continue

            flagged = support.label != "supports"
            severity = self._severity_for_support(support.label)
            raw_conf, calibrated_conf, conf_reason = self._confidence_values(
                calibration_map=calibration_map,
                kind="citation_support",
                reference_id=citation.id,
                fallback_raw=support.confidence,
            )

            citation_finding = CitationFinding(
                id=f"finding_{citation.id}",
                citation_id=citation.id,
                raw_citation=citation.raw_citation,
                proposition_text=citation.proposition_text,
                support_label=support.label,
                raw_confidence=raw_conf,
                confidence=calibrated_conf,
                confidence_reason=conf_reason,
                reason=support.reason,
                uncertainty_reason=support.uncertainty_reason,
                retrieval_status=(
                    authority.retrieval_status if authority else "error"
                ),
                source_url=authority.source_url if authority else None,
                motion_span=citation.motion_span,
                evidence_spans=support.evidence_spans,
                flagged=flagged,
            )
            citation_findings.append(citation_finding)

            findings.append(
                Finding(
                    id=citation_finding.id,
                    kind="citation_support",
                    severity=severity,
                    raw_confidence=raw_conf,
                    confidence=calibrated_conf,
                    confidence_reason=conf_reason,
                    status=support.label,
                    supports_flag=flagged,
                    reference_id=citation.id,
                    message=support.reason,
                    evidence_spans=[citation.motion_span, *support.evidence_spans],
                )
            )

        quote_findings: list[QuoteFinding] = []
        for quote_id, assessment in quote_assessment_by_id.items():
            quote = quote_by_id.get(quote_id)
            if quote is None:
                continue

            flagged = assessment.label != "exact"
            severity = self._severity_for_quote(assessment.label)
            raw_conf, calibrated_conf, conf_reason = self._confidence_values(
                calibration_map=calibration_map,
                kind="quote_accuracy",
                reference_id=quote.id,
                fallback_raw=assessment.confidence,
            )

            quote_finding = QuoteFinding(
                id=f"finding_{quote.id}",
                quote_id=quote.id,
                quote_text=quote.quote_text,
                citation_id=quote.citation_id,
                quote_label=assessment.label,
                raw_confidence=raw_conf,
                confidence=calibrated_conf,
                confidence_reason=conf_reason,
                reason=assessment.reason,
                uncertainty_reason=assessment.uncertainty_reason,
                motion_span=quote.motion_span,
                evidence_spans=assessment.evidence_spans,
                flagged=flagged,
            )
            quote_findings.append(quote_finding)

            findings.append(
                Finding(
                    id=quote_finding.id,
                    kind="quote_accuracy",
                    severity=severity,
                    raw_confidence=raw_conf,
                    confidence=calibrated_conf,
                    confidence_reason=conf_reason,
                    status=assessment.label,
                    supports_flag=flagged,
                    reference_id=quote.id,
                    message=assessment.reason,
                    evidence_spans=[quote.motion_span, *assessment.evidence_spans],
                )
            )

        cross_document_findings: list[CrossDocumentFinding] = []
        for assessment in cross_doc_assessments:
            claim = claim_by_id.get(assessment.claim_id)
            if claim is None:
                continue

            flagged = assessment.label == "contradicted"
            severity = self._severity_for_cross_doc(assessment.label)
            raw_conf, calibrated_conf, conf_reason = self._confidence_values(
                calibration_map=calibration_map,
                kind="cross_document_consistency",
                reference_id=claim.id,
                fallback_raw=assessment.confidence,
            )

            cross_finding = CrossDocumentFinding(
                id=f"finding_{claim.id}",
                claim_id=claim.id,
                claim_text=claim.claim_text,
                label=assessment.label,
                raw_confidence=raw_conf,
                confidence=calibrated_conf,
                confidence_reason=conf_reason,
                reason=assessment.reason,
                uncertainty_reason=assessment.uncertainty_reason,
                motion_span=claim.motion_span,
                evidence_spans=assessment.evidence_spans,
                flagged=flagged,
            )
            cross_document_findings.append(cross_finding)

            findings.append(
                Finding(
                    id=cross_finding.id,
                    kind="cross_document_consistency",
                    severity=severity,
                    raw_confidence=raw_conf,
                    confidence=calibrated_conf,
                    confidence_reason=conf_reason,
                    status=assessment.label,
                    supports_flag=flagged,
                    reference_id=claim.id,
                    message=assessment.reason,
                    evidence_spans=[claim.motion_span, *assessment.evidence_spans],
                )
            )

        flags_total = sum(1 for finding in findings if finding.supports_flag)
        cross_doc_flags_total = sum(1 for finding in cross_document_findings if finding.flagged)
        status: str = "complete"
        if errors:
            status = "partial"
        if not citation_findings and not quote_findings and not cross_document_findings:
            status = "failed"

        summary = ReportSummary(
            citations_extracted=len(citations),
            quotes_checked=len(quotes),
            flags_total=flags_total,
            fact_claims_checked=len(fact_claims),
            cross_doc_flags_total=cross_doc_flags_total,
        )

        return VerificationReport(
            mode="final",
            run_id=run_id,
            status=status,
            summary=summary,
            citation_findings=citation_findings,
            quote_findings=quote_findings,
            cross_document_findings=cross_document_findings,
            findings=findings,
            judicial_memo=judicial_memo,
            errors=errors,
            timings_ms=timings_ms,
        )

    @staticmethod
    def _confidence_values(
        *,
        calibration_map: dict[tuple[str, str], ConfidenceCalibration],
        kind: str,
        reference_id: str,
        fallback_raw: float,
    ) -> tuple[float, float, str]:
        calibration = calibration_map.get((kind, reference_id))
        if calibration is None:
            return (
                fallback_raw,
                fallback_raw,
                "No calibration override found; using raw confidence.",
            )
        return (
            calibration.raw_confidence,
            calibration.calibrated_confidence,
            calibration.confidence_reason,
        )

    @staticmethod
    def _severity_for_support(label: str) -> str:
        if label == "does_not_support":
            return "high"
        if label in {"partially_supports", "could_not_verify"}:
            return "medium"
        return "low"

    @staticmethod
    def _severity_for_quote(label: str) -> str:
        if label == "material_difference":
            return "high"
        if label in {"minor_difference", "could_not_verify"}:
            return "medium"
        return "low"

    @staticmethod
    def _severity_for_cross_doc(label: str) -> str:
        if label == "contradicted":
            return "high"
        if label == "partially_supported":
            return "medium"
        return "low"
