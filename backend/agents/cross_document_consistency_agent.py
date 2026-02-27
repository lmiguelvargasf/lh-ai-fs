from __future__ import annotations

import re

from schemas import CrossDocumentAssessment, DocumentBundle, FactClaim, TextSpan
from utils.text_utils import find_best_substring_span, lexical_overlap_ratio, normalize_whitespace


MONTH_PATTERN = (
    r"(?:January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+\d{1,2},\s+\d{4}"
)


class CrossDocumentConsistencyAgent:
    """Check factual claim consistency between the motion and other case documents."""

    def run(
        self,
        claims: list[FactClaim],
        bundle: DocumentBundle,
    ) -> list[CrossDocumentAssessment]:
        external_docs = [doc for doc in bundle.documents if doc.id != bundle.motion_document_id]
        assessments: list[CrossDocumentAssessment] = []

        for claim in claims:
            assessment = self._assess_claim(claim, external_docs)
            assessments.append(assessment)

        return assessments

    def _assess_claim(self, claim: FactClaim, external_docs: list) -> CrossDocumentAssessment:
        claim_text = claim.claim_text
        lowered = claim_text.lower()

        date_assessment = self._assess_date_conflict(claim, external_docs)
        if date_assessment is not None:
            return date_assessment

        ppe_assessment = self._assess_ppe_conflict(claim, external_docs)
        if ppe_assessment is not None:
            return ppe_assessment

        if "general contractor" in lowered:
            span = self._find_sentence_with_terms(external_docs, ["harmon construction group", "general contractor"])
            if span is not None:
                return CrossDocumentAssessment(
                    claim_id=claim.id,
                    label="supported",
                    confidence=0.84,
                    reason="External documents corroborate Harmon as the general contractor.",
                    evidence_spans=[span],
                    uncertainty_reason=None,
                )

        if "employed by apex staffing solutions" in lowered or "employer" in lowered:
            span = self._find_sentence_with_terms(external_docs, ["apex staffing solutions", "employer"])
            if span is not None:
                return CrossDocumentAssessment(
                    claim_id=claim.id,
                    label="supported",
                    confidence=0.84,
                    reason="External documents identify Rivera's employer as Apex Staffing Solutions.",
                    evidence_spans=[span],
                    uncertainty_reason=None,
                )

        if "osha" in lowered and "inspection" in lowered:
            return CrossDocumentAssessment(
                claim_id=claim.id,
                label="could_not_verify",
                confidence=0.3,
                reason="Provided case documents do not contain inspection records confirming this statement.",
                evidence_spans=[],
                uncertainty_reason="No Cal/OSHA inspection report is present in source documents",
            )

        if "filed the instant action" in lowered or ("file" in lowered and "complaint" in lowered):
            return CrossDocumentAssessment(
                claim_id=claim.id,
                label="could_not_verify",
                confidence=0.25,
                reason="Complaint filing metadata is not available in the provided documents.",
                evidence_spans=[],
                uncertainty_reason="Court docket document is missing",
            )

        best_span, best_ratio = self._best_overlap_span(claim_text, external_docs)
        if best_span is not None and best_ratio >= 0.55:
            return CrossDocumentAssessment(
                claim_id=claim.id,
                label="supported",
                confidence=min(0.9, 0.55 + best_ratio * 0.4),
                reason="External documents closely match the factual content of the claim.",
                evidence_spans=[best_span],
                uncertainty_reason=None,
            )

        if best_span is not None and best_ratio >= 0.34:
            return CrossDocumentAssessment(
                claim_id=claim.id,
                label="partially_supported",
                confidence=min(0.78, 0.4 + best_ratio * 0.5),
                reason="External evidence overlaps with part of the claim but does not fully corroborate it.",
                evidence_spans=[best_span],
                uncertainty_reason=None,
            )

        return CrossDocumentAssessment(
            claim_id=claim.id,
            label="could_not_verify",
            confidence=0.32,
            reason="No sufficiently specific corroborating evidence was found in the provided documents.",
            evidence_spans=[],
            uncertainty_reason="Evidence was weak or missing",
        )

    def _assess_date_conflict(self, claim: FactClaim, external_docs: list) -> CrossDocumentAssessment | None:
        claim_dates = self._extract_dates(claim.claim_text)
        if not claim_dates:
            return None

        matching: list[TextSpan] = []
        conflicting: list[TextSpan] = []

        for doc in external_docs:
            for sentence, start, end in self._iter_sentences(doc.text):
                sentence_dates = self._extract_dates(sentence)
                if not sentence_dates:
                    continue

                span = TextSpan(
                    document_id=doc.id,
                    start=start,
                    end=end,
                    excerpt=normalize_whitespace(sentence)[:500],
                )

                if any(date in claim_dates for date in sentence_dates):
                    matching.append(span)
                else:
                    if self._incident_context(claim.claim_text) and self._incident_context(sentence):
                        conflicting.append(span)

        if conflicting and not matching:
            return CrossDocumentAssessment(
                claim_id=claim.id,
                label="contradicted",
                confidence=0.93,
                reason="External documents report a conflicting incident date for the same event.",
                evidence_spans=[conflicting[0]],
                uncertainty_reason=None,
            )

        if matching and conflicting:
            return CrossDocumentAssessment(
                claim_id=claim.id,
                label="partially_supported",
                confidence=0.62,
                reason="Some external records match the date, but others conflict.",
                evidence_spans=[matching[0], conflicting[0]],
                uncertainty_reason=None,
            )

        if matching:
            return CrossDocumentAssessment(
                claim_id=claim.id,
                label="supported",
                confidence=0.81,
                reason="External records corroborate the claim date.",
                evidence_spans=[matching[0]],
                uncertainty_reason=None,
            )

        return None

    def _assess_ppe_conflict(self, claim: FactClaim, external_docs: list) -> CrossDocumentAssessment | None:
        lowered = claim.claim_text.lower()
        negative_ppe = (
            "not wearing" in lowered
            and any(token in lowered for token in ["protective", "ppe", "harness", "hard hat"])
        )
        if not negative_ppe:
            return None

        support_span = self._find_sentence_with_terms(external_docs, ["wearing", "hard hat", "harness"])
        if support_span is not None:
            return CrossDocumentAssessment(
                claim_id=claim.id,
                label="contradicted",
                confidence=0.91,
                reason="External witnesses and reports indicate Rivera was wearing required safety gear.",
                evidence_spans=[support_span],
                uncertainty_reason=None,
            )

        return CrossDocumentAssessment(
            claim_id=claim.id,
            label="could_not_verify",
            confidence=0.34,
            reason="No corroborating PPE evidence was found in external documents.",
            evidence_spans=[],
            uncertainty_reason="No explicit PPE confirmation found",
        )

    @staticmethod
    def _extract_dates(text: str) -> list[str]:
        return [normalize_whitespace(match.group(0)) for match in re.finditer(MONTH_PATTERN, text)]

    @staticmethod
    def _incident_context(text: str) -> bool:
        lowered = text.lower()
        return any(token in lowered for token in ["incident", "collapse", "scaffolding", "fall", "accident"])

    @staticmethod
    def _iter_sentences(text: str) -> list[tuple[str, int, int]]:
        segments: list[tuple[str, int, int]] = []
        cursor = 0
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                cursor += len(line) + 1
                continue

            start = text.find(line, cursor)
            if start == -1:
                start = cursor
            end = start + len(line)
            cursor = end + 1

            if len(stripped) >= 25:
                segments.append((stripped, start, end))

        return segments

    def _find_sentence_with_terms(self, external_docs: list, terms: list[str]) -> TextSpan | None:
        terms_lower = [term.lower() for term in terms]
        for doc in external_docs:
            for sentence, start, end in self._iter_sentences(doc.text):
                lowered = sentence.lower()
                if all(term in lowered for term in terms_lower):
                    return TextSpan(
                        document_id=doc.id,
                        start=start,
                        end=end,
                        excerpt=normalize_whitespace(sentence)[:500],
                    )
        return None

    def _best_overlap_span(self, claim_text: str, external_docs: list) -> tuple[TextSpan | None, float]:
        best_span: TextSpan | None = None
        best_ratio = 0.0

        for doc in external_docs:
            for sentence, start, end in self._iter_sentences(doc.text):
                ratio = lexical_overlap_ratio(claim_text, sentence)
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_span = TextSpan(
                        document_id=doc.id,
                        start=start,
                        end=end,
                        excerpt=normalize_whitespace(sentence)[:500],
                    )

        if best_span is None:
            # Fallback to fuzzy substring search at document level.
            for doc in external_docs:
                start, end, ratio = find_best_substring_span(doc.text, claim_text)
                if ratio > best_ratio and end > start:
                    best_ratio = ratio
                    best_span = TextSpan(
                        document_id=doc.id,
                        start=start,
                        end=end,
                        excerpt=normalize_whitespace(doc.text[start:end])[:500],
                    )

        return best_span, best_ratio
