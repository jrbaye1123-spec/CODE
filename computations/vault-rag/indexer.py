"""
Vault RAG Engine — Indexer
===========================
Builds and maintains the semantic embedding index for the vault.
Chunks markdown notes, generates embeddings via sentence-transformers,
and writes to .brain/embeddings.npz + metadata.json.

Supports:
  - Full rebuild: index all notes in wiki/, knowledge/, decisions/, etc.
  - Incremental update: index only new/changed notes since last build
  - Chunking: split long notes into overlapping chunks for better retrieval
"""

import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np

# ── Configuration ────────────────────────────────────────────────────
VAULT = Path.home() / "Desktop/backup-20260606/vault"
BRAIN = VAULT / ".brain"

# Directories to index (relative to vault root)
INDEXED_DIRS = [
    "wiki",
    "knowledge",
    "decisions",
    "conversations",
    "output",
    "raw",
    "_hermes",
]

# Directories to exclude from indexing
EXCLUDED_DIRS = {".git", ".obsidian", ".brain", "_hermes", "__pycache__", "templates"}

# Chunking parameters
CHUNK_SIZE = 256   # words per chunk
CHUNK_OVERLAP = 64  # word overlap between chunks

# Default embedding model — BGE is top of MTEB retrieval leaderboard,
# handles technical/scientific vocabulary well (quantum cosmology, spectral
# triples, information geometry — the vault's domains).
DEFAULT_MODEL = "BAAI/bge-large-en-v1.5"  # 1024-dim, 1.3GB, SOTA retrieval
# Fallback: "all-MiniLM-L6-v2" (384-dim, 80MB, fast but general-purpose)
# Fallback: "all-mpnet-base-v2" (768-dim, 420MB, good quality general)


