#!/usr/bin/env python3
"""VaultLens CLI: Multi-Variant GraphRAG without the single-vector bottleneck.

Usage:
    python -m vaultlens index /path/to/vault
    python -m vaultlens query "What causes demand drop?"
    python -m vaultlens stats
    python -m vaultlens export --format json
"""

import argparse
import os
import sqlite3
import sys
import json

from .indexer import index_vault, print_stats
from .graph_store import GraphStore
from .query_router import analyze_query, detect_variants
from .retriever import retrieve
from .serializer import serialize_context, serialize_json
from .proposer import propose_from_text, EdgeProposal
from .parser import parse_note, RELATION_TO_VARIANT, _generate_note_id


def cmd_index(args) -> None:
    """Index a vault of markdown notes."""
    vault_path = os.path.abspath(args.vault_path)
    if not os.path.isdir(vault_path):
        print(f"Error: '{args.vault_path}' is not a directory", file=sys.stderr)
        sys.exit(1)

    db_path = args.db_path or os.path.join(vault_path, ".vaultlens", "vaultlens.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    print(f"Indexing vault: {vault_path}")
    print(f"Database: {db_path}")

    stats = index_vault(
        vault_path=vault_path,
        db_path=db_path,
        rebuild=args.rebuild,
        verbose=args.verbose,
    )
    print_stats(stats)


def cmd_query(args) -> None:
    """Query the vault."""
    db_path = args.db_path or ".vaultlens/vaultlens.db"
    if not os.path.exists(db_path):
        print(f"Error: No database found at '{db_path}'. Run 'index' first.", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row

    graph = GraphStore(conn)

    # Determine variants
    variants = None
    if args.variants:
        variants = [v.strip() for v in args.variants.split(",")]

    # If explain requested, analyze query first
    if args.explain:
        analysis = analyze_query(args.query, verbose=True)
        if variants is None:
            variants = analysis["variants"]

    result = retrieve(
        conn=conn,
        graph=graph,
        query=args.query,
        variants=variants,
        max_hops=args.max_hops,
        max_notes=args.max_notes,
        explain=args.explain,
        verbose=args.verbose,
    )

    if args.json:
        print(serialize_json(result))
    else:
        print(serialize_context(result))

    if args.explain and result.get("explanation"):
        print(result["explanation"])

    conn.close()


def cmd_stats(args) -> None:
    """Show graph statistics."""
    db_path = args.db_path or ".vaultlens/vaultlens.db"
    if not os.path.exists(db_path):
        print(f"Error: No database found at '{db_path}'. Run 'index' first.", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    graph = GraphStore(conn)
    graph.load()
    stats = graph.get_stats()

    print(f"\n{'='*60}")
    print(f"  VaultLens Graph Statistics")
    print(f"{'='*60}")
    print(f"  Total notes:     {stats.total_notes:>6d}")
    print(f"  Total edges:     {stats.total_edges:>6d}")
    print(f"  Unresolved:      {stats.unresolved_links:>6d}")
    print(f"  DB size:         {os.path.getsize(db_path) / (1024*1024):.2f} MB")
    print(f"\n  Variants:")
    for variant, count in sorted(stats.variant_counts.items(),
                                  key=lambda x: x[1], reverse=True):
        print(f"    {variant:20s} {count:>8d}")
    print(f"\n  Top Connected Notes:")
    for title, nid, count in stats.top_connected:
        print(f"    [{count:3d}] {title} ({nid})")
    print(f"{'='*60}\n")

    conn.close()


def cmd_export(args) -> None:
    """Export the graph."""
    db_path = args.db_path or ".vaultlens/vaultlens.db"
    if not os.path.exists(db_path):
        print(f"Error: No database found at '{db_path}'. Run 'index' first.", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    fmt = args.format or "json"

    if fmt == "json":
        # Export notes + edges as JSON
        notes = []
        for row in conn.execute("SELECT * FROM notes"):
            notes.append({
                "note_id": row["note_id"],
                "file_path": row["file_path"],
                "title": row["title"],
                "aliases": json.loads(row["aliases"] or "[]"),
                "tags": json.loads(row["tags"] or "[]"),
                "note_type": row["note_type"],
            })

        edges = []
        for row in conn.execute("SELECT * FROM edges WHERE resolved = 1"):
            edges.append({
                "source": row["source_note_id"],
                "target": row["target_note_id"],
                "relation": row["relation"],
                "variant": row["variant"],
                "confidence": row["confidence"],
            })

        output = json.dumps({"notes": notes, "edges": edges}, indent=2)
        if args.output:
            with open(args.output, "w") as f:
                f.write(output)
            print(f"Exported to {args.output} ({len(notes)} notes, {len(edges)} edges)")
        else:
            print(output)

    elif fmt == "csv":
        # Export edges as CSV
        output_lines = ["source_note_id,target_note_id,relation,variant,confidence"]
        for row in conn.execute("SELECT * FROM edges WHERE resolved = 1"):
            output_lines.append(
                f"{row['source_note_id']},{row['target_note_id']},"
                f"{row['relation']},{row['variant']},{row['confidence']}"
            )
        output = "\n".join(output_lines)
        if args.output:
            with open(args.output, "w") as f:
                f.write(output)
            print(f"Exported to {args.output} ({len(output_lines)-1} edges)")
        else:
            print(output)

    elif fmt == "graphml":
        # Export as GraphML (basic)
        lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        lines.append('<graphml xmlns="http://graphml.graphdrawing.org/xmlns">')
        lines.append('  <graph id="vaultlens" edgedefault="directed">')
        for row in conn.execute("SELECT * FROM notes"):
            lines.append(f'    <node id="{row["note_id"]}">')
            lines.append(f'      <data key="title">{row["title"]}</data>')
            lines.append(f'      <data key="type">{row["note_type"]}</data>')
            lines.append('    </node>')
        for row in conn.execute("SELECT * FROM edges WHERE resolved = 1"):
            lines.append(
                f'    <edge source="{row["source_note_id"]}" target="{row["target_note_id"]}">'
            )
            lines.append(f'      <data key="relation">{row["relation"]}</data>')
            lines.append(f'      <data key="variant">{row["variant"]}</data>')
            lines.append('    </edge>')
        lines.append('  </graph>')
        lines.append('</graphml>')
        output = "\n".join(lines)
        if args.output:
            with open(args.output, "w") as f:
                f.write(output)
            print(f"Exported to {args.output}")
        else:
            print(output)

    conn.close()


def cmd_propose(args) -> None:
    """Generate edge proposals from vault notes."""
    db_path = args.db_path or ".vaultlens/vaultlens.db"
    vault_path = args.vault_path
    if not os.path.isdir(vault_path):
        print(f"Error: '{vault_path}' is not a directory", file=sys.stderr)
        sys.exit(1)

    # Find vault DB
    if not os.path.exists(db_path):
        alt_db = os.path.join(vault_path, ".vaultlens", "vaultlens.db")
        if os.path.exists(alt_db):
            db_path = alt_db

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Get all notes
    notes = list(conn.execute("SELECT note_id, title, body FROM notes"))

    allowed_variants = None
    if args.variants:
        allowed_variants = set(v.strip() for v in args.variants.split(","))

    mode = args.mode or "heuristic"
    total_proposals = 0

    for row in notes:
        body = row["body"]
        title = row["title"]
        note_id = row["note_id"]

        proposals = propose_from_text(
            body=body,
            title=title,
            mode=mode,
            min_confidence=args.min_confidence,
            allowed_variants=allowed_variants,
        )

        for p in proposals:
            # Check for duplicates
            existing = conn.execute(
                "SELECT COUNT(*) FROM proposals WHERE proposal_id = ?",
                (p.proposal_id,)
            ).fetchone()[0]
            if existing:
                continue

            conn.execute("""
                INSERT INTO proposals (proposal_id, source_note_id, source_title,
                    target_title, relation, variant, confidence, evidence_span,
                    rationale, proposer, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """, (
                p.proposal_id, note_id, p.source_title, p.target_title,
                p.relation, p.variant, p.confidence, p.evidence_span,
                p.rationale, p.proposer,
            ))
            total_proposals += 1

    conn.commit()
    print(f"Generated {total_proposals} new proposals from {len(notes)} notes (mode={mode})")

    # Show top proposals
    if total_proposals > 0 and not args.quiet:
        cursor = conn.execute(
            "SELECT * FROM proposals WHERE status='pending' ORDER BY confidence DESC LIMIT 5"
        )
        print("\nTop proposals:")
        for p in cursor:
            print(f"  [{p['confidence']:.2f}] {p['source_title']} --{p['relation']}--> {p['target_title']} ({p['variant']})")

    conn.close()


def cmd_review(args) -> None:
    """Interactive proposal review."""
    from .review_cli import review_proposals
    db_path = args.db_path or ".vaultlens/vaultlens.db"
    if not os.path.exists(db_path):
        alt_db = os.path.join(args.vault_path, ".vaultlens", "vaultlens.db") if args.vault_path else None
        if alt_db and os.path.exists(alt_db):
            db_path = alt_db
        else:
            print(f"Error: No database found at '{db_path}'.", file=sys.stderr)
            sys.exit(1)

    review_proposals(db_path, write_markdown=args.write_markdown)


def cmd_eval(args) -> None:
    """Run evaluation commands."""
    from eval.evaluate import run_evaluation, print_report, compare_runs, list_runs

    db_path = args.db_path or ".vaultlens/vaultlens.db"
    if not os.path.exists(db_path):
        print(f"Error: No database found at '{db_path}'.", file=sys.stderr)
        sys.exit(1)

    action = args.eval_action

    if action == "run":
        yaml_path = args.queries or "eval/golden_queries.yaml"
        tag = args.tag or None
        run_id = run_evaluation(db_path, yaml_path, tag=tag, verbose=args.verbose)
        print(f"Evaluation run '{run_id}' complete.")
        print_report(db_path, run_id)

    elif action == "report":
        print_report(db_path, args.run_id)

    elif action == "compare":
        if not args.run_a or not args.run_b:
            print("Error: --run-a and --run-b required for compare", file=sys.stderr)
            sys.exit(1)
        compare_runs(db_path, args.run_a, args.run_b)

    elif action == "list":
        list_runs(db_path)

    else:
        print(f"Unknown eval action: {action}")


def main():
    parser = argparse.ArgumentParser(
        description="VaultLens: Multi-Variant GraphRAG without the single-vector bottleneck",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Index command
    index_parser = subparsers.add_parser("index", help="Index a vault of markdown notes")
    index_parser.add_argument("vault_path", help="Path to directory containing .md files")
    index_parser.add_argument("--db-path", help="Path to SQLite database")
    index_parser.add_argument("--rebuild", action="store_true", help="Rebuild index from scratch")
    index_parser.add_argument("--verbose", action="store_true", help="Verbose output")

    # Query command
    query_parser = subparsers.add_parser("query", help="Query the vault")
    query_parser.add_argument("query", help="Natural language query")
    query_parser.add_argument("--db-path", help="Path to SQLite database")
    query_parser.add_argument("--variants", help="Comma-separated variant override (e.g., causal,evidential)")
    query_parser.add_argument("--max-hops", type=int, default=2, help="Max graph traversal depth")
    query_parser.add_argument("--max-notes", type=int, default=25, help="Max notes to return")
    query_parser.add_argument("--explain", action="store_true", help="Show retrieval explanation")
    query_parser.add_argument("--json", action="store_true", help="Output as JSON")
    query_parser.add_argument("--verbose", action="store_true", help="Verbose output")

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show graph statistics")
    stats_parser.add_argument("--db-path", help="Path to SQLite database")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export the graph")
    export_parser.add_argument("--db-path", help="Path to SQLite database")
    export_parser.add_argument("--format", choices=["json", "csv", "graphml"], default="json")
    export_parser.add_argument("--output", help="Output file path")

    # v0.2: Propose command
    propose_parser = subparsers.add_parser("propose", help="Generate edge proposals from notes")
    propose_parser.add_argument("vault_path", help="Path to vault directory")
    propose_parser.add_argument("--db-path", help="Path to SQLite database")
    propose_parser.add_argument("--mode", choices=["heuristic", "llm"], default="heuristic")
    propose_parser.add_argument("--min-confidence", type=float, default=0.5)
    propose_parser.add_argument("--variants", help="Filter by variants (comma-separated)")
    propose_parser.add_argument("--limit", type=int, default=0)
    propose_parser.add_argument("--quiet", action="store_true")

    # v0.2: Review command
    review_parser = subparsers.add_parser("review", help="Review pending proposals interactively")
    review_parser.add_argument("--db-path", help="Path to SQLite database")
    review_parser.add_argument("--vault-path", help="Path to vault (auto-detects DB)")
    review_parser.add_argument("--write-markdown", action="store_true", help="Write approved edges to markdown")

    # v0.2: Eval command
    eval_parser = subparsers.add_parser("eval", help="Evaluation commands")
    eval_parser.add_argument("eval_action", choices=["run", "report", "compare", "list"])
    eval_parser.add_argument("--db-path", help="Path to SQLite database")
    eval_parser.add_argument("--queries", help="Path to golden queries YAML")
    eval_parser.add_argument("--tag", help="Tag for this evaluation run")
    eval_parser.add_argument("--run-id", help="Run ID for report")
    eval_parser.add_argument("--run-a", help="First run for comparison")
    eval_parser.add_argument("--run-b", help="Second run for comparison")
    eval_parser.add_argument("--verbose", action="store_true")

    args = parser.parse_args()

    if args.command == "index":
        cmd_index(args)
    elif args.command == "query":
        cmd_query(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "export":
        cmd_export(args)
    elif args.command == "propose":
        cmd_propose(args)
    elif args.command == "review":
        cmd_review(args)
    elif args.command == "eval":
        cmd_eval(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
