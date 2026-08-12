#!/usr/bin/env python3
"""
index_scriptures.py — Index all Myosu scripture documents into LanceDB for RAG.

One-time setup. After this, the local GGUF model can retrieve
relevant passages from:
  - unified-scripture.md (18 books of unified scripture)
  - book-of-the-hidden-door.md (14 obscured fables)
  - derrida-myosu-conjugation.md (12-section critical archive)
  - README.md (the 15-act framework documentation)

Usage:
    python3 index_scriptures.py
"""
import os, sys, json
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT))

# Documents to index
DOCUMENTS = [
    PROJECT / "unified-scripture.md",
    PROJECT / "book-of-the-hidden-door.md",
    PROJECT / "derrida-myosu-conjugation.md",
    PROJECT / "README.md",
]

# ── Simple chunker (no deps beyond stdlib) ────────────────────────────────────

def chunk_text(text: str, source: str, chunk_size: int = 600, overlap: int = 100) -> list[dict]:
    """Split text into overlapping chunks with metadata."""
    paragraphs = []
    current = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped == "":
            if current:
                paragraphs.append(" ".join(current))
                current = []
        elif stripped.startswith("#"):
            if current:
                paragraphs.append(" ".join(current))
                current = []
            paragraphs.append(stripped)  # keep headings as separate chunks
        else:
            current.append(stripped)
    if current:
        paragraphs.append(" ".join(current))

    chunks = []
    i = 0
    for para in paragraphs:
        words = para.split()
        if len(words) < 20:
            continue  # skip very short chunks
        chunks.append({
            "text": para,
            "source": source,
            "chunk_index": i,
            "title": source.replace(".md", "").replace("-", " ").title(),
        })
        i += 1
    return chunks


def index_documents():
    """Chunk and save as JSON (LanceDB compatible)."""
    all_chunks = []
    for doc_path in DOCUMENTS:
        if not doc_path.exists():
            print(f"  SKIP: {doc_path.name} (not found)")
            continue
        text = doc_path.read_text(encoding="utf-8", errors="replace")
        chunks = chunk_text(text, doc_path.name)
        all_chunks.extend(chunks)
        print(f"  {doc_path.name}: {len(chunks)} chunks")

    # Save to JSON for LanceDB ingestion
    out_path = PROJECT / "data" / "scripture_chunks.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(all_chunks, indent=2, ensure_ascii=False))
    print(f"\nTotal: {len(all_chunks)} chunks → {out_path}")
    print(f"Size: {out_path.stat().st_size / 1024:.1f} KB")
    return all_chunks


# ── Try LanceDB indexing if available ─────────────────────────────────────────

def index_to_lancedb(chunks: list[dict]):
    """Index chunks into LanceDB with embeddings."""
    try:
        import lancedb
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("\n⚠ LanceDB or sentence-transformers not installed.")
        print("  Install: pip install lancedb sentence-transformers")
        print(f"  Chunks saved as JSON — manual ingestion available.")
        return False

    print("\nGenerating embeddings...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    texts = [c["text"] for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=True)

    # Add embeddings to chunks
    for i, emb in enumerate(embeddings):
        chunks[i]["vector"] = emb.tolist()

    # Connect to LanceDB
    db_path = str(PROJECT / "data" / "myosu_lancedb")
    db = lancedb.connect(db_path)

    # Create or overwrite table
    import pyarrow as pa
    table = pa.table({
        "text": [c["text"] for c in chunks],
        "source": [c["source"] for c in chunks],
        "chunk_index": [c["chunk_index"] for c in chunks],
        "title": [c["title"] for c in chunks],
        "vector": [c["vector"] for c in chunks],
    })

    try:
        db.drop_table("scriptures", ignore_missing=True)
    except:
        pass

    db.create_table("scriptures", table)
    print(f"  Indexed {len(chunks)} chunks into LanceDB at {db_path}")
    return True


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Indexing Myosu Scripture Documents")
    print("=" * 50)
    chunks = index_documents()
    index_to_lancedb(chunks)
    print("\nDone. RAG layer ready.")
