"""
Vault RAG Engine — Query Server
================================
FastAPI server that exposes the hybrid retriever as a REST API.
Serves as the backend for Kitadel's semantic search and any
client that wants vault-aware RAG.

Endpoints:
  GET  /search?q=...&top_k=10        — Hybrid search results
  GET  /context?q=...&top_k=5         — RAG context string
  POST /chat                           — Full RAG chat completion
  GET  /health                         — Health check
  GET  /stats                          — Index statistics

Usage:
  python3 vault_rag/server.py --port 8421
"""

import json
import sys
import time
from pathlib import Path
from typing import Optional

# Lazy imports to keep the module importable without heavy deps
try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    import uvicorn
    HAS_SERVER_DEPS = True
except ImportError:
    HAS_SERVER_DEPS = False

# Local imports
sys.path.insert(0, str(Path(__file__).resolve().parent))
from retriever import VaultRetriever

app = FastAPI(
    title="Vault RAG Engine",
    description="Hybrid search + RAG over Obsidian vault with continuous learning",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global state ─────────────────────────────────────────────────────
retriever = VaultRetriever()
start_time = time.time()


# ── Models ───────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    query: str
    top_k: int = 5
    max_context_tokens: int = 3000
    system_prompt: Optional[str] = None

class SearchResponse(BaseModel):
    query: str
    results: list[dict]
    total: int
    time_ms: float

class ContextResponse(BaseModel):
    query: str
    context: str
    source_count: int
    time_ms: float


# ── Endpoints ────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "uptime_seconds": int(time.time() - start_time),
        "vault": str(Path.home() / "Desktop/backup-20260606/vault"),
    }

@app.get("/stats")
async def stats():
    """Return index statistics."""
    try:
        meta_path = Path.home() / "Desktop/backup-20260606/vault/.brain/metadata.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            return {
                "model": meta.get("model", "unknown"),
                "total_chunks": meta.get("total_chunks", 0),
                "total_files": meta.get("total_files", 0),
                "chunk_size": meta.get("chunk_size", 0),
            }
    except Exception:
        pass
    return {"status": "no index found"}

@app.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., description="Search query"),
    top_k: int = Query(10, ge=1, le=50),
    alpha: float = Query(0.3, ge=0.0, le=1.0,
                          description="Semantic weight (0=keyword, 1=semantic)"),
):
    """Hybrid search: keyword + semantic → fused ranking."""
    t0 = time.time()
    results = retriever.search(q, top_k=top_k, alpha=alpha)
    elapsed = (time.time() - t0) * 1000

    return SearchResponse(
        query=q,
        results=results,
        total=len(results),
        time_ms=round(elapsed, 1),
    )

@app.get("/context", response_model=ContextResponse)
async def context(
    q: str = Query(..., description="Query for context retrieval"),
    top_k: int = Query(5, ge=1, le=20),
    max_tokens: int = Query(3000, ge=100, le=10000),
):
    """Retrieve context string from vault for RAG."""
    t0 = time.time()
    ctx = retriever.retrieve_context(q, top_k=top_k, max_tokens=max_tokens)
    elapsed = (time.time() - t0) * 1000

    # Count unique sources
    sources = set()
    for line in ctx.split("\n"):
        if line.startswith("### ") and "(score:" in line:
            path = line.split("(score:")[0].replace("### ", "").strip()
            sources.add(path)

    return ContextResponse(
        query=q,
        context=ctx,
        source_count=len(sources),
        time_ms=round(elapsed, 1),
    )

@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Full RAG chat: retrieve context from vault, then generate response.

    NOTE: Requires an LLM backend (OpenAI API, local model, etc.)
    This endpoint returns the retrieved context + a placeholder for
    the generation step. Wire in your LLM of choice.
    """
    t0 = time.time()
    ctx = retriever.retrieve_context(
        request.query,
        top_k=request.top_k,
        max_tokens=request.max_context_tokens,
    )
    elapsed = (time.time() - t0) * 1000

    return {
        "query": request.query,
        "context": ctx,
        "retrieval_time_ms": round(elapsed, 1),
        "message": (
            "Context retrieved. To complete the RAG pipeline, send this "
            "context to an LLM with the original query. "
            "Example:\n\n"
            f"System: You are a knowledgeable assistant. Use the following "
            f"context from the user's vault to answer questions.\n\n"
            f"Context:\n{ctx[:500]}...\n\n"
            f"User: {request.query}"
        ),
    }


# ── Main ─────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Vault RAG server")
    parser.add_argument("--port", type=int, default=8421)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    if not HAS_SERVER_DEPS:
        print("ERROR: FastAPI/uvicorn not installed.", file=sys.stderr)
        print("  Install: uv pip install fastapi uvicorn", file=sys.stderr)
        sys.exit(1)

    print(f"Vault RAG Engine starting on http://{args.host}:{args.port}", file=sys.stderr)
    print(f"  Search:  http://{args.host}:{args.port}/search?q=black+hole", file=sys.stderr)
    print(f"  Context: http://{args.host}:{args.port}/context?q=WDW+equation", file=sys.stderr)
    print(f"  Health:  http://{args.host}:{args.port}/health", file=sys.stderr)

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
