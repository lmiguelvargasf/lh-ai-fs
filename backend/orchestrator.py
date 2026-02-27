from __future__ import annotations

import time
from uuid import uuid4

from agents.authority_retrieval_agent import AuthorityRetrievalAgent
from agents.citation_extraction_agent import CitationExtractionAgent
from agents.citation_support_verifier_agent import CitationSupportVerifierAgent
from agents.document_ingest_agent import DocumentIngestAgent
from agents.quote_accuracy_verifier_agent import QuoteAccuracyVerifierAgent
from agents.report_assembler_agent import ReportAssemblerAgent
from schemas import AnalyzeRequest, PipelineError, VerificationReport


class PipelineOrchestrator:
    """Typed DAG orchestration for Tier 1 analysis pipeline."""

    def __init__(self) -> None:
        self.document_ingest_agent = DocumentIngestAgent()
        self.citation_extraction_agent = CitationExtractionAgent()
        self.authority_retrieval_agent = AuthorityRetrievalAgent()
        self.citation_support_verifier_agent = CitationSupportVerifierAgent()
        self.quote_accuracy_verifier_agent = QuoteAccuracyVerifierAgent()
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

        start = time.perf_counter()
        try:
            bundle = self.document_ingest_agent.run(documents)
        except Exception as exc:  # noqa: BLE001
            errors.append(PipelineError(step="document_ingest", message="Document ingest failed", detail=str(exc)))
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
        if extraction is None:
            return VerificationReport(
                mode=request.mode,
                status="failed",
                run_id=run_id,
                errors=errors,
                timings_ms=timings_ms,
            )

        report = self.report_assembler_agent.run(
            run_id=run_id,
            mode=request.mode,
            citations=extraction.citations,
            quotes=extraction.quotes,
            authorities=authorities,
            support_assessments=support_assessments,
            quote_assessments=quote_assessments,
            errors=errors,
            timings_ms=timings_ms,
        )
        timings_ms["report_assembly"] = int((time.perf_counter() - start) * 1000)
        report.timings_ms = timings_ms
        return report
