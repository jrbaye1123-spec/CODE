#!/usr/bin/env python3
"""
retrieval_dissent — Audit agent for retrieval diversity.

Surfaces what the main retrieval pipeline excluded:
  - Non-English sources
  - Low-prestige sources (preprint, institutional, self-published)
  - Underrepresented intellectual traditions
  - Non-Western geographic traditions

Usage:
  python retrieval_dissent.py --query "quantum biology and consciousness"
  python retrieval_dissent.py --query "autonomic nervous system empathy" --top-n 30

Designed to plug into a retrieval agent. Currently operates on a source
catalog or CSV input for demonstration. When integrated with a live retrieval
pipeline, replace _mock_retrieve() with the actual retrieval call.

Constitution Reference: Requirement 4.5 — Retrieval Dissent Agent (design consideration).
"""

import argparse
import json
import sys
from collections import Counter
from typing import List, Dict


# ── Mock retrieval — replace with actual retrieval agent call ──────────────

def _mock_retrieve(query: str, top_n: int = 30) -> List[Dict]:
    """
    MOCK: Simulates a retrieval agent returning results.
    Replace this with an actual call to the vault retrieval agent.

    Expected return format: list of dicts with at minimum:
      - title: str
      - language: str (ISO 639-1 or name)
      - geographic_tradition: str
      - prestige_signal: str (peer_reviewed, preprint, institutional, self_published, unknown)
      - intellectual_tradition: str
    """
    # In production: call retrieval agent, return top_n results
    # For now: return empty list with a notice
    print("⚠️  Retrieval dissent agent is operating in mock mode.", file=sys.stderr)
    print("   To use with live data, replace _mock_retrieve() with actual retrieval call.", file=sys.stderr)
    print("   See /governance/retrieval-bias-review.md for manual audit procedure.", file=sys.stderr)
    print(file=sys.stderr)
    return []


# ── Analysis ───────────────────────────────────────────────────────────────

def analyze_diversity(results: List[Dict]) -> Dict:
    """Analyze top-N results for diversity gaps."""
    if not results:
        return {
            "status": "no_data",
            "message": "No results to analyze. Run with live retrieval data.",
        }

    n = len(results)

    # Language diversity
    languages = Counter(r.get("language", "unknown") for r in results)
    non_english = sum(v for k, v in languages.items() if k != "en" and k != "english")
    non_english_pct = (non_english / n) * 100

    # Geographic diversity
    geographies = Counter(r.get("geographic_tradition", "unknown") for r in results)
    non_western = sum(v for k, v in geographies.items()
                      if k not in ("Western", "unknown"))

    # Prestige diversity
    prestige = Counter(r.get("prestige_signal", "unknown") for r in results)
    non_peer_reviewed = sum(v for k, v in prestige.items()
                            if k not in ("peer_reviewed",))

    # Intellectual tradition diversity
    traditions = Counter(r.get("intellectual_tradition", "unknown") for r in results)
    n_traditions = len([k for k, v in traditions.items() if v > 0 and k != "unknown"])

    # Gap assessment
    gaps = []
    if non_english_pct < 10:
        gaps.append(f"Non-English sources: {non_english_pct:.1f}% (threshold: 10%)")
    if n_traditions < 3:
        gaps.append(f"Intellectual traditions represented: {n_traditions} (threshold: 3)")
    if non_western == 0:
        gaps.append("Zero non-Western geographic traditions in top results")

    status = "ok"
    if non_english_pct < 5 and n_traditions < 3:
        status = "critical"
    elif gaps:
        status = "warning"

    return {
        "status": status,
        "total_results": n,
        "languages": dict(languages.most_common()),
        "non_english_pct": round(non_english_pct, 1),
        "geographic_traditions": dict(geographies.most_common()),
        "prestige_signals": dict(prestige.most_common()),
        "non_peer_reviewed": non_peer_reviewed,
        "intellectual_traditions": dict(traditions.most_common()),
        "n_traditions": n_traditions,
        "gaps": gaps,
        "recommendations": _generate_recommendations(gaps, languages, traditions),
    }


