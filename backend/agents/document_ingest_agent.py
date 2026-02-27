from __future__ import annotations

from schemas import DocumentBundle, DocumentChunk, DocumentRecord, TextSpan
from utils.text_utils import normalize_whitespace, paragraph_chunks


class DocumentIngestAgent:
    """Normalize and chunk source documents."""

    def run(self, documents: dict[str, str]) -> DocumentBundle:
        records: list[DocumentRecord] = []
        for name, raw_text in sorted(documents.items()):
            cleaned_text = raw_text.replace("\r\n", "\n").strip()
            chunks: list[DocumentChunk] = []

            for index, (start, end, chunk_text) in enumerate(
                paragraph_chunks(cleaned_text, document_id=name),
                start=1,
            ):
                span = TextSpan(
                    document_id=name,
                    start=start,
                    end=end,
                    excerpt=normalize_whitespace(chunk_text)[:500],
                )
                chunks.append(
                    DocumentChunk(
                        id=f"{name}_chunk_{index:03d}",
                        span=span,
                        text=chunk_text,
                    )
                )

            records.append(
                DocumentRecord(
                    id=name,
                    name=name,
                    text=cleaned_text,
                    chunks=chunks,
                )
            )

        if not records:
            raise ValueError("No documents were loaded")

        motion_document_id = "motion_for_summary_judgment"
        if not any(doc.id == motion_document_id for doc in records):
            raise ValueError(
                f"Missing required motion document: {motion_document_id}.txt"
            )

        return DocumentBundle(documents=records, motion_document_id=motion_document_id)
