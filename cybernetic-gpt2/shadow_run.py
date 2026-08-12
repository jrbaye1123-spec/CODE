#!/usr/bin/env python3
"""Shadow Run — Daily governed triage pipeline that proves itself.

Runs the full epistemic supply chain against real arXiv papers every day.
Produces evidence packs suitable for investor decks, cold email attachments,
and compliance demonstrations.

Usage:
    python shadow_run.py                     # Run once now
    python shadow_run.py --schedule          # Set up daily cron
    python shadow_run.py --report           # Generate weekly report from logs
    python shadow_run.py --evidence-pack    # Generate investor-ready evidence
"""

import sys
import os
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/../agentic-triage")

SHADOW_DIR = Path(os.path.expanduser("~/shadow-run"))
SHADOW_DIR.mkdir(parents=True, exist_ok=True)

VAULT = os.path.expanduser("~/workspace/rbaye/vault")


# ═══════════════════════════════════════════════════════════
# DAILY SHADOW RUN
# ═══════════════════════════════════════════════════════════

def run_daily_shadow(categories: list[str] = None, max_papers: int = 10):
    """Run one day's shadow triage pipeline.
    
    Fetches papers from arXiv, runs the full governed pipeline,
    and stores all outputs in the shadow directory.
    """
    if categories is None:
        categories = ["cs.AI", "cs.CL", "cs.LG"]

    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    run_dir = SHADOW_DIR / f"run_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print(f"  SHADOW RUN — {run_id}")
    print("=" * 60)
    print()

    # --- 1. Gate check before anything ---
    print("[1/7] Gate health check...")
    gate_result = _run_command([
        "venv/bin/python", "-m", "curation.gate", VAULT, "--dir", "wiki/agents", "--json"
    ])
    (run_dir / "gate_check.json").write_text(gate_result.stdout)
    gate_data = json.loads(gate_result.stdout)
    gate_ok = gate_data.get("passed", False)
    print(f"  Gate: {'✅ PASSED' if gate_ok else '⛔ BLOCKED'}")
    print(f"  Eligible: {gate_data.get('eligible', 0)}, Rejected: {gate_data.get('rejected', 0)}")
    print()

    # --- 2. Fetch papers ---
    print(f"[2/7] Fetching papers from arXiv categories: {categories}...")
    venv = Path(os.path.dirname(os.path.abspath(__file__))) / "../agentic-triage/venv"
    
    from sources import ArxivSource
    source = ArxivSource()
    papers = []
    for cat in categories:
        try:
            cat_papers = source.fetch_recent(cat, max_results=max_papers // len(categories) + 1)
            for p in cat_papers:
                papers.append({
                    "id": p.arxiv_id,
                    "title": p.title,
                    "text": p.abstract,
                    "source": f"https://arxiv.org/abs/{p.arxiv_id}",
                    "metadata": {"authors": p.authors, "categories": p.categories, "published": p.published},
                })
        except Exception as e:
            print(f"  ⚠ {cat}: {e}")
    
    print(f"  Fetched: {len(papers)} papers")
    (run_dir / "papers_fetched.json").write_text(json.dumps(papers, indent=2, default=str))
    print()

    # --- 3. Safety scan all papers ---
    print("[3/7] Safety scanning...")
    from safety.injection_scanner import InjectionScanner
    scanner = InjectionScanner()
    safe_papers = []
    blocked_papers = []
    for p in papers:
        result = scanner.scan(p["text"], source=p["source"])
        if result.passed:
            safe_papers.append(p)
        else:
            blocked_papers.append({
                "id": p["id"],
                "title": p["title"],
                "risk": result.risk_score,
                "patterns": result.flagged_patterns,
            })
    
    print(f"  Safe: {len(safe_papers)}, Blocked: {len(blocked_papers)}")
    if blocked_papers:
        (run_dir / "blocked_papers.json").write_text(json.dumps(blocked_papers, indent=2))
        for bp in blocked_papers:
            print(f"    🚫 {bp['title'][:60]}... (risk={bp['risk']:.2f})")
    print()

    # --- 4. Triage ---
    print("[4/7] Running triage pipeline...")
    from triage import LiteratureTriageAgent, TriageConfig, ResearchThread
    from memory import MemoryManager
    from provenance import ProvenanceTracker
    from ops import AgentOps
    from safety.policy_engine import PolicyEngine
    
    config = TriageConfig(
        top_n=5,
        relevance_threshold=0.3,
        allowed_sources=["arxiv.org", "export.arxiv.org"],
        research_threads=[
            ResearchThread("transformer_efficiency", "Transformer Efficiency",
                          "Parameter-efficient architectures, pruning, distillation, quantization",
                          ["transformer", "efficient", "pruning", "sparse", "distillation", "quantization", "lora"]),
            ResearchThread("alignment_safety", "AI Alignment & Safety",
                          "RLHF, constitutional AI, jailbreak defense, interpretability",
                          ["alignment", "safety", "RLHF", "jailbreak", "interpretability", "guardrails"]),
            ResearchThread("multimodal_learning", "Multimodal Learning",
                          "Vision-language, audio-visual, cross-modal retrieval",
                          ["multimodal", "vision", "language", "image", "CLIP", "cross-modal"]),
            ResearchThread("reasoning_planning", "Reasoning & Planning",
                          "Chain-of-thought, agent architectures, planning, code generation",
                          ["reasoning", "chain-of-thought", "planning", "agent", "tool", "code"]),
            ResearchThread("scalable_oversight", "Scalable Oversight",
                          "Evaluation, monitoring, debate, recursive reward modeling",
                          ["oversight", "evaluation", "debate", "benchmark", "scalable", "monitoring"]),
        ],
    )
    
    agent = LiteratureTriageAgent(
        config=config,
        memory_manager=MemoryManager(storage_path=str(run_dir / "memory")),
        provenance_tracker=ProvenanceTracker(storage_path=str(run_dir / "provenance")),
        ops_pipeline=AgentOps(storage_path=str(run_dir)),
        policy_engine=PolicyEngine(memory_path=str(run_dir / "memory")),
        injection_scanner=scanner,
    )
    
    output_data = agent.triage_with_provenance(safe_papers)
    results = output_data["results"]
    top_n = output_data["top_n"]
    
    print(f"  Triaged: {len(results)}, Top-N: {len(top_n)}")
    for i, r in enumerate(top_n, 1):
        print(f"    [{i}] {r.paper_title[:70]}...")
        print(f"        {r.classification} (score: {r.relevance_score:.2f})")
    print()

    # --- 5. Provenance ---
    print("[5/7] Attaching provenance labels...")
    provenance_verified = 0
    provenance_degraded = 0
    for r in results:
        if any("verified" in str(getattr(c, 'source_document', '')) for c in r.claims_extracted):
            provenance_verified += 1
        else:
            provenance_degraded += 1
    
    print(f"  Verified: {provenance_verified}, Degraded: {provenance_degraded}")
    (run_dir / "triage_results.json").write_text(json.dumps({
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "papers_fetched": len(papers),
        "papers_blocked": len(blocked_papers),
        "papers_triaged": len(results),
        "top_n": [
            {
                "title": r.paper_title,
                "classification": r.classification,
                "relevance_score": r.relevance_score,
                "summary": r.summary,
                "claims": len(r.claims_extracted),
            }
            for r in top_n
        ],
        "provenance_verified": provenance_verified,
        "provenance_degraded": provenance_degraded,
    }, indent=2, default=str))
    print()

    # --- 6. Observability ---
    print("[6/7] Recording health snapshot...")
    from observability import daily_health_check
    health = daily_health_check()
    (run_dir / "health_check.json").write_text(json.dumps(health, indent=2, default=str))
    print(f"  Eligibility Rate: {health['snapshot']['eligibility_rate']:.1%}")
    print(f"  Gate Status: {health['snapshot']['gate_status']}")
    print(f"  Audit Chain: {'✅ VERIFIED' if health['audit_chain_verified'] else '💔 BROKEN'}")
    print()

    # --- 7. Summary ---
    print("[7/7] Writing run summary...")
    summary = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gate_passed": gate_ok,
        "papers_fetched": len(papers),
        "papers_blocked_by_safety": len(blocked_papers),
        "papers_triaged": len(results),
        "top_classifications": list(set(r.classification for r in top_n)),
        "provenance_verified_outputs": provenance_verified,
        "provenance_degraded_outputs": provenance_degraded,
        "eligibility_rate": health['snapshot']['eligibility_rate'],
        "audit_chain_verified": health['audit_chain_verified'],
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    
    print(f"  ✅ Shadow run complete: {run_dir}")
    print(f"  {'=' * 60}")
    print()
    
    return summary


# ═══════════════════════════════════════════════════════════
# WEEKLY REPORT
# ═══════════════════════════════════════════════════════════

def generate_weekly_report():
    """Generate a weekly summary from shadow run logs. Investor-ready."""
    runs = sorted(SHADOW_DIR.glob("run_*"))
    if not runs:
        print("No shadow runs found. Run daily_shadow() first.")
        return
    
    # Collect summaries
    summaries = []
    for run_dir in runs[-7:]:  # Last 7 days
        summary_file = run_dir / "summary.json"
        if summary_file.exists():
            summaries.append(json.loads(summary_file.read_text()))
    
    if not summaries:
        print("No run summaries found.")
        return
    
    # Aggregate
    total_papers = sum(s["papers_fetched"] for s in summaries)
    total_triaged = sum(s["papers_triaged"] for s in summaries)
    total_blocked = sum(s["papers_blocked_by_safety"] for s in summaries)
    gate_passes = sum(1 for s in summaries if s["gate_passed"])
    all_classifications = set()
    for s in summaries:
        all_classifications.update(s.get("top_classifications", []))
    
    report = {
        "report_type": "weekly_shadow_run",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period": f"{summaries[0]['timestamp'][:10]} to {summaries[-1]['timestamp'][:10]}",
        "runs_completed": len(summaries),
        "total_papers_fetched": total_papers,
        "total_papers_triaged": total_triaged,
        "total_papers_blocked_by_safety": total_blocked,
        "gate_passes": f"{gate_passes}/{len(summaries)}",
        "active_research_threads": sorted(all_classifications),
        "average_eligibility_rate": sum(s["eligibility_rate"] for s in summaries) / len(summaries) if summaries else 0,
        "audit_chain_intact": all(s["audit_chain_verified"] for s in summaries),
        "daily_runs": summaries,
    }
    
    report_file = SHADOW_DIR / f"weekly_report_{datetime.now(timezone.utc).strftime('%Y%m%d')}.json"
    report_file.write_text(json.dumps(report, indent=2, default=str))
    
    print("=" * 60)
    print("  WEEKLY SHADOW RUN REPORT")
    print("=" * 60)
    print(f"  Period:    {report['period']}")
    print(f"  Runs:      {report['runs_completed']}")
    print(f"  Papers:    {total_papers} fetched, {total_triaged} triaged, {total_blocked} blocked")
    print(f"  Gate:      {report['gate_passes']} passes")
    print(f"  Threads:   {', '.join(sorted(all_classifications))}")
    print(f"  Eligibility: {report['average_eligibility_rate']:.1%}")
    print(f"  Audit:     {'✅ INTACT' if report['audit_chain_intact'] else '💔 BROKEN'}")
    print(f"  Saved:     {report_file}")
    print("=" * 60)
    
    return report


# ═══════════════════════════════════════════════════════════
# INVESTOR EVIDENCE PACK
# ═══════════════════════════════════════════════════════════

def generate_evidence_pack():
    """Generate an investor-ready evidence pack from all shadow runs."""
    from apps import generate_evidence_pack as gen_evidence
    
    runs = sorted(SHADOW_DIR.glob("run_*"))
    if not runs:
        print("No shadow runs found.")
        return
    
    latest = runs[-1]
    summary = json.loads((latest / "summary.json").read_text()) if (latest / "summary.json").exists() else {}
    
    # Evidence from the governed answer surface
    evidence = gen_evidence(
        "What governed knowledge does the system support?",
        VAULT,
        directory="wiki/agents"
    )
    
    pack = {
        "evidence_pack_type": "investor_demo",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "system_capabilities": {
            "gate_enforcement": "100% index eligibility rate required for production use",
            "safety_scanning": "Prompt-injection defense before any content enters agent context",
            "provenance_tracking": "Every claim traces to governed source with reviewer attribution",
            "audit_chain": "SHA-256 linked cryptographic audit trail, tamper-evident",
            "shadow_runs": len(runs),
            "latest_run": summary.get("run_id", "none"),
            "papers_processed": sum(
                json.loads((r / "summary.json").read_text()).get("papers_triaged", 0)
                for r in runs[-7:]
                if (r / "summary.json").exists()
            ),
        },
        "live_evidence": evidence,
        "differentiator": (
            "This is not a chatbot. This is a governed answer surface where every output "
            "is traceable to a verified source, reviewed by a knowledge engineer, and "
            "backed by cryptographic audit proof. The system says no when it should."
        ),
    }
    
    pack_file = SHADOW_DIR / f"investor_evidence_pack_{datetime.now(timezone.utc).strftime('%Y%m%d')}.json"
    pack_file.write_text(json.dumps(pack, indent=2, default=str))
    
    print("=" * 60)
    print("  INVESTOR EVIDENCE PACK")
    print("=" * 60)
    print(f"  Shadow runs:    {pack['system_capabilities']['shadow_runs']}")
    print(f"  Papers processed: {pack['system_capabilities']['papers_processed']}")
    print(f"  Gate:           {'PASSED' if evidence['evidence_pack']['gate']['passed'] else 'BLOCKED'}")
    print(f"  Audit chain:    {'✅ VERIFIED' if evidence['evidence_pack']['audit_chain']['verified'] else '💔 BROKEN'}")
    print(f"  Saved:          {pack_file}")
    print("=" * 60)
    
    return pack


# ═══════════════════════════════════════════════════════════
# CRON SETUP
# ═══════════════════════════════════════════════════════════

def setup_cron():
    """Print cron instructions for daily shadow runs."""
    script_path = Path(__file__).resolve()
    venv_python = str(Path(os.path.dirname(__file__)) / "../agentic-triage/venv/bin/python")
    
    cron_line = f"0 6 * * * cd {SHADOW_DIR.parent} && {venv_python} {script_path} >> {SHADOW_DIR}/cron.log 2>&1"
    
    print("=" * 60)
    print("  CRON SETUP")
    print("=" * 60)
    print()
    print("  Add this line to your crontab (crontab -e):")
    print()
    print(f"  {cron_line}")
    print()
    print("  This runs the shadow pipeline daily at 6:00 AM UTC,")
    print("  fetches the latest arXiv papers, triages them through")
    print("  the governed pipeline, and stores all evidence.")
    print()
    print("  Weekly report (add to crontab):")
    print(f"  0 9 * * MON cd {SHADOW_DIR.parent} && {venv_python} {script_path} --report")
    print("=" * 60)


# ═══════════════════════════════════════════════════════════
# UTILITY
# ═══════════════════════════════════════════════════════════

def _run_command(cmd: list[str]):
    """Run a command and return the CompletedProcess."""
    cwd = os.path.dirname(os.path.abspath(__file__)) + "/../agentic-triage"
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=60)


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Shadow Run — Governed AI evidence pipeline")
    parser.add_argument("--schedule", action="store_true", help="Show cron setup instructions")
    parser.add_argument("--report", action="store_true", help="Generate weekly report from logs")
    parser.add_argument("--evidence-pack", action="store_true", help="Generate investor evidence pack")
    parser.add_argument("--categories", default="cs.AI,cs.CL,cs.LG", help="arXiv categories (comma-separated)")
    parser.add_argument("--max-papers", type=int, default=10, help="Max papers to fetch")
    parser.add_argument("--run", action="store_true", default=True, help="Run daily shadow now")
    
    args = parser.parse_args()
    
    if args.schedule:
        setup_cron()
    elif args.report:
        generate_weekly_report()
    elif args.evidence_pack:
        generate_evidence_pack()
    else:
        categories = [c.strip() for c in args.categories.split(",")]
        run_daily_shadow(categories=categories, max_papers=args.max_papers)
        print()
        print("💡 Next: python shadow_run.py --report     (weekly summary)")
        print("💡 Next: python shadow_run.py --evidence-pack  (investor demo)")
        print("💡 Next: python shadow_run.py --schedule   (daily cron setup)")
