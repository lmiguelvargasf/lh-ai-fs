from __future__ import annotations

from typing import Any

from agents.prompts import CITATION_SUPPORT_SYSTEM_PROMPT
from llm import LLMError, call_llm_json, is_llm_configured
from schemas import AuthorityRecord, CitationUnit, SupportAssessment, TextSpan
from utils.text_utils import find_best_substring_span, lexical_overlap_ratio


VALID_LABELS = {
    "supports",
    "partially_supports",
    "does_not_support",
    "could_not_verify",
}


class CitationSupportVerifierAgent:
    """Assess proposition support based on retrieved authority text."""

    def run(
        self,
        citations: list[CitationUnit],
        authorities: list[AuthorityRecord],
    ) -> list[SupportAssessment]:
        authority_by_citation = {record.citation_id: record for record in authorities}
        assessments: list[SupportAssessment] = []

        for citation in citations:
            authority = authority_by_citation.get(citation.id)
            if authority is None or authority.retrieval_status != "found" or not authority.authority_text:
                assessments.append(
                    SupportAssessment(
                        citation_id=citation.id,
                        label="could_not_verify",
                        confidence=0.2,
                        reason="Authority text could not be retrieved.",
                        evidence_spans=[],
                        uncertainty_reason=authority.error if authority else "Missing authority record",
                    )
                )
                continue

            assessment = self._assess_support(citation, authority)
            assessments.append(assessment)

        return assessments

    def _assess_support(
        self,
        citation: CitationUnit,
        authority: AuthorityRecord,
    ) -> SupportAssessment:
        if is_llm_configured():
            llm_assessment = self._assess_support_with_llm(citation, authority)
            if llm_assessment is not None:
                return llm_assessment

        return self._assess_support_with_heuristic(citation, authority)

    def _assess_support_with_llm(
        self,
        citation: CitationUnit,
        authority: AuthorityRecord,
    ) -> SupportAssessment | None:
        messages = [
            {"role": "system", "content": CITATION_SUPPORT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Citation: "
                    f"{citation.raw_citation}\n"
                    "Proposition: "
                    f"{citation.proposition_text}\n"
                    "Authority text: "
                    f"{authority.authority_text[:6000]}\n\n"
                    "Return JSON with keys: label, confidence, reason, evidence_quote."
                ),
            },
        ]

        try:
            payload = call_llm_json(messages)
            label = str(payload.get("label", "")).strip()
            if label not in VALID_LABELS:
                return None

            confidence = float(payload.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))
            reason = str(payload.get("reason", "")).strip()[:320] or "No reason provided."
            evidence_quote = str(payload.get("evidence_quote", "")).strip()

            spans: list[TextSpan] = []
            if label != "could_not_verify" and evidence_quote:
                start, end, ratio = find_best_substring_span(authority.authority_text or "", evidence_quote)
                if end > start and ratio >= 0.4:
                    spans.append(
                        TextSpan(
                            document_id=f"authority:{citation.id}",
                            start=start,
                            end=end,
                            excerpt=(authority.authority_text or "")[start:end][:500],
                        )
                    )

            uncertainty = None
            if label == "could_not_verify":
                uncertainty = "LLM reported insufficient authority context"

            return SupportAssessment(
                citation_id=citation.id,
                label=label,
                confidence=confidence,
                reason=reason,
                evidence_spans=spans,
                uncertainty_reason=uncertainty,
            )
        except (LLMError, ValueError, TypeError):
            return None

    def _assess_support_with_heuristic(
        self,
        citation: CitationUnit,
        authority: AuthorityRecord,
    ) -> SupportAssessment:
        authority_text = authority.authority_text or ""
        ratio = lexical_overlap_ratio(citation.proposition_text, authority_text)

        if ratio >= 0.35:
            label = "supports"
            confidence = min(0.95, 0.55 + ratio)
            reason = "High lexical overlap between proposition and authority text."
        elif ratio >= 0.2:
            label = "partially_supports"
            confidence = min(0.85, 0.45 + ratio)
            reason = "Authority appears related but overlap is limited."
        else:
            label = "does_not_support"
            confidence = max(0.55, 0.8 - ratio)
            reason = "Authority text does not materially match the proposition."

        start, end, match_ratio = find_best_substring_span(authority_text, citation.proposition_text)
        spans: list[TextSpan] = []
        if end > start and match_ratio >= 0.25:
            spans.append(
                TextSpan(
                    document_id=f"authority:{citation.id}",
                    start=start,
                    end=end,
                    excerpt=authority_text[start:end][:500],
                )
            )

        return SupportAssessment(
            citation_id=citation.id,
            label=label,
            confidence=max(0.0, min(1.0, confidence)),
            reason=reason,
            evidence_spans=spans,
            uncertainty_reason=None,
        )
