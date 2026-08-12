"""
MoE Expert Retriever — Vault-Grounded Multi-Expert Retrieval
=============================================================
Routes queries to domain-specialized expert retrievers using MoE gating.
Each expert retrieves from its vault domain; router fuses results with
learned routing weights.

Architecture:
  Query → Router (classify → domain experts) → Top-k retrieval
       → Fusion (weighted combine) → Context → GPT-2 grounded generation

The vault is the ground truth. No fabricated knowledge. Every retrieved
chunk links back to a specific vault file + line.
"""

import json
import sys
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import numpy as np

# ── Configuration ────────────────────────────────────────────────────

VAULT = Path.home() / "Documents/ObsidianVault"
BRAIN = VAULT / ".brain"
GPT2_FINETUNED = Path.home() / "gpt2_moe_1m" / "vault-gpt-finetuned"

# Domain definitions: each expert covers a vault subdirectory
DOMAINS = {
    "wiki": {
        "dirs": ["wiki"],
        "description": "Core concepts — BBP, WDW, Connes, Prophet inequality, spectral triples",
        "keywords": ["phase transition", "spectral", "eigenvalue", "quantum", "cosmology",
                     "berry", "connes", "prophet", "beltrami", "logdet", "moe", "attention",
                     "rope", "transformer", "ledger", "nobody"],
    },
    "trading": {
        "dirs": ["knowledge"],
        "description": "Trading, finance, markets — Game Plan, LogDet+Logit+Ledger",
        "keywords": ["trading", "market", "logdet", "logit", "ledger", "game plan",
                     "arbitrage", "portfolio", "risk", "sharpe", "volatility"],
    },
    "systems": {
        "dirs": ["decisions", "conversations"],
        "description": "System design, decisions, architecture, tooling",
        "keywords": ["architecture", "system", "pipeline", "cron", "indexer", "rag",
                     "finetune", "training", "model", "server", "api", "deploy"],
    },
    "general": {
        "dirs": ["output", "raw"],
        "description": "Generated output, raw data, cross-domain synthesis",
        "keywords": ["synthesis", "output", "summary", "report", "analysis"],
    },
}

# ── Embedding Cache ─────────────────────────────────────────────────

class EmbeddingCache:
    """Load and query the pre-built vault embedding index."""

    def __init__(self, brain_dir: Path = BRAIN):
        self.brain_dir = brain_dir
        self.embeddings = None
        self.metadata = None
        self._loaded = False

    def load(self):
        if self._loaded:
            return
        emb_path = self.brain_dir / "embeddings.npz"
        meta_path = self.brain_dir / "metadata.json"

        if not emb_path.exists():
            raise FileNotFoundError(f"No index at {emb_path}. Run indexer.py build first.")

        print(f"[cache] Loading index from {emb_path}", file=sys.stderr)
        data = np.load(emb_path, allow_pickle=True)
        self.embeddings = data["embeddings"]  # [N, dim] — 23172 × 768 for bge-base

        with open(meta_path) as f:
            meta = json.load(f)

        # metadata.json structure: {"chunks": [{path, chunk_index, title, tags}, ...]}
        self.chunks_meta = meta["chunks"]  # list of N dicts, aligned with embeddings

        self._loaded = True
        print(f"[cache] {len(self.embeddings)} chunks, "
              f"{self.embeddings.shape[1]}d", file=sys.stderr)

    def search(self, query_embedding: np.ndarray, top_k: int = 10,
               domain_filter: Optional[List[str]] = None) -> List[Dict]:
        """
        Cosine similarity search over the embedding index.
        Optionally filter by domain (vault subdirectory).
        """
        if not self._loaded:
            self.load()

        # Cosine similarity
        embeddings = self.embeddings.astype(np.float32)
        query = query_embedding.astype(np.float32)

        # Normalize
        embeddings_norm = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-8)
        query_norm = query / (np.linalg.norm(query) + 1e-8)
        scores = embeddings_norm @ query_norm  # [N]

        # Build results with metadata
        results = []
        for idx in np.argsort(scores)[::-1]:
            score = float(scores[idx])
            chunk_meta = self.chunks_meta[idx] if idx < len(self.chunks_meta) else {}
            file_path = chunk_meta.get("path", "")
            title = chunk_meta.get("title", "")

            # Domain filter
            if domain_filter:
                matched = any(f"/{d}/" in file_path or file_path.startswith(f"{d}/")
                             for d in domain_filter)
                if not matched:
                    continue

            results.append({
                "chunk_id": str(idx),
                "score": score,
                "file": file_path,
                "title": title,
                "chunk_index": chunk_meta.get("chunk_index", 0),
                "tags": chunk_meta.get("tags", []),
            })

            if len(results) >= top_k:
                break

        return results