class VaultIndexer:
    """
    Build and maintain the vault embedding index.

    Usage:
        indexer = VaultIndexer()
        indexer.build_full()       # Rebuild everything
        indexer.update()           # Incremental update
    """

    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.model_name = model_name
        self._model = None
        BRAIN.mkdir(parents=True, exist_ok=True)

    def _load_model(self):
        """Lazy-load the embedding model."""
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
            print(f"[indexer] Loading model: {self.model_name}", file=sys.stderr)
            self._model = SentenceTransformer(self.model_name)
        except ImportError:
            print("[indexer] ERROR: sentence-transformers not installed.", file=sys.stderr)
            print("  Install: uv pip install sentence-transformers", file=sys.stderr)
            sys.exit(1)

    # ── File discovery ───────────────────────────────────────────────

    def _discover_files(self) -> list[Path]:
        """Find all indexable .md files in the vault."""
        files = []
        for dir_name in INDEXED_DIRS:
            dir_path = VAULT / dir_name
            if not dir_path.exists():
                continue
            for md_file in dir_path.rglob("*.md"):
                parts = md_file.relative_to(VAULT).parts
                if any(p in EXCLUDED_DIRS for p in parts):
                    continue
                files.append(md_file)
        return sorted(files)

    # ── Content extraction ───────────────────────────────────────────

    def _extract_body(self, file_path: Path) -> str:
        """Extract body text from a markdown file, stripping frontmatter."""
        try:
            content = file_path.read_text()
        except UnicodeDecodeError:
            return ""

        if content.startswith("---"):
            parts = content.split("---", 2)
            return parts[2] if len(parts) >= 3 else content
        return content

    def _extract_frontmatter(self, file_path: Path) -> dict:
        """Extract YAML frontmatter from a markdown file."""
        try:
            content = file_path.read_text()
        except UnicodeDecodeError:
            return {}

        if not content.startswith("---"):
            return {}

        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}

        try:
            import yaml
            fm = yaml.safe_load(parts[1])
            return fm if isinstance(fm, dict) else {}
        except Exception:
            return {}

    # ── Chunking ─────────────────────────────────────────────────────

    def _chunk_text(self, text: str) -> list[str]:
        """Split text into overlapping word chunks."""
        words = text.split()
        if len(words) <= CHUNK_SIZE:
            return [text]

        chunks = []
        start = 0
        while start < len(words):
            end = min(start + CHUNK_SIZE, len(words))
            chunk = " ".join(words[start:end])
            chunks.append(chunk)
            start += CHUNK_SIZE - CHUNK_OVERLAP

        return chunks

    # ── Hashing ──────────────────────────────────────────────────────

    def _file_hash(self, file_path: Path) -> str:
        """Content hash for change detection."""
        try:
            return hashlib.md5(file_path.read_bytes(), usedforsecurity=False).hexdigest()
        except Exception:
            return ""

    def _load_hash_index(self) -> dict[str, str]:
        """Load the hash index from previous build."""
        hash_path = BRAIN / "chunk_hashes.json"
        if hash_path.exists():
            return json.loads(hash_path.read_text())
        return {}

    def _save_hash_index(self, hashes: dict[str, str]):
        """Save hash index for future incremental updates."""
        hash_path = BRAIN / "chunk_hashes.json"
        hash_path.write_text(json.dumps(hashes, indent=2))

    # ── Build ────────────────────────────────────────────────────────

    def build_full(self):
        """
        Full rebuild: index every note in the vault.
        Overwrites existing .brain/ index.
        """
        self._load_model()

        files = self._discover_files()
        print(f"[indexer] Found {len(files)} files to index", file=sys.stderr)

        all_embeddings = []
        all_metadata = []
        all_hashes = {}

        batch_texts = []
        batch_meta = []

        for i, file_path in enumerate(files):
            rel_path = str(file_path.relative_to(VAULT))
            body = self._extract_body(file_path)
            if not body.strip():
                continue

            fm = self._extract_frontmatter(file_path)
            title = fm.get("title", file_path.stem)
            tags = fm.get("tags", [])

            # Chunk long files
            chunks = self._chunk_text(body)
            for chunk_idx, chunk in enumerate(chunks):
                batch_texts.append(chunk)
                batch_meta.append({
                    "path": rel_path,
                    "chunk_index": chunk_idx,
                    "title": title,
                    "tags": tags if isinstance(tags, list) else [],
                })

            all_hashes[rel_path] = self._file_hash(file_path)

            # Batch encode every 32 chunks
            if len(batch_texts) >= 32 or i == len(files) - 1:
                if batch_texts:
                    embeddings = self._model.encode(
                        batch_texts,
                        normalize_embeddings=True,
                        show_progress_bar=False,
                    )
                    all_embeddings.append(embeddings)
                    all_metadata.extend(batch_meta)
                    print(f"[indexer]   Encoded {len(all_metadata)} chunks...", file=sys.stderr)
                    batch_texts = []
                    batch_meta = []

        # Concatenate all embeddings
        if all_embeddings:
            embeddings_array = np.concatenate(all_embeddings, axis=0)
        else:
            embeddings_array = np.array([]).reshape(0, 384)

        # Save
        np.savez_compressed(BRAIN / "embeddings.npz", embeddings=embeddings_array)

        meta = {
            "version": 2,
            "model": self.model_name,
            "chunk_size": CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
            "total_chunks": len(all_metadata),
            "total_files": len(all_hashes),
            "chunks": all_metadata,
        }
        (BRAIN / "metadata.json").write_text(json.dumps(meta, indent=2))
        (BRAIN / "indexed_at.txt").write_text(str(int(time.time())))

        self._save_hash_index(all_hashes)

        print(f"[indexer] Done. {len(all_metadata)} chunks from "
              f"{len(all_hashes)} files.", file=sys.stderr)

    def update(self) -> dict:
        """
        Incremental update: re-index only changed files.
        Loads existing index, removes deleted files, adds/updates changed files,
        saves back. Falls back to full rebuild only when the existing index is
        missing or corrupted.

        Returns:
            dict with counts: {added, removed, unchanged}
        """
        self._load_model()

        old_hashes = self._load_hash_index()
        files = self._discover_files()

        current_hashes = {}
        changed_files = []
        removed_paths = set(old_hashes.keys())

        for file_path in files:
            rel_path = str(file_path.relative_to(VAULT))
            h = self._file_hash(file_path)
            current_hashes[rel_path] = h

            if rel_path in removed_paths:
                removed_paths.discard(rel_path)

            if rel_path not in old_hashes or old_hashes[rel_path] != h:
                changed_files.append(file_path)

        stats = {
            "added": len(changed_files),
            "removed": len(removed_paths),
            "unchanged": len(current_hashes) - len(changed_files),
        }

        if not changed_files and not removed_paths:
            print(f"[indexer] No changes detected. {stats['unchanged']} files unchanged.", file=sys.stderr)
            return stats

        print(f"[indexer] Changes: +{stats['added']} -{stats['removed']} "
              f"={stats['unchanged']} unchanged", file=sys.stderr)

        # Load existing index
        emb_path = BRAIN / "embeddings.npz"
        meta_path = BRAIN / "metadata.json"

        if not emb_path.exists() or not meta_path.exists():
            print("[indexer] No existing index — full rebuild.", file=sys.stderr)
            self.build_full()
            return stats

        try:
            existing = np.load(emb_path)
            old_embeddings = existing["embeddings"]
            old_metadata = json.loads(meta_path.read_text())
            old_chunks = old_metadata["chunks"]
        except Exception as e:
            print(f"[indexer] Failed to load existing index ({e}) — full rebuild.", file=sys.stderr)
            self.build_full()
            return stats

        # Build path→chunk_indices map from old metadata
        path_to_indices = {}
        for idx, chunk_meta in enumerate(old_chunks):
            p = chunk_meta["path"]
            if p not in path_to_indices:
                path_to_indices[p] = []
            path_to_indices[p].append(idx)

        # Remove deleted files
        delete_indices = set()
        for removed_path in removed_paths:
            if removed_path in path_to_indices:
                delete_indices.update(path_to_indices[removed_path])

        # Keep only non-deleted embeddings and metadata
        keep_mask = np.ones(len(old_embeddings), dtype=bool)
        for i in delete_indices:
            keep_mask[i] = False

        new_embeddings = old_embeddings[keep_mask]
        new_chunks = [c for i, c in enumerate(old_chunks) if i not in delete_indices]

        # Remove changed files' old chunks (will be re-added)
        changed_paths = {str(f.relative_to(VAULT)) for f in changed_files}
        changed_delete_indices = set()
        for cp in changed_paths:
            if cp in path_to_indices:
                changed_delete_indices.update(path_to_indices[cp])

        keep_mask2 = np.ones(len(new_embeddings), dtype=bool)
        for i in changed_delete_indices:
            # Remap old index to new index after first deletion pass
            mapped = i - sum(1 for d in sorted(delete_indices) if d < i)
            if 0 <= mapped < len(new_embeddings):
                keep_mask2[mapped] = False

        new_embeddings = new_embeddings[keep_mask2]
        new_chunks = [c for i, c in enumerate(new_chunks) if keep_mask2[i]]

        # Encode changed files
        batch_texts = []
        batch_meta = []
        all_new_hashes = {}

        for file_path in changed_files:
            rel_path = str(file_path.relative_to(VAULT))
            body = self._extract_body(file_path)
            if not body.strip():
                all_new_hashes[rel_path] = self._file_hash(file_path)
                continue

            fm = self._extract_frontmatter(file_path)
            title = fm.get("title", file_path.stem)
            tags = fm.get("tags", [])

            chunks = self._chunk_text(body)
            for chunk_idx, chunk in enumerate(chunks):
                batch_texts.append(chunk)
                batch_meta.append({
                    "path": rel_path,
                    "chunk_index": chunk_idx,
                    "title": title,
                    "tags": tags if isinstance(tags, list) else [],
                })

            all_new_hashes[rel_path] = self._file_hash(file_path)

            # Encode in batches of 32
            if len(batch_texts) >= 32:
                embeddings = self._model.encode(
                    batch_texts, normalize_embeddings=True, show_progress_bar=False,
                )
                new_embeddings = np.concatenate([new_embeddings, embeddings], axis=0) \
                    if len(new_embeddings) > 0 else embeddings
                new_chunks.extend(batch_meta)
                print(f"[indexer]   Encoded {len(new_chunks)} total chunks...", file=sys.stderr)
                batch_texts = []
                batch_meta = []

        # Final batch
        if batch_texts:
            embeddings = self._model.encode(
                batch_texts, normalize_embeddings=True, show_progress_bar=False,
            )
            new_embeddings = np.concatenate([new_embeddings, embeddings], axis=0) \
                if len(new_embeddings) > 0 else embeddings
            new_chunks.extend(batch_meta)

        # Merge hashes
        merged_hashes = {**old_hashes}
        for removed_path in removed_paths:
            merged_hashes.pop(removed_path, None)
        merged_hashes.update(all_new_hashes)

        # Save
        np.savez_compressed(emb_path, embeddings=new_embeddings)
        meta = {
            "version": 2,
            "model": self.model_name,
            "chunk_size": CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
            "total_chunks": len(new_chunks),
            "total_files": len(merged_hashes),
            "chunks": new_chunks,
        }
        meta_path.write_text(json.dumps(meta, indent=2))
        (BRAIN / "indexed_at.txt").write_text(str(int(time.time())))
        self._save_hash_index(merged_hashes)

        print(f"[indexer] Done. {len(new_chunks)} chunks from "
              f"{len(merged_hashes)} files (incremental).", file=sys.stderr)

        return stats


# ── CLI ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Vault embedding indexer")
    parser.add_argument("action", nargs="?", default="build",
                        choices=["build", "update"],
                        help="build = full rebuild, update = incremental")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"Embedding model (default: {DEFAULT_MODEL})")
    args = parser.parse_args()

    indexer = VaultIndexer(model_name=args.model)

    if args.action == "build":
        indexer.build_full()
    elif args.action == "update":
        stats = indexer.update()
        print(json.dumps(stats))
