# Reflection

## 1) Problem decomposition into agents

I intentionally used a typed DAG with single-purpose agents rather than a free-form supervisor. The final production flow is:

`ingest -> citation/quote extraction -> authority retrieval -> citation support verification -> quote verification -> fact claim extraction -> cross-document consistency -> confidence calibration -> judicial memo -> report assembly`

What I think this got right:

1. Agent responsibilities are non-overlapping and easy to reason about.
2. Every stage communicates through explicit Pydantic models (no raw prose handoffs).
3. Per-step timing and error boundaries made partial success possible instead of all-or-nothing failure.

What I gave up:

1. Less adaptive behavior than a planner/supervisor architecture.
2. More boilerplate for schemas and conversions.

## 2) Prompt precision

I kept prompts short, label-constrained, and JSON-only. The verifier prompts force the model to:

1. Use only supplied evidence.
2. Emit explicit uncertainty (`could_not_verify`) when context is missing.
3. Stay concise (short reasons) and evidence-anchored.

This reduced format drift, but there is still model variance on borderline semantic support judgments.

## 3) Eval approach and what it measures

I used deterministic gold fixtures and scored what matters for this challenge:

1. Precision/recall for defect flagging.
2. Hallucination rate for evidence-anchor integrity.
3. Task split metrics (`citation_quote` vs `cross_document`) and macro roll-up.
4. Contract checks:
   - confidence fields present/bounded with reason
   - judicial memo structure + valid supporting finding IDs

Latest run:

1. Precision: `0.9286`
2. Recall: `1.0000`
3. Hallucination rate: `0.0000`
4. Confidence contract pass rate: `1.0000`
5. Memo contract pass: `true`

Honest read: recall is strong on this fixture set, but precision is not perfect (1 false positive remains), which is acceptable but signals threshold/rule tuning opportunity.

## 4) How far I got through the spec

Implemented:

1. Single-path API/runtime flow.
2. Confidence calibration agent with deterministic adjustment rules and reasons.
3. Judicial memo agent with LLM-first generation and deterministic fallback.
4. Structured UI rendering for memo + confidence fields.
5. Eval harness and tests, including contract checks.

Not implemented:

1. Learned/statistical calibration on held-out datasets.
2. More sophisticated retrieval providers beyond current approach.
3. Rich memo quality scoring beyond structural contract checks.

## 5) Tradeoffs and remaining gaps

1. Calibration is heuristic and transparent, but not statistically calibrated.
2. Cross-document contradiction checks are precision-first and may miss subtle inconsistencies.
3. Citation support quality is coupled to retrieval quality; upstream source failures can push outcomes to `could_not_verify`.
4. Memo quality is bounded by finding quality and ranking logic; template fallback is reliable but less nuanced.

## 6) What I would do next

1. Build held-out calibration fixtures and tune confidence rule weights from observed FP/FN patterns.
2. Add memo factuality/coverage evals that score sentence-level grounding against supporting finding IDs.
3. Expand cross-document fixtures with adversarial phrasing, temporal ambiguity, and mixed-support cases.
4. Add UI evidence drill-down (motion span + external span side-by-side) to speed human review.

## 7) Operational notes (kept here intentionally)

These implementation details were intentionally not kept in README.

1. Current API endpoint in this repo is `POST /analyze` on `http://localhost:8002` during normal local runs.
2. Current frontend dev server runs at `http://localhost:5175`.
3. Eval command is `python3 run_evals.py`.
4. Active eval fixtures are `backend/evals/fixtures/gold.json` and `backend/evals/fixtures/authority_overrides.json`.
5. Report mode tag is `final` and contract metric key is `contract_checks`.
