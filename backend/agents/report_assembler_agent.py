from __future__ import annotations

from schemas import (
    CitationFinding,
    CitationUnit,
    Finding,
    PipelineError,
    QuoteFinding,
    QuoteUnit,
    ReportSummary,
    SupportAssessment,
    VerificationReport,
    QuoteAssessment,
    AuthorityRecord,
)


class ReportAssemblerAgent:
    """Build final structured verification report."""

    def run(
        self,
        *,
        run_id: str,
        mode: str,
        citations: list[CitationUnit],
        quotes: list[QuoteUnit],
        authorities: list[AuthorityRecord],
        support_assessments: list[SupportAssessment],
        quote_assessments: list[QuoteAssessment],
        errors: list[PipelineError],
        timings_ms: dict[str, int],
    ) -> VerificationReport:
        authority_by_citation = {record.citation_id: record for record in authorities}
        support_by_citation = {assessment.citation_id: assessment for assessment in support_assessments}
        quote_by_id = {quote.id: quote for quote in quotes}
        quote_assessment_by_id = {assessment.quote_id: assessment for assessment in quote_assessments}

        citation_findings: list[CitationFinding] = []
        findings: list[Finding] = []

        for citation in citations:
            support = support_by_citation.get(citation.id)
            authority = authority_by_citation.get(citation.id)
            if support is None:
                continue

            flagged = support.label != "supports"
            severity = self._severity_for_support(support.label)

            citation_finding = CitationFinding(
                id=f"finding_{citation.id}",
                citation_id=citation.id,
                raw_citation=citation.raw_citation,
                proposition_text=citation.proposition_text,
                support_label=support.label,
                confidence=support.confidence,
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
                    confidence=support.confidence,
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

            quote_finding = QuoteFinding(
                id=f"finding_{quote.id}",
                quote_id=quote.id,
                quote_text=quote.quote_text,
                citation_id=quote.citation_id,
                quote_label=assessment.label,
                confidence=assessment.confidence,
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
                    confidence=assessment.confidence,
                    status=assessment.label,
                    supports_flag=flagged,
                    reference_id=quote.id,
                    message=assessment.reason,
                    evidence_spans=[quote.motion_span, *assessment.evidence_spans],
                )
            )

        flags_total = sum(1 for finding in findings if finding.supports_flag)
        status: str = "complete"
        if errors:
            status = "partial"
        if not citation_findings and not quote_findings:
            status = "failed"

        summary = ReportSummary(
            citations_extracted=len(citations),
            quotes_checked=len(quotes),
            flags_total=flags_total,
        )

        return VerificationReport(
            mode=mode,
            run_id=run_id,
            status=status,
            summary=summary,
            citation_findings=citation_findings,
            quote_findings=quote_findings,
            findings=findings,
            errors=errors,
            timings_ms=timings_ms,
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
