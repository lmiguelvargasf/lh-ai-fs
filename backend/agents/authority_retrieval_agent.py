from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from schemas import AuthorityRecord, CitationUnit, TextSpan
from utils.text_utils import normalize_whitespace, stable_hash


class AuthorityRetrievalAgent:
    """Retrieve cited authority text with cache and graceful fallback."""

    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self.timeout_seconds = timeout_seconds
        self.cache_dir = Path(__file__).resolve().parent.parent / "cache" / "authorities"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        citations: list[CitationUnit],
        use_web_retrieval: bool,
        authority_overrides: dict[str, dict] | None = None,
    ) -> list[AuthorityRecord]:
        records: list[AuthorityRecord] = []
        overrides = authority_overrides or {}

        for citation in citations:
            override = overrides.get(citation.normalized_citation)
            if override:
                records.append(self._record_from_override(citation, override))
                continue

            cached = self._read_cache(citation)
            if cached:
                records.append(cached)
                continue

            if not use_web_retrieval:
                record = AuthorityRecord(
                    citation_id=citation.id,
                    normalized_citation=citation.normalized_citation,
                    retrieval_status="disabled",
                    error="Web retrieval disabled",
                )
                self._write_cache(record)
                records.append(record)
                continue

            record = self._retrieve_from_web(citation)
            self._write_cache(record)
            records.append(record)

        return records

    def _record_from_override(self, citation: CitationUnit, override: dict) -> AuthorityRecord:
        authority_text = override.get("authority_text")
        spans = []
        if authority_text:
            spans.append(
                TextSpan(
                    document_id=f"authority:{citation.id}",
                    start=0,
                    end=len(authority_text),
                    excerpt=authority_text[:500],
                )
            )

        return AuthorityRecord(
            citation_id=citation.id,
            normalized_citation=citation.normalized_citation,
            retrieval_status=override.get("retrieval_status", "found"),
            source_url=override.get("source_url"),
            authority_text=authority_text,
            authority_spans=spans,
            error=override.get("error"),
        )

    def _retrieve_from_web(self, citation: CitationUnit) -> AuthorityRecord:
        status, source_url, authority_text, error = self._fetch_from_courtlistener(
            citation.normalized_citation
        )
        if status != "found":
            fallback_status, fallback_url, fallback_text, fallback_error = self._fetch_from_web_search(
                citation.normalized_citation
            )
            if fallback_status == "found":
                status, source_url, authority_text, error = (
                    fallback_status,
                    fallback_url,
                    fallback_text,
                    None,
                )
            else:
                error = fallback_error or error

        spans: list[TextSpan] = []
        if authority_text:
            spans.append(
                TextSpan(
                    document_id=f"authority:{citation.id}",
                    start=0,
                    end=len(authority_text),
                    excerpt=authority_text[:500],
                )
            )

        return AuthorityRecord(
            citation_id=citation.id,
            normalized_citation=citation.normalized_citation,
            retrieval_status=status,
            source_url=source_url,
            authority_text=authority_text,
            authority_spans=spans,
            error=error,
        )

    def _fetch_from_courtlistener(
        self,
        citation_query: str,
    ) -> tuple[str, str | None, str | None, str | None]:
        url = "https://www.courtlistener.com/api/rest/v4/search/"
        params = {"q": citation_query, "order_by": "score desc"}

        try:
            with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                payload = response.json()

                results = payload.get("results", [])
                if not results:
                    return ("not_found", None, None, "CourtListener returned no results")

                first = results[0]
                snippet = first.get("snippet") or first.get("caseName") or ""
                snippet = self._clean_html(snippet)
                absolute_url = first.get("absolute_url")
                if absolute_url and absolute_url.startswith("/"):
                    absolute_url = f"https://www.courtlistener.com{absolute_url}"

                if snippet:
                    return ("found", absolute_url, snippet, None)

                if absolute_url:
                    page_response = client.get(absolute_url)
                    page_response.raise_for_status()
                    page_text = self._clean_html(page_response.text)
                    if page_text:
                        return ("found", absolute_url, page_text[:7000], None)

                return (
                    "not_found",
                    absolute_url,
                    None,
                    "CourtListener results lacked usable text",
                )
        except Exception as exc:  # noqa: BLE001
            return ("error", None, None, f"CourtListener retrieval failed: {exc}")

    def _fetch_from_web_search(
        self,
        citation_query: str,
    ) -> tuple[str, str | None, str | None, str | None]:
        search_url = "https://duckduckgo.com/html/"
        params = {"q": citation_query}

        try:
            with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
                response = client.get(search_url, params=params)
                response.raise_for_status()
                html = response.text

                match = re.search(r'class="result__a" href="([^"]+)"', html)
                if not match:
                    return ("not_found", None, None, "Fallback search returned no links")

                raw_url = match.group(1)
                parsed = urlparse(raw_url)
                if parsed.path.startswith("/l/"):
                    uddg = parse_qs(parsed.query).get("uddg", [raw_url])[0]
                    raw_url = unquote(uddg)

                page = client.get(raw_url)
                page.raise_for_status()
                text = self._clean_html(page.text)
                if not text:
                    return ("not_found", raw_url, None, "Fallback page had no readable text")

                return ("found", raw_url, text[:7000], None)
        except Exception as exc:  # noqa: BLE001
            return ("error", None, None, f"Fallback retrieval failed: {exc}")

    @staticmethod
    def _clean_html(html: str) -> str:
        no_script = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
        no_style = re.sub(r"<style[\s\S]*?</style>", " ", no_script, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", no_style)
        text = normalize_whitespace(text)
        return text

    def _cache_path(self, citation: CitationUnit) -> Path:
        key = stable_hash(citation.normalized_citation)
        return self.cache_dir / f"{key}.json"

    def _read_cache(self, citation: CitationUnit) -> AuthorityRecord | None:
        path = self._cache_path(citation)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text())
            if payload.get("citation_id") != citation.id:
                payload["citation_id"] = citation.id
            return AuthorityRecord(**payload)
        except Exception:  # noqa: BLE001
            return None

    def _write_cache(self, record: AuthorityRecord) -> None:
        path = self.cache_dir / f"{stable_hash(record.normalized_citation)}.json"
        path.write_text(json.dumps(record.model_dump(), indent=2))
