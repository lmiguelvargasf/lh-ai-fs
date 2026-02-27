# Reflection

## What I prioritized

I prioritized a reliable Tier 1 + Tier 2 pipeline with typed contracts, explicit agent boundaries, and deterministic evaluation outputs.

Key decisions:

1. Typed DAG orchestration over free-form supervisor behavior to keep failures isolated and debuggable.
2. Strict JSON/schema-driven handoffs between agents, including the new cross-document branch.
3. Deterministic eval harness with fixed fixtures and explicit hallucination checks so quality signals are reproducible.

## Tier 2 tradeoffs

1. Cross-document consistency is precision-first for contradiction flags. I only mark `contradicted` with explicit conflicting evidence, and I default to `could_not_verify` when evidence is weak.
2. Fact-claim extraction is deterministic by default (rules-first) to keep evals stable, with optional LLM extraction behind a toggle.
3. Cross-document checks are anchored to sentence-level evidence spans, which improves auditability but can miss nuanced multi-sentence context.

## What worked well

1. Agent decomposition remains clear and non-overlapping across Tier 1 and Tier 2.
2. `/analyze` returns a structured report with citation, quote, and cross-document findings.
3. Eval reporting now includes task breakdown (`citation_quote`, `cross_document`) and combined roll-up metrics.

## Remaining gaps and limitations

1. Tier 3 judicial memo and confidence calibration layering are not implemented.
2. Citation/quote verification still depends on best-effort authority retrieval and can degrade when sources are unavailable.
3. Rule-based cross-document logic is tuned for this case format and should be generalized with broader fixtures.
4. Current confidence values are heuristic and not statistically calibrated.

## If I had more time

1. Add more cross-document fixtures (adversarial contradictions, partial supports, and neutral controls).
2. Add optional LLM adjudication for edge cases while preserving deterministic fallback.
3. Add calibration and threshold tuning using held-out eval examples.
4. Extend frontend evidence drill-down for side-by-side claim vs source views.
