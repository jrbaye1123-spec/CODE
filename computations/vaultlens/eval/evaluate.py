"""Evaluation harness: measures retrieval quality against golden queries.

Provides run, report, and compare commands for VaultLens v0.2.
"""

import sqlite3
import json
import time
import uuid
import sys
from pathlib import Path
from typing import Optional

from vaultlens.retriever import retrieve, bm25_search
from vaultlens.graph_store import GraphStore
from vaultlens.query_router import detect_variants
from vaultlens.parser import _generate_note_id


def load_golden_queries(path: str) -> list[dict]:
    """Load golden queries from a JSON or YAML file.

    Uses JSON parsing. YAML falls back to simple line-based parser.
    """
    with open(path, "r") as f:
        content = f.read()

    # Try JSON first
    if path.endswith(".json"):
        queries = json.loads(content)
        for q in queries:
            if "expected_notes" in q and isinstance(q["expected_notes"], str):
                q["expected_notes"] = [n.strip() for n in q["expected_notes"].split(",")]
        return queries

    # Fallback: simple YAML parser
    return _parse_yaml_queries(content)


def _parse_yaml_queries(content: str) -> list[dict]:
    """Simple YAML parser for golden queries."""
    queries = []
    current_query: dict = {}
    current_list: Optional[list] = None
    current_list_name: str = ""

    for line in content.split("\n"):
        stripped = line.rstrip()
        if stripped.startswith("#") or not stripped.strip():
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0 and stripped.startswith("- id:"):
            if current_query:
                queries.append(current_query)
            current_query = {"id": stripped[5:].strip()}
            current_list = None
        elif indent == 2 and not stripped.startswith("- "):
            if ":" in stripped:
                key, _, value = stripped.partition(":")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key == "query":
                    current_query["query"] = value
                else:
                    current_query[key] = value
                current_list = None
        elif indent == 4 and stripped.startswith("- "):
            if current_list is not None and current_list_name:
                current_list.append(stripped[2:].strip().strip('"').strip("'"))
        elif indent == 2 and stripped.startswith("expected_"):
            name = stripped.rstrip(":").strip()
            current_list_name = name
            current_list = []
            current_query[name] = current_list

    if current_query:
        queries.append(current_query)
    return queries


