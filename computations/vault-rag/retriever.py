"""
Vault RAG Engine — Hybrid Retriever
====================================
Combines Kitadel keyword search with semantic embedding search for
the Obsidian vault. Reciprocal rank fusion merges results from both
backends into a single ranked list.

Architecture:
  Query → [Kitadel keyword] + [Semantic embeddings] → Fusion → Ranked results
                                              ↑
                                     .brain/embeddings.npz
"""

import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np

# ── Configuration ────────────────────────────────────────────────────
VAULT = Path.home() / "Desktop/backup-20260606/vault"
BRAIN = VAULT / ".brain"
KITADEL = Path.home() / "Documents/ObsidianVault/tools/kitadel/kitadel.py"

# Directories indexed for semantic search
INDEXED_DIRS = ["wiki", "knowledge", "decisions", "conversations", "output"]

# Fusion: weight between keyword (0) and semantic (1)
# 0.3 = 70% keyword, 30% semantic — keyword anchors, semantic broadens
FUSION_ALPHA = 0.3


class VaultRetriever:
    """
    Hybrid retrieval over the Obsidian vault.

    Usage:
        retriever = VaultRetriever()
        results = retriever.search("black hole information geometry", top_k=10)
        for r in results:
            print(f"{r['score']:.3f} | {r['path']} — {r['snippet']}")
    """

    def __init__(self):
        self._embeddings = None
        self._metadata = None
        self._model = None
        self._model_name = None
        self._loaded = False

    # ── Lazy loading ────────────────────────────────────────────────

    def _ensure_loaded(self):
        if self._loaded:
            return
        self._load_embeddings()
        self._load_model()
        self._loaded = True

    def _load_embeddings(self):
        """Load the .brain/ embedding index."""
        npz_path = BRAIN / "embeddings.npz"
        meta_path = BRAIN / "metadata.json"

        if not npz_path.exists():
            print("[retriever] No embedding index found. Run indexer first.", file=sys.stderr)
            self._embeddings = np.array([]).reshape(0, 384)
            self._metadata = {"chunks": []}
            return

        data = np.load(npz_path)
        self._embeddings = data["embeddings"]

        with open(meta_path) as f:
            self._metadata = json.load(f)

        self._model_name = self._metadata.get("model", "unknown")
        print(f"[retriever] Loaded {len(self._embeddings)} embeddings "
              f"(model: {self._model_name})", file=sys.stderr)

    def _load_model(self):
        """Load sentence-transformers for query encoding."""
        try:
            from sentence_transformers import SentenceTransformer
            if not self._model_name:
                print("[retriever] No model name in index metadata. "
                      "Rebuild index with indexer first.", file=sys.stderr)
                self._model = None
                return
            self._model = SentenceTransformer(self._model_name)
        except ImportError:
            print("[retriever] sentence-transformers not installed. "
                  "Semantic search disabled.", file=sys.stderr)
            self._model = None

    # ── Keyword search (Kitadel) ─────────────────────────────────────

    def _keyword_search(self, query: str, top_k: int = 20) -> list[dict]:
        """
        Query Kitadel for keyword search results.
        Tries HTTP API first (if server running on :8420),
        falls back to CLI subprocess.
        """
        import json as _json

        # ── Try HTTP API first (server already running) ──────────────
        try:
            import urllib.request
            url = f"http://127.0.0.1:8420/api/search?q={_json.dumps(query)[1:-1]}"
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read())
            # Extract vault results from API response
            results = []
            for r in data.get("results", []):
                if r.get("source") == "Vault":
                    results.append({
                        "path": r.get("url", "").replace("file://", ""),
                        "snippet": r.get("snippet", ""),
                        "score": 0.5,  # API doesn't return numeric score
                        "source": "keyword",
                    })
            if results:
                return results[:top_k]
        except Exception:
            pass  # Fall through to CLI

        # ── Fallback: CLI subprocess ─────────────────────────────────
        try:
            result = subprocess.run(
                ["python3", str(KITADEL), query],
                capture_output=True, text=True, timeout=15,
                cwd=str(KITADEL.parent)
            )
            return self._parse_kitadel_output(result.stdout, top_k)
        except Exception as e:
            print(f"[retriever] Kitadel keyword search failed: {e}", file=sys.stderr)
            return []

    def _parse_kitadel_output(self, output: str, top_k: int) -> list[dict]:
        """Parse Kitadel's text output into structured results."""
        results = []
        in_vault = False
        for line in output.split("\n"):
            if "VAULT" in line.upper() and ("RESULT" in line.upper() or "─" in line):
                in_vault = True
                continue
            if in_vault and line.strip().startswith("[") and "]" in line:
                # Format: [score] path — snippet
                try:
                    bracket_end = line.index("]")
                    score_str = line[1:bracket_end]
                    rest = line[bracket_end + 1:].strip()
                    if " — " in rest:
                        path, snippet = rest.split(" — ", 1)
                    else:
                        path, snippet = rest, ""
                    results.append({
                        "path": path.strip(),
                        "snippet": snippet.strip(),
                        "score": float(score_str) if score_str.replace(".", "").isdigit() else 0.5,
                        "source": "keyword",
                    })
                except (ValueError, IndexError):
                    continue
            if in_vault and (line.strip() == "" or "───" in line):
                in_vault = False

        return results[:top_k]

    # ── Semantic search (embeddings) ─────────────────────────────────

    def _semantic_search(self, query: str, top_k: int = 20) -> list[dict]:
        """Cosine similarity search over pre-computed embeddings."""
        if self._model is None or len(self._embeddings) == 0:
            return []

        # Encode query
        query_embedding = self._model.encode(
            [query], normalize_embeddings=True, show_progress_bar=False
        )[0]

        # Cosine similarity (embeddings are normalized, so dot product = cosine)
        scores = np.dot(self._embeddings, query_embedding)

        # Top-k indices
        top_k = min(top_k, len(scores))
        top_indices = np.argpartition(scores, -top_k)[-top_k:]
        top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]

        results = []
        chunks = self._metadata.get("chunks", [])
        for idx in top_indices:
            score = float(scores[idx])
            if idx < len(chunks):
                chunk = chunks[idx]
                results.append({
                    "path": chunk.get("path", "unknown"),
                    "snippet": chunk.get("title", ""),
                    "score": score,
                    "source": "semantic",
                    "chunk_index": chunk.get("chunk_index", 0),
                })

        return results

    # ── Fusion ───────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 10,
               alpha: float = FUSION_ALPHA) -> list[dict]:
        """
        Hybrid search: keyword + semantic → reciprocal rank fusion.

        Args:
            query: Search query
            top_k: Number of results to return
            alpha: Weight of semantic results (0 = keyword only, 1 = semantic only)

        Returns:
            List of dicts with keys: path, snippet, score, source
        """
        self._ensure_loaded()

        # Fetch from both backends
        keyword_results = self._keyword_search(query, top_k=top_k * 2)
        semantic_results = self._semantic_search(query, top_k=top_k * 2)

        # Reciprocal rank fusion
        # RRF_score(d) = Σ (1 / (k + rank_i(d))) across rankings
        K = 60  # RRF constant

        fused = {}
        for rank, r in enumerate(keyword_results):
            path = r["path"]
            rrf_score = (1 - alpha) / (K + rank + 1)
            fused[path] = {
                **r,
                "score": rrf_score,
                "keyword_rank": rank + 1,
                "semantic_rank": None,
            }

        for rank, r in enumerate(semantic_results):
            path = r["path"]
            rrf_score = alpha / (K + rank + 1)
            if path in fused:
                fused[path]["score"] += rrf_score
                fused[path]["semantic_rank"] = rank + 1
                fused[path]["source"] = "hybrid"
            else:
                fused[path] = {
                    **r,
                    "score": rrf_score,
                    "keyword_rank": None,
                    "semantic_rank": rank + 1,
                }

        # Sort by fused score, descending
        ranked = sorted(fused.values(), key=lambda x: x["score"], reverse=True)
        return ranked[:top_k]

    # ── Retrieval-augmented context builder ──────────────────────────

    def retrieve_context(self, query: str, top_k: int = 5,
                         max_tokens: int = 3000) -> str:
        """
        Search the vault and build a context string for RAG.

        Returns concatenated snippets from top-k results, truncated to
        approximately max_tokens.
        """
        results = self.search(query, top_k=top_k)

        context_parts = []
        token_estimate = 0

        for r in results:
            # Read the actual file content for context
            file_path = VAULT / r["path"]
            if not file_path.exists():
                # Try without .md
                if not r["path"].endswith(".md"):
                    file_path = VAULT / (r["path"] + ".md")
            if not file_path.exists():
                context_parts.append(f"### {r['path']}\n{r['snippet']}")
                continue

            try:
                content = file_path.read_text()
            except Exception:
                context_parts.append(f"### {r['path']}\n{r['snippet']}")
                continue

            # Extract body (skip YAML frontmatter)
            if content.startswith("---"):
                parts = content.split("---", 2)
                body = parts[2] if len(parts) >= 3 else content
            else:
                body = content

            # Truncate to ~2000 words per result (1M context can handle it)
            words = body.split()
            if len(words) > 2000:
                body = " ".join(words[:2000]) + "..."

            context_parts.append(f"### {r['path']} (score: {r['score']:.3f})\n{body}")
            token_estimate += len(body.split())

            if token_estimate >= max_tokens:
                break

        return "\n\n---\n\n".join(context_parts)


# ── Quick test ────────────────────────────────────────────────────────

if __name__ == "__main__":
    retriever = VaultRetriever()

    queries = [
        "black hole information geometry",
        "Wheeler-DeWitt equation Kantowski-Sachs",
        "mixture of experts routing",
        "Lawvere fixed point",
    ]

    for q in queries:
        print(f"\n{'='*70}")
        print(f"QUERY: {q}")
        print(f"{'='*70}")
        results = retriever.search(q, top_k=5)
        for i, r in enumerate(results):
            src_tag = f"[{r['source']}]"
            print(f"  {i+1}. {src_tag:10s} {r['score']:.4f} | {r['path']}")
            if r['snippet']:
                print(f"      {r['snippet'][:120]}")
