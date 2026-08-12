# Calibration Divergence Report

**Generated:** 2026-08-06T13:55:36.130566+00:00
**Baseline:** keyword classifier (golden_dataset.json)
**Candidate:** keyword classifier (candidate_tweaked.json)

## Summary

| Metric | Value |
|--------|-------|
| Papers compared | 4 |
| Convergences | 2 (50%) |
| Divergences | 2 (50%) |
| Missing in candidate | 0 |
| Extra in candidate | 0 |

## Divergences (Labeled Test Cases)

| Paper | Baseline | Candidate | Reason |
|-------|----------|-----------|--------|
| 2608.05144v1 | reasoning_planning (0.38) | reasoning_planning (0.75) | score_delta: 0.38 |
| 2608.05138v1 | multimodal_learning (0.33) | alignment_safety (0.85) | classification: multimodal_learning → alignment_safety |

## Convergences (Regression Anchors)

| Paper | Classification | Score | Thread Match |
|-------|---------------|-------|-------------|
| 2608.05131v1 | multimodal_learning | 0.50 → 0.50 | 100% |
| 2608.05141v1 | scalable_oversight | 0.43 → 0.43 | 100% |

## Action Items

1. Manually review 2 divergences. Correct if LLM hallucinated; accept if keyword was wrong.
2. Promote 2 convergences to regression anchors in eval harness.
3. Re-run comparison after classifier update to verify no regressions.