def run_evaluation(db_path: str, queries_yaml: str = "eval/golden_queries.yaml",
                   tag: Optional[str] = None, verbose: bool = False) -> str:
    """Run evaluation against golden queries.

    Args:
        db_path: Path to SQLite database
        queries_yaml: Path to golden queries YAML
        tag: Optional tag for this run (default: auto-generated)
        verbose: Print progress

    Returns:
        run_id string
    """
    run_id = tag or f"run-{uuid.uuid4().hex[:8]}"

    # Load golden queries
    golden = load_golden_queries(queries_yaml)
    if not golden:
        print("Error: No golden queries found.")
        return run_id

    # Connect
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    graph = GraphStore(conn)
    graph.load()

    if verbose:
        print(f"Running evaluation '{run_id}' on {len(golden)} queries...")

    results = []
    total_latency = 0.0

    for gq in golden:
        qid = gq["id"]
        query_text = gq["query"]
        expected_variants = gq.get("expected_variants", [])
        expected_notes = gq.get("expected_notes", [])
        expected_edges = gq.get("expected_edges", [])

        # Detect variants
        detected = detect_variants(query_text)

        # Variant routing correct if detected[0] is in expected
        variant_correct = 1 if (not expected_variants or detected[0] in expected_variants) else 0

        # Run retrieval
        t0 = time.time()
        result = retrieve(
            conn, graph, query_text,
            variants=detected[:3],
            max_hops=2,
            max_notes=25,
            explain=False,
            verbose=False,
        )
        latency = (time.time() - t0) * 1000
        total_latency += latency

        retrieved_notes = result.get("retrieved_notes", [])
        retrieved_note_titles = [n.get("title", "") for n in retrieved_notes]
        retrieved_note_ids = [n["note_id"] for n in retrieved_notes]
        retrieved_edges = result.get("edges", [])

        # Node recall: fraction of expected notes found
        expected_slugs = {_generate_note_id(n) for n in expected_notes}
        found_slugs = expected_slugs & set(retrieved_note_ids)
        node_recall = len(found_slugs) / len(expected_slugs) if expected_slugs else 1.0

        # Edge recall: fraction of expected edges found
        edge_hits = 0
        for ee in expected_edges:
            ee_src = _generate_note_id(ee["source"])
            ee_tgt = _generate_note_id(ee["target"])
            ee_rel = ee["relation"]
            for re in retrieved_edges:
                if (re["source_note_id"] == ee_src and
                    re["target_note_id"] == ee_tgt and
                    re["relation"] == ee_rel):
                    edge_hits += 1
                    break
        edge_recall = edge_hits / len(expected_edges) if expected_edges else 1.0

        # Precision@k (k = number of retrieved notes if < len(expected) else len(expected))
        k = min(len(retrieved_notes), max(len(expected_notes), 1))
        precision = len(found_slugs) / k if k > 0 else 0.0

        if verbose:
            print(f"  {qid}: node_recall={node_recall:.2f} edge_recall={edge_recall:.2f} latency={latency:.1f}ms")

        results.append({
            "query_id": qid,
            "query": query_text,
            "variant_routing_correct": variant_correct,
            "node_recall": node_recall,
            "edge_recall": edge_recall,
            "path_hit": 0,  # path-based scoring to be added
            "precision_at_k": precision,
            "latency_ms": latency,
            "retrieved_note_ids": json.dumps(retrieved_note_ids[:20]),
            "retrieved_edges": json.dumps([
                {"s": e["source_note_id"], "t": e["target_note_id"], "r": e["relation"]}
                for e in retrieved_edges[:20]
            ]),
        })

    # Store run in database
    avg_latency = total_latency / len(golden) if golden else 0
    metrics = {
        "num_queries": len(golden),
        "variant_routing_accuracy": sum(r["variant_routing_correct"] for r in results) / len(results),
        "node_recall_at_10": sum(r["node_recall"] for r in results) / len(results),
        "edge_recall": sum(r["edge_recall"] for r in results) / len(results),
        "path_hit_rate": 0.0,
        "precision_at_k": sum(r["precision_at_k"] for r in results) / len(results),
        "average_latency_ms": round(avg_latency, 1),
    }

    conn.execute("""
        INSERT INTO eval_runs (run_id, tag, config, metrics)
        VALUES (?, ?, ?, ?)
    """, (run_id, tag or run_id, json.dumps({"queries_yaml": queries_yaml}), json.dumps(metrics)))

    for r in results:
        conn.execute("""
            INSERT INTO eval_results (run_id, query_id, query, variant_routing_correct,
                                      node_recall, edge_recall, path_hit, precision_at_k,
                                      latency_ms, retrieved_note_ids, retrieved_edges)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id, r["query_id"], r["query"], r["variant_routing_correct"],
            r["node_recall"], r["edge_recall"], r["path_hit"], r["precision_at_k"],
            r["latency_ms"], r["retrieved_note_ids"], r["retrieved_edges"],
        ))

    conn.commit()
    conn.close()

    return run_id


def print_report(db_path: str, run_id: Optional[str] = None) -> None:
    """Print evaluation report for a run or the latest run."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    if run_id:
        cursor = conn.execute("SELECT * FROM eval_runs WHERE run_id = ?", (run_id,))
    else:
        cursor = conn.execute("SELECT * FROM eval_runs ORDER BY created_at DESC LIMIT 1")

    run = cursor.fetchone()
    if not run:
        print("No evaluation runs found.")
        conn.close()
        return

    metrics = json.loads(run["metrics"])
    config = json.loads(run["config"])

    print(f"\n{'='*60}")
    print(f"  VaultLens Evaluation Report")
    print(f"{'='*60}")
    print(f"  Run:          {run['run_id']}")
    print(f"  Tag:          {run['tag']}")
    print(f"  Created:      {run['created_at']}")
    print(f"  Queries:      {metrics['num_queries']}")
    print(f"  Config:       {config.get('queries_yaml', 'N/A')}")
    print()
    print(f"  Metrics:")
    print(f"    Variant Routing Accuracy:  {metrics['variant_routing_accuracy']:.2f}")
    print(f"    Node Recall@10:            {metrics['node_recall_at_10']:.2f}")
    print(f"    Edge Recall:               {metrics['edge_recall']:.2f}")
    print(f"    Path Hit Rate:             {metrics['path_hit_rate']:.2f}")
    print(f"    Precision@k:               {metrics['precision_at_k']:.2f}")
    print(f"    Avg Latency:               {metrics['average_latency_ms']:.1f} ms")

    # Per-query details
    cursor = conn.execute("SELECT * FROM eval_results WHERE run_id = ?", (run["run_id"],))
    print(f"\n  Per-Query Results:")
    for row in cursor:
        icon = "✓" if row["node_recall"] > 0.5 else "✗"
        print(f"    {icon} {row['query_id']:30s} node={row['node_recall']:.2f} edge={row['edge_recall']:.2f}")

    print(f"{'='*60}\n")
    conn.close()


def compare_runs(db_path: str, run_a: str, run_b: str) -> None:
    """Compare two evaluation runs."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    cursor = conn.execute("SELECT * FROM eval_runs WHERE run_id = ?", (run_a,))
    run1 = cursor.fetchone()
    cursor = conn.execute("SELECT * FROM eval_runs WHERE run_id = ?", (run_b,))
    run2 = cursor.fetchone()

    if not run1 or not run2:
        print(f"Error: Could not find both runs ({run_a}, {run_b})")
        conn.close()
        return

    m1 = json.loads(run1["metrics"])
    m2 = json.loads(run2["metrics"])

    print(f"\n{'='*60}")
    print(f"  Evaluation Comparison")
    print(f"{'='*60}")
    print(f"  {run_a:30s} → {run_b}")
    print()
    print(f"  {'Metric':<30s} {'Before':>8s} {'After':>8s} {'Delta':>8s}")
    print(f"  {'-'*54}")

    for key, label in [
        ("variant_routing_accuracy", "Variant Accuracy"),
        ("node_recall_at_10", "Node Recall@10"),
        ("edge_recall", "Edge Recall"),
        ("path_hit_rate", "Path Hit Rate"),
        ("precision_at_k", "Precision@k"),
        ("average_latency_ms", "Latency (ms)"),
    ]:
        v1 = m1[key]
        v2 = m2[key]
        delta = v2 - v1
        sign = "+" if delta > 0 else ""
        if "latency" in key:
            sign = "+" if delta > 0 else ""
        print(f"  {label:<30s} {v1:>8.2f} {v2:>8.2f} {sign}{delta:>7.2f}")

    print(f"{'='*60}\n")
    conn.close()


def list_runs(db_path: str) -> None:
    """List all evaluation runs."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    cursor = conn.execute("SELECT run_id, tag, created_at FROM eval_runs ORDER BY created_at DESC")
    runs = list(cursor)
    conn.close()

    if not runs:
        print("No evaluation runs found.")
        return

    print(f"\n{'='*60}")
    print(f"  Evaluation Runs")
    print(f"{'='*60}")
    for row in runs:
        print(f"  {row['run_id']:20s}  {row['tag']:15s}  {row['created_at']}")
    print(f"{'='*60}\n")
