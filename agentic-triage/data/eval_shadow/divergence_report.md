# Calibration Divergence Report

**Generated:** 2026-08-06T13:52:15.537442+00:00
**Baseline:** keyword classifier (golden_dataset.json)
**Candidate:** keyword classifier (triage_results_20260806_135132.json)

## Summary

| Metric | Value |
|--------|-------|
| Papers compared | 4 |
| Convergences | 4 (100%) |
| Divergences | 0 (0%) |
| Missing in candidate | 0 |
| Extra in candidate | 0 |

## Convergences (Regression Anchors)

| Paper | Classification | Score | Thread Match |
|-------|---------------|-------|-------------|
| 2608.05131v1 | multimodal_learning | 0.50 → 0.50 | 100% |
| 2608.05141v1 | scalable_oversight | 0.43 → 0.43 | 100% |
| 2608.05144v1 | reasoning_planning | 0.38 → 0.38 | 100% |
| 2608.05138v1 | multimodal_learning | 0.33 → 0.33 | 100% |

## Action Items

2. Promote 4 convergences to regression anchors in eval harness.
3. Re-run comparison after classifier update to verify no regressions.