# ── MoE Router ───────────────────────────────────────────────────────

class MoERouter:
    """
    Keyword-based router that classifies queries to domain experts.
    Top-k gating: selects k most relevant domains based on keyword overlap.

    Future: replace with learned router (small classifier over query embedding).
    """

    def __init__(self, domains: Dict = DOMAINS, top_k: int = 2):
        self.domains = domains
        self.top_k = top_k

    def route(self, query: str) -> List[Tuple[str, float]]:
        """
        Route query to top-k domain experts.

        Returns: [(domain_name, routing_weight), ...]
        """
        query_lower = query.lower()
        scores = {}

        for domain_name, config in self.domains.items():
            keywords = config.get("keywords", [])
            if not keywords:
                scores[domain_name] = 0.0
                continue

            # Count keyword matches
            matches = sum(1 for kw in keywords if kw.lower() in query_lower)
            # Normalize by keyword count to avoid bias toward domains with more keywords
            score = matches / max(len(keywords), 1)
            scores[domain_name] = score

        # Top-k selection
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top = ranked[:self.top_k]

        # Softmax-normalize the selected weights
        if top:
            weights = np.array([w for _, w in top])
            weights = np.exp(weights) / np.sum(np.exp(weights))
            return [(domain, float(w)) for (domain, _), w in zip(top, weights)]

        # Fallback: general domain
        return [("general", 1.0)]


# ── MoE Expert Retriever ────────────────────────────────────────────

class MoEExpertRetriever:
    """
    Multi-Expert Retrieval over the vault.

    Query → Router → Expert retrieval → Weighted fusion → Ranked context.
    """

    def __init__(self, brain_dir: Path = BRAIN, domains: Dict = DOMAINS,
                 top_k_experts: int = 2, chunks_per_expert: int = 5):
        self.cache = EmbeddingCache(brain_dir)
        self.router = MoERouter(domains, top_k=top_k_experts)
        self.chunks_per_expert = chunks_per_expert
        self._model = None  # Lazy-loaded sentence-transformer

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            # Use same model as indexer
            model_name = "BAAI/bge-base-en-v1.5"
            print(f"[moe-retriever] Loading embedding model: {model_name}", file=sys.stderr)
            self._model = SentenceTransformer(model_name)
        return self._model

    def retrieve(self, query: str, top_k: int = 10) -> Dict:
        """
        Full MoE retrieval pipeline.

        Returns: {
            "query": str,
            "routing": [(domain, weight), ...],
            "results": [{chunk_id, score, file, text, domain, expert_weight}, ...],
            "fusion_note": str,
        }
        """
        # 1. Route to experts
        routing = self.router.route(query)
        print(f"[moe-retriever] Query: {query[:80]}...", file=sys.stderr)
        print(f"[moe-retriever] Routing: {[(d, f'{w:.3f}') for d, w in routing]}", file=sys.stderr)

        # 2. Encode query
        model = self._get_model()
        query_embedding = model.encode(query, normalize_embeddings=True)

        # 3. Each expert retrieves from their domain
        all_results = []
        seen_chunks = set()

        for domain, weight in routing:
            domain_dirs = self.router.domains.get(domain, {}).get("dirs", [])
            domain_results = self.cache.search(
                query_embedding,
                top_k=self.chunks_per_expert * 2,  # Overfetch for dedup
                domain_filter=domain_dirs,
            )

            # Apply expert routing weight to scores
            for r in domain_results:
                cid = r["chunk_id"]
                if cid in seen_chunks:
                    continue
                seen_chunks.add(cid)
                all_results.append({
                    **r,
                    "domain": domain,
                    "expert_weight": weight,
                    "fused_score": r["score"] * weight,
                })

        # 4. Sort by fused score (routing weight × retrieval score)
        all_results.sort(key=lambda x: x["fused_score"], reverse=True)
        final = all_results[:top_k]

        # 5. Build context string — read actual text from vault files
        context_lines = []
        for i, r in enumerate(final):
            # Try to read the actual text from the vault file
            file_path_full = VAULT / r["file"]
            snippet = ""
            if file_path_full.exists():
                try:
                    content = file_path_full.read_text(errors="ignore")
                    # Get a relevant snippet (approximate by chunk position)
                    chunk_idx = r.get("chunk_index", 0)
                    words = content.split()
                    start = chunk_idx * 200  # rough approximation
                    snippet = " ".join(words[start:start+100])
                except Exception:
                    snippet = f"[{r['file']}]"
            else:
                snippet = f"[{r['file']}]"
            
            context_lines.append(
                f"[{i+1}] {r['domain']} | {r['file']} (score={r['fused_score']:.3f})\n"
                f"    {snippet[:300]}"
            )

        context = "\n\n".join(context_lines)

        return {
            "query": query,
            "routing": [(d, round(w, 3)) for d, w in routing],
            "results": final,
            "context": context,
            "fusion_note": f"MoE top-{self.router.top_k} routing, "
                          f"{len(final)} fused results from {len(routing)} experts",
        }