def _generate_recommendations(gaps: List[str], languages: Counter,
                              traditions: Counter) -> List[str]:
    """Generate actionable recommendations from detected gaps."""
    recs = []
    if gaps:
        recs.append("Supplement retrieval with manual source search in underrepresented areas.")
    if "Non-English sources" in " ".join(gaps):
        dominant = languages.most_common(1)[0][0] if languages else "unknown"
        recs.append(f"Retrieval is dominated by {dominant}-language sources. "
                     "Add non-English database queries or translation pipeline.")
    if "traditions" in " ".join(gaps).lower():
        recs.append("Consider adding a retrieval dissent agent to the pipeline "
                     "to systematically flag excluded sources.")
    if not recs:
        recs.append("Retrieval diversity is within acceptable thresholds.")
    return recs


# ── CLI ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Retrieval Dissent Agent — Audit retrieval diversity")
    parser.add_argument("--query", "-q", required=True,
                        help="Research query to audit")
    parser.add_argument("--top-n", "-n", type=int, default=30,
                        help="Number of top results to analyze (default: 30)")
    parser.add_argument("--output", "-o",
                        help="Output file for report (default: stdout)")
    parser.add_argument("--json", action="store_true",
                        help="Output as JSON instead of formatted report")
    args = parser.parse_args()

    results = _mock_retrieve(args.query, args.top_n)
    report = analyze_diversity(results)
    report["query"] = args.query
    report["top_n"] = args.top_n

    if args.json:
        output = json.dumps(report, indent=2)
    else:
        output = _format_report(report)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Report saved to {args.output}", file=sys.stderr)
    else:
        print(output)

    sys.exit(0 if report["status"] == "ok" else 1)


def _format_report(report: Dict) -> str:
    """Format the audit report for human reading."""
    lines = [
        "=" * 60,
        f"RETRIEVAL DISSENT AUDIT",
        f"Query: {report.get('query', '')}",
        f"Results analyzed: {report.get('total_results', 0)}",
        f"Status: {report.get('status', 'unknown').upper()}",
        "=" * 60,
        "",
    ]

    if report.get("status") == "no_data":
        lines.append(report.get("message", "No data."))
        lines.append("")
        lines.append("To run a manual audit:")
        for item in [
            "1. Select 3 representative research queries",
            "2. Retrieve top 30 results per query",
            "3. Tag each by language and intellectual tradition",
            "4. Compute coverage rates",
            "5. Document gaps in /governance/retrieval-bias-review.md",
        ]:
            lines.append(f"   {item}")
        return "\n".join(lines)

    lines.append("Language Diversity:")
    for lang, count in report.get("languages", {}).items():
        lines.append(f"  {lang}: {count}")
    lines.append(f"  Non-English: {report.get('non_english_pct', 0)}%")
    lines.append("")

    lines.append("Geographic Traditions:")
    for geo, count in report.get("geographic_traditions", {}).items():
        lines.append(f"  {geo}: {count}")
    lines.append("")

    lines.append("Intellectual Traditions:")
    for trad, count in report.get("intellectual_traditions", {}).items():
        lines.append(f"  {trad}: {count}")
    lines.append(f"  Distinct traditions: {report.get('n_traditions', 0)}")
    lines.append("")

    lines.append("Prestige Signals:")
    for sig, count in report.get("prestige_signals", {}).items():
        lines.append(f"  {sig}: {count}")
    lines.append("")

    gaps = report.get("gaps", [])
    if gaps:
        lines.append("GAPS DETECTED:")
        for g in gaps:
            lines.append(f"  ⚠️  {g}")
    else:
        lines.append("No diversity gaps detected.")
    lines.append("")

    recs = report.get("recommendations", [])
    if recs:
        lines.append("Recommendations:")
        for r in recs:
            lines.append(f"  → {r}")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
