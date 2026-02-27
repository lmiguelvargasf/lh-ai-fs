from __future__ import annotations

import time
from uuid import uuid4

from agents.authority_retrieval_agent import AuthorityRetrievalAgent
from agents.citation_extraction_agent import CitationExtractionAgent
from agents.citation_support_verifier_agent import CitationSupportVerifierAgent
from agents.confidence_calibration_agent import ConfidenceCalibrationAgent
from agents.cross_document_consistency_agent import CrossDocumentConsistencyAgent
from agents.document_ingest_agent import DocumentIngestAgent
from agents.fact_claim_extraction_agent import FactClaimExtractionAgent
from agents.judicial_memo_agent import JudicialMemoAgent
from agents.quote_accuracy_verifier_agent import QuoteAccuracyVerifierAgent
from agents.report_assembler_agent import ReportAssemblerAgent
from schemas import AnalyzeRequest, JudicialMemo, PipelineError, VerificationReport


class PipelineOrchestrator:
    """Typed DAG orchestration for the full analysis pipeline."""

    def __init__(self) -> None:
        self.document_ingest_agent = DocumentIngestAgent()
        self.citation_extraction_agent = CitationExtractionAgent()
        self.authority_retrieval_agent = AuthorityRetrievalAgent()
        self.citation_support_verifier_agent = CitationSupportVerifierAgent()
        self.quote_accuracy_verifier_agent = QuoteAccuracyVerifierAgent()
        self.fact_claim_extraction_agent = FactClaimExtractionAgent()
        self.cross_document_consistency_agent = CrossDocumentConsistencyAgent()
        self.confidence_calibration_agent = ConfidenceCalibrationAgent()
        self.judicial_memo_agent = JudicialMemoAgent()
        self.report_assembler_agent = ReportAssemblerAgent()

    def run(
        self,
        documents: dict[str, str],
        request: AnalyzeRequest,
        authority_overrides: dict[str, dict] | None = None,
    ) -> VerificationReport:
        run_id = str(uuid4())
        timings_ms: dict[str, int] = {}
        errors: list[PipelineError] = []

        bundle = None
        extraction = None
        authorities = []
        support_assessments = []
        quote_assessments = []
        fact_claims = []
        cross_doc_assessments = []
        calibrations = []
        judicial_memo = JudicialMemo()

        start = time.perf_counter()
        try:
            bundle = self.document_ingest_agent.run(documents)
        except Exception as exc:  # noqa: BLE001
            errors.append(
                PipelineError(step="document_ingest", message="Document ingest failed", detail=str(exc))
            )
        timings_ms["document_ingest"] = int((time.perf_counter() - start) * 1000)

        start = time.perf_counter()
        if bundle is not None:
            try:
                extraction = self.citation_extraction_agent.run(bundle)
            except Exception as exc:  # noqa: BLE001
                errors.append(
                    PipelineError(
                        step="citation_extraction",
                        message="Citation extraction failed",
                        detail=str(exc),
                    )
                )
        timings_ms["citation_extraction"] = int((time.perf_counter() - start) * 1000)

        start = time.perf_counter()
        if extraction is not None:
            try:
                authorities = self.authority_retrieval_agent.run(
                    extraction.citations,
                    use_web_retrieval=request.use_web_retrieval,
                    authority_overrides=authority_overrides,
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(
                    PipelineError(
                        step="authority_retrieval",
                        message="Authority retrieval failed",
                        detail=str(exc),
                    )
                )
        timings_ms["authority_retrieval"] = int((time.perf_counter() - start) * 1000)

        start = time.perf_counter()
        if extraction is not None:
            try:
                support_assessments = self.citation_support_verifier_agent.run(
                    extraction.citations,
                    authorities,
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(
                    PipelineError(
                        step="citation_support_verification",
                        message="Citation support verification failed",
                        detail=str(exc),
                    )
                )
        timings_ms["citation_support_verification"] = int((time.perf_counter() - start) * 1000)

        start = time.perf_counter()
        if extraction is not None:
            try:
                quote_assessments = self.quote_accuracy_verifier_agent.run(
                    extraction.quotes,
                    authorities,
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(
                    PipelineError(
                        step="quote_accuracy_verification",
                        message="Quote verification failed",
                        detail=str(exc),
                    )
                )
        timings_ms["quote_accuracy_verification"] = int((time.perf_counter() - start) * 1000)

        start = time.perf_counter()
        if bundle is not None:
            try:
                fact_claims = self.fact_claim_extraction_agent.run(bundle)
            except Exception as exc:  # noqa: BLE001
                errors.append(
                    PipelineError(
                        step="fact_claim_extraction",
                        message="Fact claim extraction failed",
                        detail=str(exc),
                    )
                )
        timings_ms["fact_claim_extraction"] = int((time.perf_counter() - start) * 1000)

        start = time.perf_counter()
        if bundle is not None:
            try:
                cross_doc_assessments = self.cross_document_consistency_agent.run(
                    fact_claims,
                    bundle,
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(
                    PipelineError(
                        step="cross_document_consistency",
                        message="Cross-document consistency verification failed",
                        detail=str(exc),
                    )
                )
        timings_ms["cross_document_consistency"] = int((time.perf_counter() - start) * 1000)

        start = time.perf_counter()
        if extraction is not None:
            try:
                calibrations = self.confidence_calibration_agent.run(
                    support_assessments=support_assessments,
                    quote_assessments=quote_assessments,
                    cross_doc_assessments=cross_doc_assessments,
                    authorities=authorities,
                    quotes=extraction.quotes,
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(
                    PipelineError(
                        step="confidence_calibration",
                        message="Confidence calibration failed",
                        detail=str(exc),
                    )
                )
        timings_ms["confidence_calibration"] = int((time.perf_counter() - start) * 1000)

        start = time.perf_counter()
        if extraction is None:
            return VerificationReport(
                status="failed",
                run_id=run_id,
                errors=errors,
                timings_ms=timings_ms,
            )

        preview_report = self.report_assembler_agent.run(
            run_id=run_id,
            citations=extraction.citations,
            quotes=extraction.quotes,
            authorities=authorities,
            support_assessments=support_assessments,
            quote_assessments=quote_assessments,
            fact_claims=fact_claims,
            cross_doc_assessments=cross_doc_assessments,
            calibrations=calibrations,
            judicial_memo=JudicialMemo(),
            errors=errors,
            timings_ms=timings_ms,
        )
        timings_ms["report_assembly_preview"] = int((time.perf_counter() - start) * 1000)

        start = time.perf_counter()
        try:
            judicial_memo = self.judicial_memo_agent.run(preview_report.findings)
        except Exception as memo_exc:  # noqa: BLE001
            try:
                judicial_memo = self._memo_template_fallback(preview_report.findings)
                errors.append(
                    PipelineError(
                        step="judicial_memo",
                        message="Judicial memo generation failed; template fallback applied",
                        detail=str(memo_exc),
                    )
                )
            except Exception as fallback_exc:  # noqa: BLE001
                errors.append(
                    PipelineError(
                        step="judicial_memo",
                        message="Judicial memo generation failed with no fallback",
                        detail=f"memo_error={memo_exc}; fallback_error={fallback_exc}",
                    )
                )
                judicial_memo = JudicialMemo(
                    text="",
                    supporting_finding_ids=[],
                    generation_mode="template",
                    uncertainty_note="Memo unavailable due to generation and fallback failures.",
                )
        timings_ms["judicial_memo"] = int((time.perf_counter() - start) * 1000)

        start = time.perf_counter()
        report = self.report_assembler_agent.run(
            run_id=run_id,
            citations=extraction.citations,
            quotes=extraction.quotes,
            authorities=authorities,
            support_assessments=support_assessments,
            quote_assessments=quote_assessments,
            fact_claims=fact_claims,
            cross_doc_assessments=cross_doc_assessments,
            calibrations=calibrations,
            judicial_memo=judicial_memo,
            errors=errors,
            timings_ms=timings_ms,
        )
        timings_ms["report_assembly"] = int((time.perf_counter() - start) * 1000)
        report.timings_ms = timings_ms
        return report

    @staticmethod
    def _memo_template_fallback(findings) -> JudicialMemo:
        if not findings:
            return JudicialMemo(
                text=(
                    "No material verification findings were produced for this record. "
                    "The submitted materials appear internally consistent on available checks."
                ),
                supporting_finding_ids=[],
                generation_mode="template",
                uncertainty_note="No ranked findings were available for memo synthesis.",
            )

        ranked = sorted(
            findings,
            key=lambda item: (int(item.supports_flag), item.confidence),
            reverse=True,
        )
        top = ranked[:3]
        lead = top[0]

        text = (
            f"The verification pipeline identified {len(top)} priority issue(s), led by a "
            f"{lead.severity}-severity {lead.kind.replace('_', ' ')} finding with status "
            f"{lead.status} and calibrated confidence {lead.confidence:.2f}; additional findings "
            "indicate potential support, quote, or factual consistency concerns warranting focused judicial review."
        )
        return JudicialMemo(
            text=text,
            supporting_finding_ids=[item.id for item in top],
            generation_mode="template",
            uncertainty_note="Template fallback used due to memo generation failure.",
        )
