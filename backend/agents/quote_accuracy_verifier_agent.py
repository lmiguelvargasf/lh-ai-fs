from __future__ import annotations

import re

from agents.prompts import QUOTE_ACCURACY_SYSTEM_PROMPT
from llm import LLMError, call_llm_json, is_llm_configured
from schemas import AuthorityRecord, QuoteAssessment, QuoteUnit, TextSpan
from utils.text_utils import find_best_substring_span, normalize_whitespace


VALID_LABELS = {"exact", "minor_difference", "material_difference", "could_not_verify"}


class QuoteAccuracyVerifierAgent:
    """Check whether direct quotes match authority text."""

    def run(
        self,
        quotes: list[QuoteUnit],
        authorities: list[AuthorityRecord],
    ) -> list[QuoteAssessment]:
        authority_by_citation = {record.citation_id: record for record in authorities}
        results: list[QuoteAssessment] = []

        for quote in quotes:
            authority = (
                authority_by_citation.get(quote.citation_id)
                if quote.citation_id is not None
                else None
            )
            if (
                authority is None
                or authority.retrieval_status != "found"
                or not authority.authority_text
            ):
                results.append(
                    QuoteAssessment(
                        quote_id=quote.id,
                        label="could_not_verify",
                        confidence=0.2,
                        reason="Quote source text is unavailable.",
                        evidence_spans=[],
                        uncertainty_reason="Missing or unavailable authority text",
                    )
                )
                continue

            assessment = self._assess_quote(quote, authority)
            results.append(assessment)

        return results

    def _assess_quote(self, quote: QuoteUnit, authority: AuthorityRecord) -> QuoteAssessment:
        if is_llm_configured():
            llm_assessment = self._assess_quote_with_llm(quote, authority)
            if llm_assessment is not None:
                return llm_assessment

        return self._assess_quote_with_heuristic(quote, authority)

    def _assess_quote_with_llm(
        self,
        quote: QuoteUnit,
        authority: AuthorityRecord,
    ) -> QuoteAssessment | None:
        messages = [
            {"role": "system", "content": QUOTE_ACCURACY_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Quote: {quote.quote_text}\n"
                    f"Authority text: {authority.authority_text[:6000]}\n\n"
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
                            document_id=f"authority:{quote.citation_id}",
                            start=start,
                            end=end,
                            excerpt=(authority.authority_text or "")[start:end][:500],
                        )
                    )

            uncertainty = None
            if label == "could_not_verify":
                uncertainty = "LLM reported insufficient quote context"

            return QuoteAssessment(
                quote_id=quote.id,
                label=label,
                confidence=confidence,
                reason=reason,
                evidence_spans=spans,
                uncertainty_reason=uncertainty,
            )
        except (LLMError, ValueError, TypeError):
            return None

    def _assess_quote_with_heuristic(
        self,
        quote: QuoteUnit,
        authority: AuthorityRecord,
    ) -> QuoteAssessment:
        authority_text = authority.authority_text or ""
        raw_quote = quote.quote_text
        normalized_quote = normalize_whitespace(raw_quote)

        if raw_quote and raw_quote in authority_text:
            start = authority_text.find(raw_quote)
            end = start + len(raw_quote)
            return QuoteAssessment(
                quote_id=quote.id,
                label="exact",
                confidence=0.99,
                reason="Quote appears verbatim in retrieved authority text.",
                evidence_spans=[
                    TextSpan(
                        document_id=f"authority:{quote.citation_id}",
                        start=start,
                        end=end,
                        excerpt=authority_text[start:end][:500],
                    )
                ],
                uncertainty_reason=None,
            )

        compact_quote = re.sub(r"[^a-z0-9]", "", normalized_quote.lower())
        compact_authority = re.sub(r"[^a-z0-9]", "", authority_text.lower())
        if compact_quote and compact_quote in compact_authority:
            start, end, _ = find_best_substring_span(authority_text, normalized_quote)
            return QuoteAssessment(
                quote_id=quote.id,
                label="minor_difference",
                confidence=0.82,
                reason="Quote matches after punctuation/whitespace normalization.",
                evidence_spans=[
                    TextSpan(
                        document_id=f"authority:{quote.citation_id}",
                        start=start,
                        end=end,
                        excerpt=authority_text[start:end][:500],
                    )
                ],
                uncertainty_reason=None,
            )

        start, end, ratio = find_best_substring_span(authority_text, normalized_quote)
        if ratio >= 0.82:
            label = "minor_difference"
            confidence = 0.68 + (ratio * 0.2)
            reason = "Quote is close but not exact compared with authority language."
        else:
            label = "material_difference"
            confidence = max(0.6, 0.95 - ratio)
            reason = "Quote materially differs from best matching authority text."

        spans: list[TextSpan] = []
        if end > start and ratio >= 0.35:
            spans.append(
                TextSpan(
                    document_id=f"authority:{quote.citation_id}",
                    start=start,
                    end=end,
                    excerpt=authority_text[start:end][:500],
                )
            )

        return QuoteAssessment(
            quote_id=quote.id,
            label=label,
            confidence=max(0.0, min(1.0, confidence)),
            reason=reason,
            evidence_spans=spans,
            uncertainty_reason=None,
        )
