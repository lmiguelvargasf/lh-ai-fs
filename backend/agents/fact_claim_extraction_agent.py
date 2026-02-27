from __future__ import annotations

import os
import re

from agents.prompts import FACT_CLAIM_EXTRACTION_SYSTEM_PROMPT
from llm import LLMError, call_llm_json, is_llm_configured
from schemas import DocumentBundle, FactClaim
from utils.text_utils import find_best_substring_span, normalize_whitespace, sentence_span


MONTH_PATTERN = (
    r"(?:January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+\d{1,2},\s+\d{4}"
)


class FactClaimExtractionAgent:
    """Extract atomic factual claims from the motion document."""

    def __init__(self, use_llm: bool | None = None) -> None:
        if use_llm is None:
            # Keep extraction deterministic by default for eval reproducibility.
            use_llm = os.getenv("BS_DETECTOR_USE_LLM_FOR_CLAIMS", "0") == "1"
        self.use_llm = use_llm

    def run(self, bundle: DocumentBundle) -> list[FactClaim]:
        motion_doc = next(doc for doc in bundle.documents if doc.id == bundle.motion_document_id)
        motion_text = motion_doc.text

        if self.use_llm and is_llm_configured():
            llm_claims = self._extract_with_llm(motion_text, motion_doc.id)
            if llm_claims:
                return llm_claims

        return self._extract_with_rules(motion_text, motion_doc.id)

    def _extract_with_llm(self, motion_text: str, motion_doc_id: str) -> list[FactClaim] | None:
        messages = [
            {"role": "system", "content": FACT_CLAIM_EXTRACTION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Extract factual claims from the following motion text. "
                    "Return JSON with key 'claims', where each claim has: "
                    "claim_text, claim_type, source_section.\n\n"
                    f"{motion_text[:12000]}"
                ),
            },
        ]

        try:
            payload = call_llm_json(messages)
            raw_claims = payload.get("claims", [])
            if not isinstance(raw_claims, list):
                return None

            claims: list[FactClaim] = []
            seen: set[str] = set()
            for idx, item in enumerate(raw_claims, start=1):
                if not isinstance(item, dict):
                    continue

                claim_text = normalize_whitespace(str(item.get("claim_text", "")))
                if len(claim_text) < 25:
                    continue

                dedupe_key = claim_text.lower()
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)

                start, end, ratio = find_best_substring_span(motion_text, claim_text)
                if end <= start or ratio < 0.35:
                    continue

                span = sentence_span(motion_text, start, end, motion_doc_id)
                claims.append(
                    FactClaim(
                        id=f"claim_{idx:03d}",
                        claim_text=claim_text,
                        claim_type=self._infer_claim_type(claim_text),
                        motion_span=span,
                        source_section=str(item.get("source_section", "argument")).strip()
                        or "argument",
                    )
                )

            if not claims:
                return None
            return claims[:30]
        except (LLMError, ValueError, TypeError):
            return None

    def _extract_with_rules(self, motion_text: str, motion_doc_id: str) -> list[FactClaim]:
        claims: list[FactClaim] = []
        seen: set[str] = set()

        facts_start = motion_text.find("II. STATEMENT OF UNDISPUTED MATERIAL FACTS")
        facts_end = motion_text.find("III. ARGUMENT")
        facts_section = motion_text[facts_start:facts_end] if facts_start != -1 and facts_end != -1 else motion_text

        fact_pattern = re.compile(
            r"^\s*(\d+)\.\s+(.*?)(?=(?:\n\s*\d+\.\s+)|\n\s*III\.|\Z)",
            flags=re.MULTILINE | re.DOTALL,
        )

        idx = 0
        for match in fact_pattern.finditer(facts_section):
            claim_text = normalize_whitespace(match.group(2))
            if len(claim_text) < 15:
                continue

            dedupe_key = claim_text.lower()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            absolute_start = facts_start + match.start(2) if facts_start != -1 else match.start(2)
            absolute_end = facts_start + match.end(2) if facts_start != -1 else match.end(2)
            span = sentence_span(motion_text, absolute_start, absolute_end, motion_doc_id)

            idx += 1
            claims.append(
                FactClaim(
                    id=f"claim_{idx:03d}",
                    claim_text=claim_text,
                    claim_type=self._infer_claim_type(claim_text),
                    motion_span=span,
                    source_section="statement_of_undisputed_material_facts",
                )
            )

        argument_start = motion_text.find("III. ARGUMENT")
        argument_end = motion_text.find("IV. CONCLUSION")
        if argument_start != -1:
            argument_text = motion_text[argument_start:argument_end if argument_end != -1 else len(motion_text)]
            for sentence in self._argument_factual_sentences(argument_text):
                dedupe_key = sentence.lower()
                if dedupe_key in seen:
                    continue

                absolute_start = motion_text.find(sentence, argument_start)
                if absolute_start == -1:
                    continue
                absolute_end = absolute_start + len(sentence)
                span = sentence_span(motion_text, absolute_start, absolute_end, motion_doc_id)

                seen.add(dedupe_key)
                idx += 1
                claims.append(
                    FactClaim(
                        id=f"claim_{idx:03d}",
                        claim_text=sentence,
                        claim_type=self._infer_claim_type(sentence),
                        motion_span=span,
                        source_section="argument",
                    )
                )

        return claims[:30]

    def _argument_factual_sentences(self, argument_text: str) -> list[str]:
        candidates: list[str] = []
        sentence_candidates = re.split(r"(?<=[.!?])\s+", argument_text)
        for raw in sentence_candidates:
            sentence = normalize_whitespace(raw)
            if len(sentence) < 45:
                continue
            if " v. " in sentence:
                continue

            has_date = re.search(MONTH_PATTERN, sentence) is not None
            has_numeric_fact = re.search(r"\b\d+\b", sentence) is not None
            has_fact_marker = any(
                marker in sentence.lower()
                for marker in [
                    "incident",
                    "inspection",
                    "medical records",
                    "years of experience",
                    "filed",
                    "wearing",
                    "harness",
                    "osha",
                ]
            )

            if has_fact_marker and (has_date or has_numeric_fact):
                candidates.append(sentence)

        return candidates[:6]

    @staticmethod
    def _infer_claim_type(claim_text: str) -> str:
        lowered = claim_text.lower()
        if re.search(MONTH_PATTERN, claim_text):
            return "timeline"
        if "wear" in lowered or "harness" in lowered or "ppe" in lowered:
            return "safety_equipment"
        if "osha" in lowered or "inspection" in lowered or "iipp" in lowered:
            return "safety_compliance"
        if "employed" in lowered or "subcontractor" in lowered or "general contractor" in lowered:
            return "employment_relationship"
        if "filed" in lowered or "complaint" in lowered or "action" in lowered:
            return "procedural"
        return "factual"
