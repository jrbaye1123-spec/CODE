"""Application layer — governed answer surface for the epistemic control plane.

Applications:
  curate  — Interactive curation console for the knowledge engineer
  ask     — Governed RAG: answer only from index-eligible sources
  evidence — Audit pack: prove why an answer was given
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from curation.gate import EpistemicGate
from curation.queue import generate_queue
from curation.repair import add_provenance_frontmatter


def _default_expiry(days: int = 90) -> str:
    """Default exception expiry: 90 days from now."""
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d")


# ═══════════════════════════════════════════════════════════
# 1. CURATION CONSOLE
# ═══════════════════════════════════════════════════════════

def curate_file(vault_path: str, file_path: str, reviewer: str = "@knowledge-engineer",
                decision: str = "review", source_id: str = "") -> dict:
    """Curate a single file through the review workflow.

    Args:
        vault_path: Root of the vault.
        file_path: Relative path to the file.
        reviewer: @handle of the reviewer.
        decision: verify, exception, quarantine, or skip.
        source_id: Source registry ID if verifying.

    Returns:
        Dict with curation result.
    """
    vault = Path(vault_path)
    full_path = vault / file_path

    if not full_path.exists():
        return {"error": f"File not found: {file_path}", "status": "not_found"}

    import frontmatter

    try:
        post = frontmatter.load(str(full_path))
    except Exception as e:
        return {"error": f"Parse failed: {e}", "status": "parse_failed", "file": file_path}

    metadata = post.metadata or {}

    result = {
        "file": file_path,
        "decision": decision,
        "reviewer": reviewer,
        "reviewed_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "previous_status": metadata.get("provenance_status", "missing"),
    }

    if decision == "verify":
        if not source_id:
            return {"error": "source_id required for verify decision", "status": "missing_source_id"}

        metadata["provenance_status"] = "complete"
        metadata["provenance_level"] = "verified"
        metadata["source"] = f'"{source_id}"'
        metadata["reviewer"] = f'"{reviewer}"'
        metadata["reviewed_at"] = result["reviewed_at"]
        result["status"] = "verified"

    elif decision == "exception":
        metadata["provenance_status"] = "exception"
        metadata["provenance_level"] = "exception"
        metadata["reviewer"] = f'"{reviewer}"'
        metadata["reviewed_at"] = result["reviewed_at"]
        metadata["exception_owner"] = f'"{reviewer}"'
        metadata["exception_expires_at"] = _default_expiry()
        metadata["exception_reason"] = '"Pending full provenance review"'
        result["status"] = "exception"

    elif decision == "quarantine":
        metadata["provenance_status"] = "quarantined"
        metadata["provenance_level"] = "unknown"
        metadata["reviewer"] = f'"{reviewer}"'
        metadata["reviewed_at"] = result["reviewed_at"]
        result["status"] = "quarantined"

    elif decision == "skip":
        result["status"] = "skipped"
        return result

    else:
        return {"error": f"Unknown decision: {decision}", "status": "unknown_decision"}

    # Write the updated frontmatter
    new_content = frontmatter.dumps(post)
    full_path.write_text(new_content)

    # Run the gate
    gate = EpistemicGate(vault_path)
    gate_result = gate.scan_file(file_path)
    result["gate_passed"] = gate_result.passed
    result["gate_details"] = {
        "parse_failed": gate_result.parse_failed_count,
        "missing_fields": gate_result.missing_field_count,
        "eligible": gate_result.eligible_count,
    }

    return result


def curate_interactive(vault_path: str, directory: str = None, reviewer: str = "@knowledge-engineer"):
    """Interactive curation console — guides the knowledge engineer through the queue.

    Usage:
        python -m apps.curate /path/to/vault --dir wiki/agents
    """
    # Generate queue
    queue_data = generate_queue(vault_path, directory=directory)
    items = queue_data["items"]

    if not items:
        print("\n  ✅ No files in curation queue. All clear.")
        return

    print()
    print("=" * 60)
    print("  CURATION CONSOLE")
    print("=" * 60)
    print(f"  Queue: {len(items)} files")
    print(f"  Reviewer: {reviewer}")
    print()

    curated = 0
    skipped = 0

    for i, item in enumerate(items, 1):
        print(f"  [{i}/{len(items)}] {item['file']}")
        print(f"  Priority: {item['priority']} | Reason: {item['reason']}")
        print(f"  Action needed: {item['action']}")
        print()

        # Auto-skip parse failures (need repair first)
        if item["priority"] == 1:
            print(f"  ⚠ Parse failure — run repair first. Skipping.")
            print(f"     python -m curation.repair {vault_path} --file {item['file']} --fix")
            skipped += 1
            print()
            continue

        # Show missing fields
        if "field" in item:
            print(f"  Missing: {item['field']}")
            print()

        # Prompt for decision
        print(f"  Decisions:")
        print(f"    [v] verify  — approve with source ID")
        print(f"    [e] exception — time-boxed use")
        print(f"    [q] quarantine — remove from index path")
        print(f"    [s] skip     — come back later")
        print()

        choice = input(f"  Choose [v/e/q/s]: ").strip().lower()

        if choice == "v":
            source_id = input(f"  Source registry ID: ").strip()
            if not source_id:
                print(f"  ⚠ Source ID required. Skipping.")
                skipped += 1
                continue
            result = curate_file(vault_path, item["file"], reviewer=reviewer,
                                decision="verify", source_id=source_id)
        elif choice == "e":
            result = curate_file(vault_path, item["file"], reviewer=reviewer,
                                decision="exception")
        elif choice == "q":
            result = curate_file(vault_path, item["file"], reviewer=reviewer,
                                decision="quarantine")
        else:
            print(f"  Skipped.")
            skipped += 1
            print()
            continue

        if result.get("error"):
            print(f"  ❌ Error: {result['error']}")
            skipped += 1
        else:
            gate_icon = "✅" if result.get("gate_passed") else "❌"
            print(f"  {gate_icon} {result['status']} — gate {'passed' if result.get('gate_passed') else 'blocked'}")
            curated += 1

        print()

    print(f"  {'─' * 50}")
    print(f"  Curated: {curated} | Skipped: {skipped} | Total: {len(items)}")
    print(f"  {'=' * 60}")


# ═══════════════════════════════════════════════════════════
# 2. GOVERNED RAG GATEWAY
# ═══════════════════════════════════════════════════════════

def governed_ask(query: str, vault_path: str, directory: str = "wiki/agents",
                 provider: str = "keyword", model: str = "") -> dict:
    """Answer a query only from index-eligible sources.

    If no governed source exists for the query, returns a refusal with provenance_level: none.
    This is the core governed answer surface.

    Args:
        query: The question to answer.
        vault_path: Path to the vault.
        directory: Directory to search for governed sources.
        provider: LLM provider (keyword for no API key).
        model: Model name.

    Returns:
        Dict with answer, provenance_level, sources, and gate_status.
    """
    vault = Path(vault_path)

    # Find index-eligible sources
    gate = EpistemicGate(vault_path)
    gate_result = gate.scan_directory(directory) if directory else gate.scan()

    eligible_sources = gate_result.eligible

    if not eligible_sources:
        return {
            "answer": None,
            "provenance_level": "none",
            "response": "No governed source available for this query. The index has no eligible entries.",
            "sources": [],
            "gate_status": "no_eligible_sources",
            "query": query,
        }

    # Search eligible sources for relevant content
    relevant = []
    query_lower = query.lower()
    query_terms = set(query_lower.split())

    for source in eligible_sources:
        try:
            source_path = vault / source["file"]
            if not source_path.exists():
                continue

            content = source_path.read_text(encoding="utf-8", errors="replace")
            content_lower = content.lower()

            # Simple relevance: term overlap
            term_hits = sum(1 for t in query_terms if t in content_lower)
            if term_hits >= 2:
                # Extract relevant excerpt
                excerpt = _extract_relevant_excerpt(content, query_terms, max_chars=1000)
                relevant.append({
                    "file": source["file"],
                    "status": source.get("status", "complete"),
                    "degraded": source.get("degraded", False),
                    "excerpt": excerpt,
                    "relevance": term_hits / max(len(query_terms), 1),
                })
        except Exception:
            continue

    if not relevant:
        return {
            "answer": None,
            "provenance_level": "verified",
            "response": (
                f"No governed source matched the query '{query}'. "
                f"{len(eligible_sources)} index-eligible sources exist but none are relevant to this question."
            ),
            "sources": [s["file"] for s in eligible_sources],
            "eligible_sources_count": len(eligible_sources),
            "gate_status": "no_relevant_source",
            "query": query,
        }

    # Sort by relevance
    relevant.sort(key=lambda r: r["relevance"], reverse=True)

    # Build answer from relevant sources
    best = relevant[0]
    provenance_level = "degraded" if best["degraded"] else "verified"

    # If using LLM provider, generate answer
    if provider != "keyword":
        try:
            from llm import create_provider
            llm = create_provider(provider, model=model)
            if llm:
                context = "\n\n".join(r["excerpt"] for r in relevant[:3])
                prompt = f"""Answer this question using ONLY the governed source material below.
