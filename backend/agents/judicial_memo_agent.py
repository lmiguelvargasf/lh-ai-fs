from __future__ import annotations

from agents.prompts import JUDICIAL_MEMO_SYSTEM_PROMPT
from llm import LLMError, call_llm_json, is_llm_configured
from schemas import Finding, JudicialMemo


SEVERITY_ORDER = {"high": 3, "medium": 2, "low": 1}


class JudicialMemoAgent:
    """Generate a one-paragraph judicial memo from top findings."""

    def run(self, findings: list[Finding]) -> JudicialMemo:
        ranked = self._rank(findings)
        top = ranked[:3]

        if not top:
            return JudicialMemo(
                text=(
                    "No material verification findings were generated from the current record. "
                    "The submitted motion appears internally consistent against available sources."
                ),
                supporting_finding_ids=[],
                generation_mode="template",
                uncertainty_note="No high-priority findings were available for memo synthesis.",
            )

        if is_llm_configured():
            llm_memo = self._generate_with_llm(top)
            if llm_memo is not None:
                return llm_memo

        return self._generate_template(top)

    def _generate_with_llm(self, top_findings: list[Finding]) -> JudicialMemo | None:
        finding_summaries = []
        for finding in top_findings:
            finding_summaries.append(
                {
                    "id": finding.id,
                    "kind": finding.kind,
                    "severity": finding.severity,
                    "status": finding.status,
                    "confidence": finding.confidence,
                    "message": finding.message,
                }
            )

        messages = [
            {"role": "system", "content": JUDICIAL_MEMO_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Generate a one-paragraph judicial memo from the following findings.\n"
                    f"Findings: {finding_summaries}\n"
                    "Return JSON with keys: memo_text, uncertainty_note."
                ),
            },
        ]

        try:
            payload = call_llm_json(messages)
            memo_text = str(payload.get("memo_text", "")).strip()
            if not memo_text:
                return None

            one_paragraph = " ".join(memo_text.splitlines()).strip()
            uncertainty_note = str(payload.get("uncertainty_note", "")).strip() or None
            return JudicialMemo(
                text=one_paragraph,
                supporting_finding_ids=[finding.id for finding in top_findings],
                generation_mode="llm",
                uncertainty_note=uncertainty_note,
            )
        except (LLMError, ValueError, TypeError):
            return None

    def _generate_template(self, top_findings: list[Finding]) -> JudicialMemo:
        lead = top_findings[0]
        fragments = [
            f"The verification pipeline identified {len(top_findings)} priority issue(s), led by a {lead.severity}-severity {lead.kind.replace('_', ' ')} finding ({lead.status}) with calibrated confidence {lead.confidence:.2f}."
        ]

        for finding in top_findings[1:]:
            fragments.append(
                f"Additional findings include {finding.kind.replace('_', ' ')} ({finding.status}, confidence {finding.confidence:.2f})."
            )

        fragments.append(
            "These findings warrant focused judicial review of source support, quote fidelity, and cross-document factual consistency."
        )

        memo_text = " ".join(fragments)
        return JudicialMemo(
            text=memo_text,
            supporting_finding_ids=[finding.id for finding in top_findings],
            generation_mode="template",
            uncertainty_note="Template fallback was used because model memo generation was unavailable or failed.",
        )

    def _rank(self, findings: list[Finding]) -> list[Finding]:
        ranked = sorted(
            findings,
            key=lambda item: (
                int(item.supports_flag),
                SEVERITY_ORDER.get(item.severity, 0),
                item.confidence,
            ),
            reverse=True,
        )
        return ranked
