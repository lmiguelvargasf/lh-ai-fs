from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


PipelineMode = Literal["tier1"]
ReportStatus = Literal["complete", "partial", "failed"]
RetrievalStatus = Literal["found", "not_found", "error", "disabled"]
SupportLabel = Literal[
    "supports",
    "partially_supports",
    "does_not_support",
    "could_not_verify",
]
QuoteLabel = Literal["exact", "minor_difference", "material_difference", "could_not_verify"]
Severity = Literal["low", "medium", "high"]


class AnalyzeRequest(BaseModel):
    mode: PipelineMode = "tier1"
    use_web_retrieval: bool = True


class TextSpan(BaseModel):
    document_id: str
    start: int
    end: int
    excerpt: str | None = None


class DocumentChunk(BaseModel):
    id: str
    span: TextSpan
    text: str


class DocumentRecord(BaseModel):
    id: str
    name: str
    text: str
    chunks: list[DocumentChunk] = Field(default_factory=list)


class DocumentBundle(BaseModel):
    documents: list[DocumentRecord]
    motion_document_id: str


class CitationUnit(BaseModel):
    id: str
    raw_citation: str
    normalized_citation: str
    proposition_text: str
    motion_span: TextSpan
    needs_review: bool = False


class QuoteUnit(BaseModel):
    id: str
    quote_text: str
    citation_id: str | None = None
    proposition_text: str
    motion_span: TextSpan


class ExtractionOutput(BaseModel):
    citations: list[CitationUnit] = Field(default_factory=list)
    quotes: list[QuoteUnit] = Field(default_factory=list)


class AuthorityRecord(BaseModel):
    citation_id: str
    normalized_citation: str
    retrieval_status: RetrievalStatus
    source_url: str | None = None
    authority_text: str | None = None
    authority_spans: list[TextSpan] = Field(default_factory=list)
    error: str | None = None


class SupportAssessment(BaseModel):
    citation_id: str
    label: SupportLabel
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    evidence_spans: list[TextSpan] = Field(default_factory=list)
    uncertainty_reason: str | None = None


class QuoteAssessment(BaseModel):
    quote_id: str
    label: QuoteLabel
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    evidence_spans: list[TextSpan] = Field(default_factory=list)
    uncertainty_reason: str | None = None


class Finding(BaseModel):
    id: str
    kind: Literal["citation_support", "quote_accuracy"]
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    status: str
    supports_flag: bool
    reference_id: str
    message: str
    evidence_spans: list[TextSpan] = Field(default_factory=list)


class CitationFinding(BaseModel):
    id: str
    citation_id: str
    raw_citation: str
    proposition_text: str
    support_label: SupportLabel
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    uncertainty_reason: str | None = None
    retrieval_status: RetrievalStatus
    source_url: str | None = None
    motion_span: TextSpan
    evidence_spans: list[TextSpan] = Field(default_factory=list)
    flagged: bool


class QuoteFinding(BaseModel):
    id: str
    quote_id: str
    quote_text: str
    citation_id: str | None = None
    quote_label: QuoteLabel
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    uncertainty_reason: str | None = None
    motion_span: TextSpan
    evidence_spans: list[TextSpan] = Field(default_factory=list)
    flagged: bool


class ReportSummary(BaseModel):
    citations_extracted: int = 0
    quotes_checked: int = 0
    flags_total: int = 0


class PipelineError(BaseModel):
    step: str
    message: str
    detail: str | None = None


class VerificationReport(BaseModel):
    report_version: str = "1.0"
    mode: PipelineMode = "tier1"
    status: ReportStatus = "complete"
    run_id: str
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    summary: ReportSummary = Field(default_factory=ReportSummary)
    citation_findings: list[CitationFinding] = Field(default_factory=list)
    quote_findings: list[QuoteFinding] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    errors: list[PipelineError] = Field(default_factory=list)
    timings_ms: dict[str, int] = Field(default_factory=dict)


class AnalysisArtifacts(BaseModel):
    bundle: DocumentBundle
    extraction: ExtractionOutput
    authorities: list[AuthorityRecord]
    support_assessments: list[SupportAssessment]
    quote_assessments: list[QuoteAssessment]


class EvalMetricSummary(BaseModel):
    precision: float
    recall: float
    hallucination_rate: float
    true_positive: int
    false_positive: int
    false_negative: int


class EvalResult(BaseModel):
    metrics: EvalMetricSummary
    details: dict[str, Any]