If the sources don't contain enough information, say so.

Question: {query}

Governed sources:
{context}

Return JSON: {{"answer": "...", "confidence": 0.0-1.0, "used_sources": ["file1", "file2"]}}"""

                response = llm.classify("Query", prompt, [])
                try:
                    data = json.loads(response.content)
                    generated_answer = data.get("answer", "")
                except json.JSONDecodeError:
                    generated_answer = response.content[:500]
            else:
                generated_answer = _build_keyword_answer(query, relevant)
        except Exception:
            generated_answer = _build_keyword_answer(query, relevant)
    else:
        generated_answer = _build_keyword_answer(query, relevant)

    return {
        "answer": generated_answer,
        "provenance_level": provenance_level,
        "sources": [r["file"] for r in relevant[:3]],
        "source_count": len(relevant),
        "eligible_sources_count": len(eligible_sources),
        "gate_status": "passed" if gate_result.passed else "blocked",
        "query": query,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _extract_relevant_excerpt(content: str, query_terms: set, max_chars: int = 1000) -> str:
    """Extract the most relevant excerpt from content."""
    content_lower = content.lower()
    best_start = 0
    best_score = 0

    # Sliding window scoring
    window = 500
    for i in range(0, len(content) - window, 100):
        chunk = content_lower[i:i + window]
        score = sum(1 for t in query_terms if t in chunk)
        if score > best_score:
            best_score = score
            best_start = max(0, i - 50)

    if best_score == 0:
        return content[:max_chars]

    return content[best_start:best_start + max_chars]


def _build_keyword_answer(query: str, relevant: list[dict]) -> str:
    """Build a keyword-based answer from relevant source excerpts."""
    parts = [f"Query: {query}\n"]
    parts.append("Answer based on governed sources:\n")

    for i, r in enumerate(relevant[:3], 1):
        parts.append(f"[Source {i}: {r['file']}]")
        parts.append(r["excerpt"][:300])
        parts.append("")

    parts.append(f"provenance_level: {'degraded' if any(r['degraded'] for r in relevant[:3]) else 'verified'}")
    parts.append(f"sources_used: {len(relevant[:3])}")
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════
# 3. AUDIT / EVIDENCE PACK
# ═══════════════════════════════════════════════════════════

def generate_evidence_pack(query: str, vault_path: str, directory: str = "wiki/agents") -> dict:
    """Generate an audit evidence pack for a query.

    Produces a complete governance trail: what sources were used, were they
    index-eligible, who reviewed them, gate status, audit chain verification.

    Args:
        query: The question asked.
        vault_path: Path to the vault.
        directory: Directory searched.

    Returns:
        Dict with full evidence pack.
    """
    vault = Path(vault_path)

    # Get the governed ask response
    ask_result = governed_ask(query, vault_path, directory)

    # Get gate status
    gate = EpistemicGate(vault_path)
    gate_result = gate.scan_directory(directory) if directory else gate.scan()

    # Verify audit chain
    from observability import IndexHealthMonitor
    monitor = IndexHealthMonitor()
    audit_verification = monitor.verify_audit_chain()

    # Build source details
    source_details = []
    for source_file in ask_result.get("sources", []):
        try:
            source_path = vault / source_file
            if source_path.exists():
                import frontmatter
                post = frontmatter.load(str(source_path))
                meta = post.metadata or {}
                source_details.append({
                    "file": source_file,
                    "provenance_status": meta.get("provenance_status", "unknown"),
                    "provenance_level": meta.get("provenance_level", "unknown"),
                    "reviewer": meta.get("reviewer", "unknown"),
                    "reviewed_at": meta.get("reviewed_at", "unknown"),
                    "source": meta.get("source", "unknown"),
                })
            else:
                source_details.append({
                    "file": source_file,
                    "error": "file_not_found",
                })
        except Exception as e:
            source_details.append({
                "file": source_file,
                "error": str(e),
            })

    return {
        "evidence_pack": {
            "query": query,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "answer": ask_result,
            "sources_detail": source_details,
            "gate": {
                "passed": gate_result.passed,
                "total_files": gate_result.total_files,
                "eligible": gate_result.eligible_count,
                "rejected": gate_result.rejected_count,
                "parse_failures": gate_result.parse_failed_count,
                "missing_fields": gate_result.missing_field_count,
            },
            "audit_chain": {
                "verified": audit_verification["verified"],
                "entries": audit_verification["entries"],
            },
            "exceptions": _get_active_exceptions(),
            "governance_status": "complete" if ask_result["provenance_level"] == "verified" else "degraded",
        }
    }


def _get_active_exceptions() -> list[dict]:
    """Get active exceptions from the exception register."""
    exceptions_file = Path("data/logs/exceptions.jsonl")
    if not exceptions_file.exists():
        return []

    active = []
    with open(exceptions_file) as f:
        for line in f:
            exc = json.loads(line)
            if not exc.get("expired", False):
                active.append(exc)
    return active


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Epistemic Control Plane — Governed Answer Surface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Applications:
  curate    Interactive curation console
  ask       Governed RAG: answer from index-eligible sources only
  evidence  Audit pack: full governance trail for any query

Examples:
  python -m apps curate --vault /path/to/vault --dir wiki/agents
  python -m apps ask "What is the index eligibility rule?" --vault /path/to/vault
  python -m apps evidence "What is the index eligibility rule?" --vault /path/to/vault
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Application to run")

    # curate
    curate_parser = subparsers.add_parser("curate", help="Interactive curation console")
    curate_parser.add_argument("--vault", required=True, help="Path to vault")
    curate_parser.add_argument("--dir", default=None, help="Limit to directory")
    curate_parser.add_argument("--reviewer", default="@knowledge-engineer", help="Reviewer handle")
    curate_parser.add_argument("--batch", action="store_true", help="Batch mode: auto-skip parse failures")
    curate_parser.add_argument("--verify", default=None, help="Quick-verify a single file with source ID")
    curate_parser.add_argument("--file", default=None, help="File to curate (with --verify)")

    # ask
    ask_parser = subparsers.add_parser("ask", help="Governed RAG query")
    ask_parser.add_argument("query", help="Question to answer from governed sources")
    ask_parser.add_argument("--vault", required=True, help="Path to vault")
    ask_parser.add_argument("--dir", default="wiki/agents", help="Directory to search")
    ask_parser.add_argument("--provider", default="keyword", help="LLM provider")
    ask_parser.add_argument("--model", default="", help="Model name")
    ask_parser.add_argument("--provenance", action="store_true", default=True, help="Show provenance")

    # evidence
    evidence_parser = subparsers.add_parser("evidence", help="Generate audit evidence pack")
    evidence_parser.add_argument("query", help="Question to generate evidence for")
    evidence_parser.add_argument("--vault", required=True, help="Path to vault")
    evidence_parser.add_argument("--dir", default="wiki/agents", help="Directory to search")
    evidence_parser.add_argument("--json", action="store_true", help="Output JSON")

    args = parser.parse_args()

    if args.command == "curate":
        if args.verify and args.file:
            result = curate_file(args.vault, args.file, reviewer=args.reviewer,
                                decision="verify", source_id=args.verify)
            print(json.dumps(result, indent=2))
        else:
            curate_interactive(args.vault, directory=args.dir, reviewer=args.reviewer)

    elif args.command == "ask":
        result = governed_ask(args.query, args.vault, directory=args.dir,
                             provider=args.provider, model=args.model)
        print()
        print("=" * 60)
        print("  GOVERNED ANSWER")
        print("=" * 60)

        if result["answer"] is None:
            print(f"  ❌ {result['response']}")
        else:
            print(f"  {result['answer'][:500]}")

        print()
        print(f"  Provenance:   {result['provenance_level'].upper()}")
        print(f"  Sources:      {len(result.get('sources', []))}")
        print(f"  Eligible:     {result.get('eligible_sources_count', 0)} index entries")
        if result.get("sources"):
            for s in result["sources"]:
                print(f"    → {s}")
        print(f"  Gate:         {result['gate_status']}")
        print("=" * 60)
        print()

    elif args.command == "evidence":
        result = generate_evidence_pack(args.query, args.vault, directory=args.dir)

        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            ep = result["evidence_pack"]
            print()
            print("=" * 60)
            print("  AUDIT EVIDENCE PACK")
            print("=" * 60)
            print(f"  Query:            {ep['query']}")
            print(f"  Generated:        {ep['generated_at']}")
            print(f"  Governance:       {ep['governance_status'].upper()}")
            print()
            print(f"  ── ANSWER ──")
            ans = ep["answer"]
            print(f"  Provenance:       {ans['provenance_level'].upper()}")
            print(f"  Sources found:    {ans.get('source_count', 0)}")
            print(f"  Eligible sources: {ans.get('eligible_sources_count', 0)}")
            print()
            print(f"  ── GATE ──")
            print(f"  Passed:           {ep['gate']['passed']}")
            print(f"  Eligible:         {ep['gate']['eligible']}")
            print(f"  Rejected:         {ep['gate']['rejected']}")
            print()
            print(f"  ── AUDIT CHAIN ──")
            print(f"  Verified:         {ep['audit_chain']['verified']}")
            print(f"  Entries:          {ep['audit_chain']['entries']}")
            print()
            if ep["sources_detail"]:
                print(f"  ── SOURCE DETAILS ──")
                for sd in ep["sources_detail"]:
                    print(f"  📄 {sd['file']}")
                    print(f"     status: {sd.get('provenance_status', '?')}")
                    print(f"     level:  {sd.get('provenance_level', '?')}")
                    print(f"     reviewer: {sd.get('reviewer', '?')}")
            print()
            print(f"  ── EXCEPTIONS ──")
            print(f"  Active: {len(ep.get('exceptions', []))}")
            print("=" * 60)
            print()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
