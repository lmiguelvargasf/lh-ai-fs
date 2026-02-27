from __future__ import annotations

import re

from schemas import CitationUnit, DocumentBundle, ExtractionOutput, QuoteUnit
from utils.text_utils import normalize_citation, sentence_span


CITATION_REGEX = re.compile(
    r"([A-Z][A-Za-z&'\-\.]*?(?:\s+[A-Z][A-Za-z0-9&'\-\.]*)*\s+v\.\s+"
    r"[A-Z][A-Za-z0-9&'\-\.]*?(?:\s+[A-Z][A-Za-z0-9&'\-\.]*)*,\s*"
    r"[^;\n\)]*\((?:[^\)]*?\d{4})\))"
)
QUOTE_REGEX = re.compile(r'"([^"\n]{6,600})"')


class CitationExtractionAgent:
    """Extract citations and direct quotes from the motion text."""

    def run(self, bundle: DocumentBundle) -> ExtractionOutput:
        motion_doc = next(doc for doc in bundle.documents if doc.id == bundle.motion_document_id)
        text = motion_doc.text

        citations: list[CitationUnit] = []
        for index, match in enumerate(CITATION_REGEX.finditer(text), start=1):
            raw_citation = match.group(1).strip()
            span = sentence_span(text, match.start(1), match.end(1), motion_doc.id)
            proposition = span.excerpt or raw_citation
            citations.append(
                CitationUnit(
                    id=f"citation_{index:03d}",
                    raw_citation=raw_citation,
                    normalized_citation=normalize_citation(raw_citation),
                    proposition_text=proposition,
                    motion_span=span,
                    needs_review=False,
                )
            )

        quotes: list[QuoteUnit] = []
        quote_index = 0
        for match in QUOTE_REGEX.finditer(text):
            quote_text = match.group(1).strip()

            # Ignore short defined-term quotes; keep substantive quoted authority language.
            word_count = len([token for token in quote_text.split() if token.strip()])
            if word_count < 6 or len(quote_text) < 35:
                continue

            quote_index += 1
            span = sentence_span(text, match.start(1), match.end(1), motion_doc.id)
            nearest_citation_id = self._nearest_citation_id(citations, match.start(1), text)
            quotes.append(
                QuoteUnit(
                    id=f"quote_{quote_index:03d}",
                    quote_text=quote_text,
                    citation_id=nearest_citation_id,
                    proposition_text=span.excerpt or quote_text,
                    motion_span=span,
                )
            )

        return ExtractionOutput(citations=citations, quotes=quotes)

    @staticmethod
    def _nearest_citation_id(
        citations: list[CitationUnit],
        quote_position: int,
        motion_text: str,
    ) -> str | None:
        if not citations:
            return None

        best_id: str | None = None
        best_distance: int | None = None
        for citation in citations:
            needle = citation.raw_citation
            citation_idx = motion_text.find(needle)
            if citation_idx == -1:
                continue
            # Favor citations appearing before the quote when distances are close.
            adjusted_distance = abs(quote_position - citation_idx)
            if citation_idx <= quote_position:
                adjusted_distance -= 2

            if best_distance is None or adjusted_distance < best_distance:
                best_distance = adjusted_distance
                best_id = citation.id

        return best_id
