#!/usr/bin/env python3
"""Calibration Comparison Tool — diffs baseline vs candidate classifier outputs.

Produces a divergence report showing where LLM/updated classifier disagrees
with the keyword baseline. Divergences become labeled test cases for the
eval harness. Convergences become regression anchors.

Usage:
    python -m eval.compare \
      --baseline data/eval_shadow/golden_dataset.json \
      --candidate data/logs/triage_results_20260806_135132.json \
      --output data/eval_shadow/divergence_report.md
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def load_baseline(path: str) -> dict[str, dict]:
    """Load golden dataset indexed by paper_id."""
    data = json.loads(Path(path).read_text())
    return {p["paper_id"]: p for p in data.get("papers", [])}


def load_candidate(path: str) -> dict[str, dict]:
    """Load shadow run results indexed by paper_id."""
    data = json.loads(Path(path).read_text())
    return {r["paper_id"]: r for r in data.get("top_n", [])}


def compare(baseline_path: str, candidate_path: str, output_path: Optional[str] = None) -> dict:
    """Compare baseline (golden) against candidate (shadow) classifier output.

    Args:
        baseline_path: Path to golden_dataset.json from the production flight.
        candidate_path: Path to triage_results_*.json from the shadow run.
        output_path: Optional path for a markdown divergence report.

    Returns:
        dict with comparison results including divergences and convergences.
    """
    baseline = load_baseline(baseline_path)
    candidate = load_candidate(candidate_path)

    if not baseline:
        return {"error": "Empty baseline dataset"}
    # Empty candidate is valid — all baseline papers are missing_in_candidate

    divergences = []
    convergences = []
    missing_in_candidate = []
    extra_in_candidate = []

    for paper_id, base in baseline.items():
        cand = candidate.get(paper_id)

        if cand is None:
            missing_in_candidate.append({
                "paper_id": paper_id,
                "title": base["title"],
                "baseline_classification": base["classification"],
            })
            continue

        # Compare classification
        class_match = base["classification"] == cand.get("classification", "")
        score_delta = abs(base["relevance_score"] - cand.get("relevance_score", 0))

        # Normalize threads: baseline stores thread_id strings, candidate stores dicts
        cand_threads_raw = cand.get("threads", [])
        cand_thread_ids = set(
            t["thread_id"] if isinstance(t, dict) else t
            for t in cand_threads_raw
        )
        base_thread_ids = set(base.get("threads", []))
        thread_overlap = len(base_thread_ids & cand_thread_ids)
        base_thread_count = len(base_thread_ids)
        thread_match_rate = thread_overlap / max(base_thread_count, 1)
        claims_base = len(base.get("claims", []))
        claims_cand = len(cand.get("claims", []))

        entry = {
            "paper_id": paper_id,
            "title": base["title"],
            "baseline_classification": base["classification"],
            "candidate_classification": cand.get("classification", "unknown"),
            "baseline_score": base["relevance_score"],
            "candidate_score": cand.get("relevance_score", 0),
            "score_delta": round(score_delta, 4),
            "thread_overlap": thread_overlap,
            "thread_match_rate": round(thread_match_rate, 4),
            "claims_baseline": claims_base,
            "claims_candidate": claims_cand,
            "classification_match": class_match,
            "baseline_classifier": base.get("classifier", "unknown"),
            "baseline_model": base.get("model_version", "unknown"),
            "candidate_classifier": cand.get("classifier", "keyword"),
            "candidate_model": cand.get("model_version", "keyword_v1"),
        }

        # Divergence criteria:
        #   - Different classification, OR
        #   - Score delta > 0.15, OR
        #   - Thread match rate < 0.5
        if not class_match:
            entry["divergence_reason"] = f"classification: {base['classification']} → {cand.get('classification', 'unknown')}"
            divergences.append(entry)
        elif score_delta > 0.15:
            entry["divergence_reason"] = f"score_delta: {score_delta:.2f}"
            divergences.append(entry)
        elif thread_match_rate < 0.5:
            entry["divergence_reason"] = f"thread_match: {thread_match_rate:.0%}"
            divergences.append(entry)
        else:
            convergences.append(entry)

    # Check for papers in candidate but not in baseline
    for paper_id in candidate:
        if paper_id not in baseline:
            extra_in_candidate.append({
                "paper_id": paper_id,
                "title": candidate[paper_id].get("title", "unknown"),
                "candidate_classification": candidate[paper_id].get("classification", "unknown"),
            })

    result = {
        "compared_at": datetime.now(timezone.utc).isoformat(),
        "baseline_path": baseline_path,
        "candidate_path": candidate_path,
        "baseline_classifier": list(baseline.values())[0].get("classifier", "unknown") if baseline else "unknown",
        "candidate_classifier": list(candidate.values())[0].get("classifier", "keyword") if candidate else "keyword",
        "total_baseline": len(baseline),
        "total_candidate": len(candidate),
        "matched_papers": len(baseline) - len(missing_in_candidate),
        "divergences": len(divergences),
        "divergence_entries": divergences,
        "convergences": len(convergences),
        "convergence_entries": convergences,
        "missing_in_candidate": missing_in_candidate,
        "extra_in_candidate": extra_in_candidate,
        "divergence_rate": round(len(divergences) / max(len(baseline), 1), 4),
        "convergence_rate": round(len(convergences) / max(len(baseline), 1), 4),
    }

    if output_path:
        _write_report(result, output_path)

    return result


def _write_report(result: dict, output_path: str):
    """Write a markdown divergence report."""
    lines = [
        "# Calibration Divergence Report",
        "",
        f"**Generated:** {result['compared_at']}",
        f"**Baseline:** {result['baseline_classifier']} classifier ({Path(result['baseline_path']).name})",
        f"**Candidate:** {result['candidate_classifier']} classifier ({Path(result['candidate_path']).name})",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Papers compared | {result['matched_papers']} |",
        f"| Convergences | {result['convergences']} ({result['convergence_rate']:.0%}) |",
        f"| Divergences | {result['divergences']} ({result['divergence_rate']:.0%}) |",
        f"| Missing in candidate | {len(result['missing_in_candidate'])} |",
        f"| Extra in candidate | {len(result['extra_in_candidate'])} |",
        "",
    ]

    if result["divergence_entries"]:
        lines.append("## Divergences (Labeled Test Cases)")
        lines.append("")
        lines.append("| Paper | Baseline | Candidate | Reason |")
        lines.append("|-------|----------|-----------|--------|")
        for d in result["divergence_entries"]:
            lines.append(
                f"| {d['paper_id']} | {d['baseline_classification']} ({d['baseline_score']:.2f}) "
                f"| {d['candidate_classification']} ({d['candidate_score']:.2f}) "
                f"| {d['divergence_reason']} |"
            )
        lines.append("")

    if result["convergence_entries"]:
        lines.append("## Convergences (Regression Anchors)")
        lines.append("")
        lines.append("| Paper | Classification | Score | Thread Match |")
        lines.append("|-------|---------------|-------|-------------|")
        for c in result["convergence_entries"]:
            lines.append(
                f"| {c['paper_id']} | {c['baseline_classification']} "
                f"| {c['baseline_score']:.2f} → {c['candidate_score']:.2f} "
                f"| {c['thread_match_rate']:.0%} |"
            )
        lines.append("")

    if result["missing_in_candidate"]:
        lines.append("## Missing in Candidate")
        lines.append("")
        for m in result["missing_in_candidate"]:
            lines.append(f"- {m['paper_id']}: {m['title']} (baseline: {m['baseline_classification']})")
        lines.append("")

    if result["extra_in_candidate"]:
        lines.append("## Extra in Candidate (Not in Baseline)")
        lines.append("")
        for e in result["extra_in_candidate"]:
            lines.append(f"- {e['paper_id']}: {e['title']} (candidate: {e['candidate_classification']})")
        lines.append("")

    lines.append("## Action Items")
    lines.append("")
    if result["divergences"] > 0:
        lines.append(f"1. Manually review {result['divergences']} divergences. Correct if LLM hallucinated; accept if keyword was wrong.")
    if result["convergences"] > 0:
        lines.append(f"2. Promote {result['convergences']} convergences to regression anchors in eval harness.")
    lines.append("3. Re-run comparison after classifier update to verify no regressions.")
    lines.append("")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(
        description="Compare baseline vs candidate classifier outputs for calibration.",
    )
    parser.add_argument("--baseline", required=True, help="Path to golden dataset JSON")
    parser.add_argument("--candidate", required=True, help="Path to shadow run triage results JSON")
    parser.add_argument("--output", default=None, help="Optional path for markdown divergence report")
    args = parser.parse_args()

    result = compare(args.baseline, args.candidate, args.output)

    # Print summary
    if "error" in result:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    print(f"Compared: {result['matched_papers']} papers")
    print(f"  Convergences: {result['convergences']} ({result['convergence_rate']:.0%})")
    print(f"  Divergences:  {result['divergences']} ({result['divergence_rate']:.0%})")

    if result["divergence_entries"]:
        print(f"\nDivergences (labeled test cases):")
        for d in result["divergence_entries"]:
            print(f"  {d['paper_id']}: {d['baseline_classification']} → {d['candidate_classification']} ({d['divergence_reason']})")

    if result["convergence_entries"]:
        print(f"\nConvergences (regression anchors):")
        for c in result["convergence_entries"]:
            print(f"  {c['paper_id']}: {c['baseline_classification']} ({c['baseline_score']:.2f})")

    if args.output:
        print(f"\nReport: {args.output}")

    if result["divergences"] > 0:
        sys.exit(0)  # Divergences exist but not an error — they're expected signals
    sys.exit(0)


if __name__ == "__main__":
    main()
