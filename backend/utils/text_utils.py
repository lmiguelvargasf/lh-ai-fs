from __future__ import annotations

import hashlib
import re
from difflib import SequenceMatcher

from schemas import TextSpan

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "was",
    "with",
}


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_citation(citation: str) -> str:
    citation = normalize_whitespace(citation)
    citation = citation.rstrip(".;")
    return citation


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def tokens_for_overlap(text: str) -> set[str]:
    raw_tokens = re.findall(r"[A-Za-z0-9']+", text.lower())
    return {token for token in raw_tokens if token not in STOPWORDS and len(token) > 2}


def lexical_overlap_ratio(lhs: str, rhs: str) -> float:
    lhs_tokens = tokens_for_overlap(lhs)
    rhs_tokens = tokens_for_overlap(rhs)
    if not lhs_tokens:
        return 0.0
    overlap = lhs_tokens.intersection(rhs_tokens)
    return len(overlap) / len(lhs_tokens)


def sentence_span(text: str, idx_start: int, idx_end: int, document_id: str) -> TextSpan:
    start = text.rfind(".", 0, idx_start)
    alt_start = text.rfind("\n", 0, idx_start)
    start = max(start, alt_start)
    start = 0 if start == -1 else start + 1

    end_period = text.find(".", idx_end)
    end_newline = text.find("\n", idx_end)
    candidates = [x for x in [end_period, end_newline] if x != -1]
    end = min(candidates) if candidates else len(text)

    excerpt = text[start:end].strip()
    if not excerpt:
        excerpt = text[idx_start:idx_end].strip()
    return TextSpan(document_id=document_id, start=start, end=end, excerpt=excerpt[:500])


def paragraph_chunks(text: str, document_id: str, max_len: int = 900) -> list[tuple[int, int, str]]:
    chunks: list[tuple[int, int, str]] = []
    offset = 0
    for paragraph in text.split("\n\n"):
        raw = paragraph.strip()
        if not raw:
            offset += len(paragraph) + 2
            continue

        paragraph_start = text.find(paragraph, offset)
        if paragraph_start == -1:
            paragraph_start = offset

        if len(raw) <= max_len:
            start = paragraph_start
            end = start + len(paragraph)
            chunks.append((start, end, raw))
        else:
            running = 0
            while running < len(raw):
                piece = raw[running : running + max_len]
                start = paragraph_start + running
                end = start + len(piece)
                chunks.append((start, end, piece))
                running += max_len

        offset = paragraph_start + len(paragraph) + 2

    return chunks


def find_best_substring_span(source_text: str, query_text: str) -> tuple[int, int, float]:
    normalized_query = normalize_whitespace(query_text)
    if not source_text or not normalized_query:
        return (0, 0, 0.0)

    direct_idx = source_text.find(query_text)
    if direct_idx != -1:
        return (direct_idx, direct_idx + len(query_text), 1.0)

    window = max(len(query_text) + 40, 160)
    best = (0, 0, 0.0)
    for start in range(0, max(len(source_text) - 1, 1), 40):
        candidate = source_text[start : start + window]
        if not candidate:
            continue
        ratio = SequenceMatcher(None, normalize_whitespace(candidate), normalized_query).ratio()
        if ratio > best[2]:
            best = (start, min(start + window, len(source_text)), ratio)

    return best
