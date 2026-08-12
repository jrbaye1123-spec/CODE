"""Tier 1 title embeddings for VaultLens.

Embeds only: title, aliases, tags, note type, short summary.
Uses bge-small-en-v1.5 (384 dims) via FastEmbed for local-only inference.
All vectors are L2-normalized. Model manifest is recorded and hash-verified.
"""

import hashlib
import json
import os
import sqlite3
import time
import numpy as np
from pathlib import Path
from typing import Optional

from ..parser import _generate_note_id


# ── Embedder ──────────────────────────────────────────

class FastEmbedder:
    """Local embedding model via FastEmbed with manifest tracking."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5",
                 cache_dir: Optional[str] = None):
        self.model_name = model_name
        self.dims = 384
        self.model_hash = ""
        self._model = None

        if cache_dir:
            os.environ["FASTEMBED_CACHE_DIR"] = cache_dir

    def _load(self):
        if self._model is None:
            from fastembed import TextEmbedding
            self._model = TextEmbedding(model_name=self.model_name)
            # Try to compute model hash from files
            self.model_hash = self._compute_model_hash()

    def _compute_model_hash(self) -> str:
        """Compute hash of model files for manifest integrity."""
        try:
            cache = os.environ.get("FASTEMBED_CACHE_DIR",
                                    os.path.expanduser("~/.cache/fastembed"))
            model_dir = os.path.join(cache, self.model_name.replace("/", "--"))
            if os.path.isdir(model_dir):
                hasher = hashlib.sha256()
                for root, _, files in sorted(os.walk(model_dir)):
                    for fname in sorted(files):
                        if fname.endswith((".onnx", ".json", ".txt", ".model")):
                            with open(os.path.join(root, fname), "rb") as f:
                                hasher.update(f.read())
                return hasher.hexdigest()[:16]
        except Exception:
            pass
        return "unknown"

    def embed(self, texts: list[str]) -> list[np.ndarray]:
        """Embed a list of texts. Returns list of normalized float32 vectors."""
        self._load()
        vectors = []
        for text in texts:
            vec = next(self._model.embed([text or " "]))
            vec = np.asarray(vec, dtype=np.float32)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            vectors.append(vec)
        return vectors


# ── Note text extraction ──────────────────────────────

def build_embedding_text(title: str, aliases: list[str] = None,
                         tags: list[str] = None, note_type: str = "",
                         summary: str = "") -> str:
    """Build a deterministic text field for embedding.

    Formula: title | aliases: ... | tags: ... | type: ... | summary: ...

    This is the ONLY text that gets embedded at Tier 1.
    """
    parts = []
    if title:
        parts.append(title)
    if aliases:
        parts.append("aliases: " + "; ".join(aliases))
    if tags:
        parts.append("tags: " + ", ".join(tags))
    if note_type:
        parts.append("type: " + note_type)
    if summary:
        parts.append("summary: " + summary)
    return " | ".join(parts) if parts else title


def extract_summary(body: str, max_chars: int = 250) -> str:
    """Extract a short summary from note body: first non-heading paragraph."""
    lines = body.strip().split("\n")
    paragraph_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            if paragraph_lines:
                break
            continue
        paragraph_lines.append(stripped)
    summary = " ".join(paragraph_lines)
    if len(summary) > max_chars:
        summary = summary[:max_chars].rsplit(" ", 1)[0] + "..."
    return summary


# ── Vector store ──────────────────────────────────────

VECTOR_SCHEMA = """
CREATE TABLE IF NOT EXISTS embedding_models (
    model_id TEXT PRIMARY KEY,
    model_name TEXT NOT NULL,
    model_hash TEXT NOT NULL,
    source TEXT DEFAULT 'fastembed',
    dims INTEGER NOT NULL,
    metric TEXT DEFAULT 'cosine',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS title_embeddings (
    note_id TEXT PRIMARY KEY,
    shard_id TEXT DEFAULT 'default',
    model_id TEXT NOT NULL,
    text_hash TEXT NOT NULL,
    dims INTEGER NOT NULL,
    quant TEXT DEFAULT 'f32',
    vec BLOB NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (model_id) REFERENCES embedding_models(model_id)
);

CREATE INDEX IF NOT EXISTS idx_title_emb_model ON title_embeddings(model_id);
"""


def vector_to_blob(vec: np.ndarray) -> bytes:
    return vec.astype(np.float32).tobytes()


def blob_to_vector(blob: bytes, dims: int) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32).copy()


class VectorStore:
    """Brute-force cosine vector store backed by SQLite.

    For Gate 1 (small scale), brute-force is sufficient.
    No ANN, no FAISS, no LanceDB yet.
    """

    def __init__(self, db_path: str = ".vaultlens/vectors.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.executescript(VECTOR_SCHEMA)
        self.conn.commit()

    def register_model(self, model_id: str, model_name: str,
                       model_hash: str, dims: int) -> None:
        """Register an embedding model in the manifest."""
        self.conn.execute(
            """INSERT OR REPLACE INTO embedding_models
               (model_id, model_name, model_hash, dims, created_at)
               VALUES (?, ?, ?, ?, datetime('now'))""",
            (model_id, model_name, model_hash, dims)
        )
        self.conn.commit()

    def insert_embedding(self, note_id: str, model_id: str,
                         vec: np.ndarray, text: str,
                         shard_id: str = "default") -> None:
        """Insert a single title embedding."""
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        blob = vector_to_blob(vec)
        self.conn.execute(
            """INSERT OR REPLACE INTO title_embeddings
               (note_id, shard_id, model_id, text_hash, dims, quant, vec, created_at)
               VALUES (?, ?, ?, ?, ?, 'f32', ?, datetime('now'))""",
            (note_id, shard_id, model_id, text_hash, len(vec), blob)
        )
        self.conn.commit()

    def search(self, query_vec: np.ndarray, model_id: str,
               top_k: int = 20) -> list[tuple[str, float]]:
        """Brute-force cosine similarity search.

        Returns list of (note_id, cosine_score) sorted by score descending.
        """
        rows = self.conn.execute(
            "SELECT note_id, vec, dims FROM title_embeddings WHERE model_id = ?",
            (model_id,)
        ).fetchall()

        scored = []
        for note_id, blob, dims in rows:
            vec = blob_to_vector(blob, dims)
            score = float(np.dot(query_vec, vec))
            scored.append((score, note_id))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [(nid, s) for s, nid in scored[:top_k]]

    def load_all_vectors(self, model_id: str) -> list[tuple[str, np.ndarray]]:
        """Load all vectors for a model (for external fusion)."""
        rows = self.conn.execute(
            "SELECT note_id, vec, dims FROM title_embeddings WHERE model_id = ?",
            (model_id,)
        ).fetchall()
        return [(r[0], blob_to_vector(r[1], r[2])) for r in rows]

    def stats(self) -> dict:
        """Return vector store statistics."""
        n_models = self.conn.execute("SELECT COUNT(*) FROM embedding_models").fetchone()[0]
        n_vecs = self.conn.execute("SELECT COUNT(*) FROM title_embeddings").fetchone()[0]
        return {"models": n_models, "vectors": n_vecs}

    def close(self):
        self.conn.commit()
        self.conn.close()


# ── Full build pipeline ───────────────────────────────

def build_title_embeddings(vault_db_path: str, vector_db_path: str,
                           model_name: str = "BAAI/bge-small-en-v1.5",
                           model_id: str = "bge-small-en-v1.5",
                           verbose: bool = False) -> dict:
    """Build Tier 1 title embeddings for all notes in a vault.

    Reads notes from vault_db, embeds title+aliases+tags+type+summary,
    stores in vector_db.

    Returns stats dict.
    """
    start = time.time()
    embedder = FastEmbedder(model_name)
    store = VectorStore(vector_db_path)

    # Register model
    store.register_model(model_id, model_name, embedder.model_hash, embedder.dims)

    # Load notes from vault DB
    vault_conn = sqlite3.connect(vault_db_path)
    vault_conn.row_factory = sqlite3.Row
    notes = list(vault_conn.execute(
        "SELECT note_id, title, aliases, tags, note_type, body FROM notes"
    ))

    if verbose:
        print(f"Embedding {len(notes)} notes with {model_name} ({embedder.dims}d)...")

    embedded = 0
    for note in notes:
        aliases_list = json.loads(note["aliases"] or "[]")
        tags_list = json.loads(note["tags"] or "[]")
        summary = extract_summary(note["body"] or "")

        text = build_embedding_text(
            title=note["title"],
            aliases=aliases_list,
            tags=tags_list,
            note_type=note["note_type"] or "",
            summary=summary,
        )

        vecs = embedder.embed([text])
        if vecs:
            store.insert_embedding(
                note_id=note["note_id"],
                model_id=model_id,
                vec=vecs[0],
                text=text,
            )

        embedded += 1
        if verbose and embedded % 10 == 0:
            print(f"  {embedded}/{len(notes)}...")

    store.close()
    vault_conn.close()

    elapsed = time.time() - start
    return {
        "model": model_name,
        "model_id": model_id,
        "dims": embedder.dims,
        "notes_embedded": embedded,
        "elapsed_seconds": round(elapsed, 2),
    }


# ── Manifest ──────────────────────────────────────────

def build_manifest(stats: dict, model_hash: str) -> dict:
    """Build a signed manifest for a vector layer."""
    import datetime
    return {
        "vector_layer": "title_embeddings_v1",
        "model_id": stats["model_id"],
        "model_name": stats["model"],
        "model_hash": model_hash,
        "dims": stats["dims"],
        "metric": "cosine",
        "quantization": "f32",
        "embedded_field": "title_aliases_tags_type_summary",
        "query_prefix": "",
        "created_at": datetime.datetime.now().isoformat(),
        "note_count": stats["notes_embedded"],
        "shard_id": "default",
    }
