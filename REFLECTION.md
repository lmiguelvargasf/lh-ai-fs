# Reflection

## What I prioritized

I prioritized a reliable Tier 1 pipeline with typed contracts, explicit agent boundaries, and deterministic evaluation outputs.

Key decisions:

1. Typed DAG orchestration over free-form supervisor behavior to keep failures isolated and debuggable.
2. Strict JSON and schema-driven handoffs between agents.
3. Deterministic eval harness using gold fixtures plus authority overrides to avoid flaky network-dependent scores.

## Tradeoffs made

1. Citation extraction is regex-first, not fully semantic parsing. It is fast and deterministic, but it may miss unusual citation formats.
2. Support and quote verification use LLM when available, but fallback heuristics are used when model calls fail. This improves robustness but can reduce legal nuance.
3. CourtListener/web retrieval is opportunistic and best-effort. In failure cases, the system intentionally returns `could_not_verify` instead of over-claiming.

## What worked well

1. Agent decomposition is clear and non-overlapping.
2. The `/analyze` response is structured and UI-consumable.
3. Eval metrics are reproducible and include a concrete hallucination check tied to evidence anchors.

## Gaps and limitations

1. Tier 2 cross-document factual consistency checks are not yet implemented.
2. Tier 3 judicial memo and confidence calibration layering are not implemented.
3. Retrieval quality can vary by source availability and search result quality.
4. Current confidence values are useful but not yet statistically calibrated.

## If I had more time

1. Implement `CrossDocumentConsistencyAgent` with claim extraction and contradiction detection.
2. Add richer authority retrieval adapters (opinion text APIs + robust HTML extraction).
3. Add more adversarial eval fixtures and regression tests around failure modes.
4. Add calibrated confidence post-processing and threshold tuning with held-out eval cases.
5. Add deeper frontend drill-down for evidence spans and side-by-side quote/source comparison.
