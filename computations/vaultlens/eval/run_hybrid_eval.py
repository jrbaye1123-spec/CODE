#!/usr/bin/env python3
"""Run hybrid eval for VaultLens Gate 1 — BM25 + vector seeds vs pure BM25.

Usage:
    .venv/bin/python3 eval/run_hybrid_eval.py [--suite original|paraphrase] [--tag TAG]
"""

import sys, os, json, sqlite3, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vaultlens.vector import FastEmbedder, VectorStore
from vaultlens.retrieval.hybrid import should_use_vector, fuse_seeds
from vaultlens.retrieval import retrieve_hybrid
from vaultlens.graph_store import GraphStore
from vaultlens.parser import _generate_note_id
from vaultlens.retriever import retrieve

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAULT_DB = os.path.join(BASE, "sample_vault/.vaultlens/vaultlens.db")
VECTOR_DB = os.path.join(BASE, "sample_vault/.vaultlens/vectors.db")
MODEL_ID = "bge-small-en-v1.5"

def load_queries(path):
    with open(path) as f:
        return json.load(f)

def run_hybrid_eval(suite_path, tag, use_hybrid=True):
    """Run eval with hybrid (or baseline) retrieval."""
    queries = load_queries(suite_path)
    conn = sqlite3.connect(VAULT_DB)
    conn.row_factory = sqlite3.Row
    graph = GraphStore(conn)
    graph.load()

    embedder = FastEmbedder("BAAI/bge-small-en-v1.5") if use_hybrid else None
    vstore = VectorStore(VECTOR_DB) if use_hybrid else None

    results = []
    total_lat = 0.0
    variant_correct = 0

    for gq in queries:
        qid = gq["id"]
        qtext = gq["query"]
        exp_variants = gq.get("expected_variants", [])
        exp_notes = gq.get("expected_notes", [])
        exp_edges = gq.get("expected_edges", [])

        t0 = time.time()

        if use_hybrid:
            from vaultlens.query_router import detect_variants
            detected = detect_variants(qtext)
            result = retrieve_hybrid(
                conn, graph, qtext,
                vector_store=vstore, embedder=embedder,
                vector_model_id=MODEL_ID,
                variants=detected[:3], max_hops=2, max_notes=25,
            )
        else:
            result = retrieve(conn, graph, qtext, max_hops=2, max_notes=25)

        lat = (time.time() - t0) * 1000
        total_lat += lat

        # Variant routing
        from vaultlens.query_router import detect_variants
        detected = detect_variants(qtext)
        vc = 1 if (not exp_variants or detected[0] in exp_variants) else 0
        variant_correct += vc

        # Node recall
        retrieved_ids = [n["note_id"] for n in result.get("retrieved_notes", [])]
        exp_slugs = {_generate_note_id(n) for n in exp_notes}
        found = exp_slugs & set(retrieved_ids)
        node_recall = len(found) / len(exp_slugs) if exp_slugs else 1.0

        # Edge recall
        retrieved_edges = result.get("edges", [])
        edge_hits = 0
        for ee in exp_edges:
            ee_src = _generate_note_id(ee["source"])
            ee_tgt = _generate_note_id(ee["target"])
            for re in retrieved_edges:
                if re["source_note_id"] == ee_src and re["target_note_id"] == ee_tgt:
                    edge_hits += 1
                    break
        edge_recall = edge_hits / len(exp_edges) if exp_edges else 1.0

        k = min(len(retrieved_ids), max(len(exp_notes), 1))
        precision = len(found) / k if k > 0 else 0.0

        vec_info = ""
        if use_hybrid:
            vc = result.get("vector_seed_count", 0)
            bc = result.get("bm25_seed_count", 0)
            sc = result.get("shared_seed_count", 0)
            vec_info = f" v={vc} b={bc} s={sc}"

        print(f"  {qid:40s} node={node_recall:.2f} edge={edge_recall:.2f} lat={lat:.1f}ms{vec_info}")
        results.append({
            "qid": qid, "node_recall": node_recall, "edge_recall": edge_recall,
            "precision": precision, "latency_ms": lat, "variant_correct": vc,
        })

    conn.close()
    if vstore: vstore.close()

    n = len(queries)
    print(f"\n{'='*60}")
    print(f"  {tag} ({n} queries, hybrid={'on' if use_hybrid else 'off'})")
    print(f"  Variant Accuracy: {variant_correct/n:.2f}")
    print(f"  Node Recall@10:   {sum(r['node_recall'] for r in results)/n:.2f}")
    print(f"  Edge Recall:      {sum(r['edge_recall'] for r in results)/n:.2f}")
    print(f"  Precision@k:      {sum(r['precision'] for r in results)/n:.2f}")
    print(f"  Avg Latency:      {total_lat/n:.1f}ms")
    print(f"{'='*60}")
    return results

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--suite", default="paraphrase", choices=["original", "paraphrase"])
    p.add_argument("--tag", default=None)
    p.add_argument("--baseline", action="store_true", help="Run pure BM25 baseline")
    args = p.parse_args()

    suite_file = os.path.join(BASE, f"eval/golden_{'paraphrase' if args.suite == 'paraphrase' else 'queries'}.json")
    mode = "baseline" if args.baseline else "hybrid"
    tag = args.tag or f"gate1-{mode}-{args.suite}"

    print(f"Suite: {suite_file}")
    print(f"Mode:  {mode}")
    print(f"Tag:   {tag}\n")

    run_hybrid_eval(suite_file, tag, use_hybrid=not args.baseline)