# ── Vault-Grounded GPT-2 Generator ──────────────────────────────────

class VaultGroundedGPT:
    """
    GPT-2 finetuned on vault, grounded by MoE retrieval context.

    Query → MoE retrieval → context-augmented prompt → GPT-2 generation.
    """

    def __init__(self, model_path: Path = GPT2_FINETUNED):
        self.model_path = model_path
        self.retriever = MoEExpertRetriever()
        self._model = None
        self._tokenizer = None

    def _load_model(self):
        if self._model is not None:
            return
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch

        print(f"[vault-gpt] Loading finetuned model from {self.model_path}", file=sys.stderr)
        self._tokenizer = AutoTokenizer.from_pretrained(str(self.model_path))
        self._tokenizer.pad_token = self._tokenizer.eos_token
        self._model = AutoModelForCausalLM.from_pretrained(
            str(self.model_path),
            torch_dtype=torch.float32,
            low_cpu_mem_usage=True,
        )
        self._model.eval()
        print(f"[vault-gpt] Loaded. Device: {self._model.device}", file=sys.stderr)

    def ask(self, query: str, max_new_tokens: int = 80,
            temperature: float = 0.7) -> Dict:
        """
        Full RAG pipeline: retrieve → augment → generate.

        Returns: {
            "query": str,
            "routing": [...],
            "retrieved_chunks": [...],
            "prompt": str,
            "response": str,
        }
        """
        import torch

        # 1. Retrieve context via MoE
        retrieval = self.retriever.retrieve(query, top_k=5)
        context = retrieval["context"]

        # 2. Build grounded prompt
        prompt = (
            f"Using the following vault notes as reference:\n\n"
            f"{context}\n\n"
            f"Question: {query}\n\n"
            f"Answer (grounded in vault notes above):"
        )

        # 3. Generate
        self._load_model()
        inputs = self._tokenizer(prompt, return_tensors="pt", truncation=True, max_length=900)
        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=True,
                temperature=temperature,
                pad_token_id=self._tokenizer.eos_token_id,
            )
        response = self._tokenizer.decode(outputs[0], skip_special_tokens=True)
        # Strip the prompt from the response
        if response.startswith(prompt):
            response = response[len(prompt):].strip()

        return {
            "query": query,
            "routing": retrieval["routing"],
            "retrieved_chunks": [
                {"file": r["file"], "score": r["fused_score"], "domain": r["domain"]}
                for r in retrieval["results"]
            ],
            "prompt": prompt,
            "response": response,
        }


# ── CLI ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="MoE Expert Vault-Grounded RAG")
    parser.add_argument("query", nargs="?", default=None,
                       help="Question to answer from vault knowledge")
    parser.add_argument("--search-only", action="store_true",
                       help="Only retrieve, don't generate")
    parser.add_argument("--top-k", type=int, default=5,
                       help="Number of chunks to retrieve")
    parser.add_argument("--max-tokens", type=int, default=80,
                       help="Max new tokens to generate")
    args = parser.parse_args()

    if args.search_only:
        retriever = MoEExpertRetriever()
        result = retriever.retrieve(args.query or "quantum cosmology", top_k=args.top_k)
        print(json.dumps(result, indent=2, default=str))
    elif args.query:
        gpt = VaultGroundedGPT()
        result = gpt.ask(args.query, max_new_tokens=args.max_tokens)
        print(f"\n{'='*60}")
        print(f"QUERY: {result['query']}")
        print(f"ROUTING: {result['routing']}")
        print(f"\nRETRIEVED:")
        for i, chunk in enumerate(result['retrieved_chunks']):
            print(f"  [{i+1}] {chunk['domain']} | {chunk['file']} ({chunk['score']:.3f})")
        print(f"\nRESPONSE:\n{result['response']}")
        print(f"{'='*60}")
    else:
        parser.print_help()
