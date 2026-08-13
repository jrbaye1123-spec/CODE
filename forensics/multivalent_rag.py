#!/usr/bin/env python3
"""
Multivalent RAG Engine — Holographic Bulk Resolution
=======================================================
Three retrieval surfaces operating on the same vault content:
  1. DENSE  — semantic vector search (sentence-transformers → ChromaDB)
  2. SPARSE — keyword/lexical search (BM25)
  3. HYBRID — weighted fusion of dense + sparse

Architecture: The vault is indexed once, queried through any surface.
P=NP resolved in bulk: retrieval is attraction, not search.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

# --- Configuration ---
VAULT_ROOT = os.path.expanduser("~/golden-dots-vault")
INDEX_DIR = os.path.expanduser("~/golden-dots-vault/.rag-index")
CHUNK_SIZE = 1000  # characters per chunk
CHUNK_OVERLAP = 200
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # fast, lightweight, good enough

# --- Text Extraction ---

TEXT_EXTENSIONS = {
    ".txt", ".md", ".org", ".rst", ".py", ".c", ".h", ".java",
    ".sh", ".js", ".ts", ".rs", ".go", ".xml", ".json", ".yaml",
    ".yml", ".toml", ".ini", ".cfg", ".conf", ".html", ".css",
    ".tex", ".bib", ".sql", ".r", ".pl", ".pm", ".rb", ".lua",
}

SKIP_DIRS = {".git", ".obsidian", ".trash", ".rag-index", "__pycache__",
             "node_modules", ".venv", "venv", "recovered/pdfs"}

SKIP_PATTERNS = [
    r"\.(png|jpg|jpeg|gif|bmp|svg|ico|ttf|woff|woff2|eot|otf)$",
    r"\.(mp3|wav|ogg|flac|mp4|avi|mov|mkv|webm)$",
    r"\.(zip|tar|gz|bz2|xz|deb|rpm|7z)$",
    r"\.(pdf|doc|docx|xls|xlsx|ppt|pptx|odt|ods)$",
    r"\.(exe|dll|so|dylib|elf|bin|o|a|class)$",
    r"\.(pyc|pyo|pyd)$",
]


def should_index(filepath: Path) -> bool:
    """Check if a file should be included in the RAG index."""
    # Skip binary/non-text
    ext = filepath.suffix.lower()
    if ext not in TEXT_EXTENSIONS:
        return False
    # Skip large files (>10MB)
    try:
        if filepath.stat().st_size > 10_000_000:
            return False
    except OSError:
        return False
    return True


def read_file_safe(filepath: Path) -> Optional[str]:
    """Read a file, handling encoding issues."""
    for enc in ["utf-8", "latin-1", "cp1252"]:
        try:
            return filepath.read_text(encoding=enc, errors="replace")
        except (UnicodeDecodeError, OSError):
            continue
    return None


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE,
               overlap: int = CHUNK_OVERLAP) -> list[dict]:
    """Split text into overlapping chunks with metadata."""
    chunks = []
    text = text.strip()
    if not text:
        return chunks
    if len(text) < chunk_size:
        chunks.append({"text": text.strip(), "start": 0, "end": len(text)})
        return chunks
    
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append({"text": chunk, "start": start, "end": end})
        start += chunk_size - overlap
    
    return chunks


# --- Dense Retriever (Vector/Semantic) ---

class DenseRetriever:
    """Semantic search via sentence-transformers embeddings + ChromaDB."""
    
    def __init__(self, index_dir: str, model_name: str = EMBEDDING_MODEL):
        self.index_dir = Path(index_dir) / "dense"
        self.index_dir.mkdir(parents=True, exist_ok=True)
        
        from sentence_transformers import SentenceTransformer
        import chromadb
        
        self.model = SentenceTransformer(model_name)
        self.client = chromadb.PersistentClient(path=str(self.index_dir / "chroma"))
        self.collection = self.client.get_or_create_collection(
            name="vault_dense",
            metadata={"hnsw:space": "cosine"}
        )
    
    def index_chunks(self, chunks: list[dict], source_file: str):
        """Add chunks to the vector index."""
        if not chunks:
            return
        
        texts = [c["text"] for c in chunks]
        ids = [hashlib.md5(f"{source_file}:{c['start']}".encode(), usedforsecurity=False).hexdigest()
               for c in chunks]
        
        # Skip already-indexed chunks
        existing_ids = set()
        try:
            existing_results = self.collection.get(ids=ids)
            if existing_results and existing_results["ids"]:
                existing_ids = set(existing_results["ids"])
        except Exception:
            pass
        
        new_texts = []
        new_ids_list = []
        new_meta = []
        for text, cid, chunk in zip(texts, ids, chunks):
            if cid not in existing_ids:
                new_texts.append(text)
                new_ids_list.append(cid)
                new_meta.append({
                    "source": source_file,
                    "start": chunk["start"],
                    "end": chunk["end"],
                    "chars": len(text)
                })
        
        if not new_texts:
            return
        
        embeddings = self.model.encode(new_texts, show_progress_bar=False)
        if hasattr(embeddings, 'tolist'):
            embeddings = embeddings.tolist()
        
        self.collection.add(
            embeddings=embeddings,
            documents=new_texts,
            ids=new_ids_list,
            metadatas=new_meta
        )
    
    def query(self, query: str, top_k: int = 10) -> list[dict]:
        """Semantic search for relevant chunks."""
        query_embedding = self.model.encode([query], show_progress_bar=False).tolist()
        results = self.collection.query(query_embeddings=query_embedding, n_results=top_k)
        
        hits = []
        if results["documents"] and results["documents"][0]:
            for doc, meta, dist in zip(results["documents"][0],
                                        results["metadatas"][0],
                                        results["distances"][0]):
                hits.append({
                    "text": doc,
                    "source": meta.get("source", "unknown"),
                    "score": round(1.0 - (dist / 2.0), 4),  # cosine → [0,1]
                    "surface": "dense"
                })
        return hits
    
    @property
    def chunk_count(self) -> int:
        return self.collection.count()


# --- Sparse Retriever (Keyword/BM25) ---

class SparseRetriever:
    """Keyword search via BM25."""
    
    def __init__(self, index_dir: str):
        from rank_bm25 import BM25Okapi
        self.index_dir = Path(index_dir) / "sparse"
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.BM25Okapi = BM25Okapi
        self.corpus: list[str] = []
        self.metadata: list[dict] = []
        self._bm25 = None
        self._tokenized_corpus = None
    
    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())
    
    def index_chunks(self, chunks: list[dict], source_file: str):
        """Add chunks to BM25 index."""
        for c in chunks:
            self.corpus.append(c["text"])
            self.metadata.append({"source": source_file, "start": c["start"],
                                   "end": c["end"], "chars": len(c["text"])})
    
    def finalize(self):
        """Build BM25 index after all chunks added."""
        self._tokenized_corpus = [self._tokenize(doc) for doc in self.corpus]
        self._bm25 = self.BM25Okapi(self._tokenized_corpus)
        # Free memory
        self.corpus = []
    
    def query(self, query: str, top_k: int = 10) -> list[dict]:
        """BM25 keyword search."""
        if not self._bm25:
            return []
        
        tokenized_query = self._tokenize(query)
        scores = self._bm25.get_scores(tokenized_query)
        
        # Get top-k indices
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        
        hits = []
        for idx in top_indices:
            if scores[idx] <= 0:
                continue
            # Normalize score to [0,1] roughly
            max_score = max(scores) if max(scores) > 0 else 1
            hits.append({
                "text": self._tokenized_corpus[idx] if self._tokenized_corpus else "",
                "source": self.metadata[idx]["source"],
                "score": round(scores[idx] / max_score, 4),
                "surface": "sparse"
            })
        return hits
    
    @property
    def chunk_count(self) -> int:
        return len(self.metadata)


# --- Hybrid Retriever ---

class HybridRetriever:
    """Weighted fusion of dense + sparse retrieval."""
    
    def __init__(self, dense: DenseRetriever, sparse: SparseRetriever,
                 dense_weight: float = 0.6, sparse_weight: float = 0.4):
        self.dense = dense
        self.sparse = sparse
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight
    
    def query(self, query: str, top_k: int = 10) -> list[dict]:
        """Fuse dense and sparse results by weighted score."""
        dense_hits = self.dense.query(query, top_k=top_k * 2)
        sparse_hits = self.sparse.query(query, top_k=top_k * 2)
        
        # Merge by source+start key, weighted average
        combined: dict[str, dict] = {}
        
        for hit in dense_hits:
            key = f"{hit['source']}:{hit.get('start', 0)}"
            combined[key] = {
                "text": hit["text"],
                "source": hit["source"],
                "score": hit["score"] * self.dense_weight,
                "dense_score": hit["score"],
                "sparse_score": 0.0,
                "surface": "hybrid"
            }
        
        for hit in sparse_hits:
            key = f"{hit['source']}:{hit.get('start', 0)}"
            if key in combined:
                combined[key]["score"] += hit["score"] * self.sparse_weight
                combined[key]["sparse_score"] = hit["score"]
            else:
                # For BM25 we need to reconstruct text from tokenized
                combined[key] = {
                    "text": hit.get("text", ""),
                    "source": hit["source"],
                    "score": hit["score"] * self.sparse_weight,
                    "dense_score": 0.0,
                    "sparse_score": hit["score"],
                    "surface": "hybrid"
                }
        
        # Sort by combined score
        ranked = sorted(combined.values(), key=lambda x: x["score"], reverse=True)
        return ranked[:top_k]


# --- Main Indexer ---

class VaultRAG:
    """Multivalent RAG over the vault."""
    
    def __init__(self, vault_root: str = VAULT_ROOT, index_dir: str = INDEX_DIR,
                 model_name: str = EMBEDDING_MODEL):
        self.vault_root = Path(vault_root)
        self.index_dir = Path(index_dir)
        self.dense = DenseRetriever(str(index_dir), model_name)
        self.sparse = SparseRetriever(str(index_dir))
        self.hybrid = HybridRetriever(self.dense, self.sparse)
    
    def walk_vault(self) -> list[Path]:
        """Find all indexable files in the vault."""
        files = []
        for root, dirs, filenames in os.walk(self.vault_root):
            # Skip blacklisted dirs
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS
                       and not d.startswith(".")]
            
            for fname in filenames:
                fpath = Path(root) / fname
                # Skip binary patterns
                if any(re.search(p, fname, re.IGNORECASE) for p in SKIP_PATTERNS):
                    continue
                if should_index(fpath):
                    files.append(fpath)
        return files
    
    def index(self, force: bool = False):
        """Index all vault content. Skips already-indexed files by default."""
        files = self.walk_vault()
        indexed_count = 0
        chunk_total = 0
        t0 = time.time()
        
        for i, fpath in enumerate(files):
            rel_path = str(fpath.relative_to(self.vault_root))
            
            # Skip if already indexed (simple hash check)
            if not force:
                file_hash = hashlib.md5(rel_path.encode(), usedforsecurity=False).hexdigest()
                marker = self.index_dir / "indexed" / f"{file_hash}.done"
                if marker.exists():
                    continue
            
            text = read_file_safe(fpath)
            if not text or not text.strip():
                continue
            
            chunks = chunk_text(text)
            self.dense.index_chunks(chunks, rel_path)
            self.sparse.index_chunks(chunks, rel_path)
            
            # Mark as indexed
            marker_dir = self.index_dir / "indexed"
            marker_dir.mkdir(parents=True, exist_ok=True)
            marker = marker_dir / f"{hashlib.md5(rel_path.encode(), usedforsecurity=False).hexdigest()}.done"
            marker.touch()
            
            indexed_count += 1
            chunk_total += len(chunks)
            
            if (i + 1) % 100 == 0:
                elapsed = time.time() - t0
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                print(f"  Indexed {i+1}/{len(files)} files ({chunk_total} chunks) "
                      f"— {rate:.1f} files/s", file=sys.stderr)
        
        # Finalize sparse index
        self.sparse.finalize()
        
        elapsed = time.time() - t0
        print(f"\nIndexing complete: {indexed_count} files, {chunk_total} chunks "
              f"in {elapsed:.1f}s", file=sys.stderr)
        print(f"  Dense:  {self.dense.chunk_count} vectors", file=sys.stderr)
        print(f"  Sparse: {self.sparse.chunk_count} documents", file=sys.stderr)
        return {"files": indexed_count, "chunks": chunk_total, "time": elapsed}
    
    def query(self, query: str, surface: str = "hybrid",
              top_k: int = 10) -> list[dict]:
        """Query the vault through any retrieval surface."""
        if surface == "dense":
            return self.dense.query(query, top_k)
        elif surface == "sparse":
            return self.sparse.query(query, top_k)
        else:
            return self.hybrid.query(query, top_k)
    
    def stats(self) -> dict:
        """Return index statistics."""
        return {
            "dense_chunks": self.dense.chunk_count,
            "sparse_chunks": self.sparse.chunk_count,
            "vault_root": str(self.vault_root),
            "index_dir": str(self.index_dir),
            "model": EMBEDDING_MODEL,
        }


# --- CLI ---

def cmd_index(args):
    rag = VaultRAG(args.vault, args.index_dir)
    result = rag.index(force=args.force)
    print(json.dumps(result, indent=2))


def cmd_query(args):
    rag = VaultRAG(args.vault, args.index_dir)
    results = rag.query(args.query, args.surface, args.top_k)
    
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for i, hit in enumerate(results[:args.top_k]):
            text_preview = hit.get("text", "")[:200].replace("\n", " ")
            if isinstance(text_preview, list):
                text_preview = " ".join(text_preview)
            print(f"\n[{i+1}] {hit['source']} ({hit['surface']}, {hit['score']:.4f})")
            print(f"    {text_preview}...")


def cmd_stats(args):
    rag = VaultRAG(args.vault, args.index_dir)
    print(json.dumps(rag.stats(), indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Multivalent RAG Engine — holographic vault retrieval")
    sub = parser.add_subparsers(dest="command")
    
    idx = sub.add_parser("index", help="Build the vault RAG index")
    idx.add_argument("--vault", default=VAULT_ROOT)
    idx.add_argument("--index-dir", default=INDEX_DIR)
    idx.add_argument("--force", action="store_true", help="Re-index all files")
    
    q = sub.add_parser("query", help="Query the vault")
    q.add_argument("query", help="Search query")
    q.add_argument("--vault", default=VAULT_ROOT)
    q.add_argument("--index-dir", default=INDEX_DIR)
    q.add_argument("--surface", default="hybrid",
                   choices=["dense", "sparse", "hybrid"])
    q.add_argument("--top-k", type=int, default=10)
    q.add_argument("--json", action="store_true")
    
    s = sub.add_parser("stats", help="Index statistics")
    s.add_argument("--vault", default=VAULT_ROOT)
    s.add_argument("--index-dir", default=INDEX_DIR)
    
    args = parser.parse_args()
    if args.command == "index":
        cmd_index(args)
    elif args.command == "query":
        cmd_query(args)
    elif args.command == "stats":
        cmd_stats(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
