"""Shard manager: partitions vaults into bounded, verifiable units.

Each shard is the atomic unit of indexing, backup, verification, and rebuild.
Shards contain: notes, edges, FTS index, vectors (optional), manifest, signatures.

Architecture:
    vault_shards/
      shard_000000/
        notes.parquet      (or .sqlite for small scale)
        edges.parquet
        fts.sqlite
        vectors.sqlite     (future)
        manifest.json
        manifest.sig
"""

import json
import hashlib
import os
import sqlite3
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


# ── Configuration ──────────────────────────────────────

DEFAULT_SHARD_SIZE = 100_000      # notes per shard
DEFAULT_SHARD_DIR = "vault_shards"
VALID_SCHEMA_VERSION = "0.3.0"


@dataclass
class ShardManifest:
    """Metadata and integrity record for a single shard."""
    shard_id: str
    note_count: int = 0
    edge_count: int = 0
    content_hash: str = ""
    schema_version: str = VALID_SCHEMA_VERSION
    created_at: str = ""
    note_range_start: Optional[str] = None
    note_range_end: Optional[str] = None
    variant_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "shard_id": self.shard_id,
            "note_count": self.note_count,
            "edge_count": self.edge_count,
            "content_hash": self.content_hash,
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "note_range_start": self.note_range_start,
            "note_range_end": self.note_range_end,
            "variant_counts": self.variant_counts,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ShardManifest":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ── Shard planner ──────────────────────────────────────

def plan_shards(vault_path: str, shard_size: int = DEFAULT_SHARD_SIZE,
                output_dir: Optional[str] = None) -> list[dict]:
    """Analyze a vault and produce a shard plan.

    Reads all .md files, sorts by path for determinism, assigns to shards.
    Does NOT write anything — returns a plan for review.

    Args:
        vault_path: Path to markdown vault
        shard_size: Notes per shard
        output_dir: Where shard directories will live (default: vault_path/vault_shards)

    Returns:
        List of {"shard_id": str, "note_count": int, "files": [str, ...]}
    """
    vault = Path(vault_path)
    md_files = sorted(vault.rglob("*.md"))

    if output_dir is None:
        output_dir = str(vault / DEFAULT_SHARD_DIR)

    shards = []
    for i in range(0, len(md_files), shard_size):
        batch = md_files[i:i + shard_size]
        shard_id = f"shard_{i // shard_size:06d}"
        shards.append({
            "shard_id": shard_id,
            "note_count": len(batch),
            "files": [str(f.relative_to(vault)) for f in batch],
            "output_dir": str(Path(output_dir) / shard_id),
            "note_range_start": str(batch[0].relative_to(vault)),
            "note_range_end": str(batch[-1].relative_to(vault)),
        })

    return shards


def print_shard_plan(shards: list[dict]) -> None:
    """Pretty-print a shard plan."""
    total_notes = sum(s["note_count"] for s in shards)
    print(f"\n{'='*60}")
    print(f"  Shard Plan: {len(shards)} shards, {total_notes:,} notes")
    print(f"{'='*60}")
    for s in shards:
        print(f"  {s['shard_id']}: {s['note_count']:,} notes")
        print(f"    range: {s['note_range_start']} → {s['note_range_end']}")
        print(f"    output: {s['output_dir']}")
    print(f"{'='*60}\n")


# ── Manifest operations ─────────────────────────────────

def create_manifest(shard_id: str, note_count: int, edge_count: int,
                    variant_counts: Optional[dict] = None,
                    note_range_start: Optional[str] = None,
                    note_range_end: Optional[str] = None) -> ShardManifest:
    """Create a signed manifest for a shard."""
    import datetime
    manifest = ShardManifest(
        shard_id=shard_id,
        note_count=note_count,
        edge_count=edge_count,
        schema_version=VALID_SCHEMA_VERSION,
        created_at=datetime.datetime.now().isoformat(),
        note_range_start=note_range_start,
        note_range_end=note_range_end,
        variant_counts=variant_counts or {},
    )
    # Compute content hash from the manifest fields (excludes hash itself)
    canonical = json.dumps({
        k: v for k, v in manifest.to_dict().items()
        if k not in ("content_hash",)
    }, sort_keys=True)
    manifest.content_hash = hashlib.sha256(canonical.encode()).hexdigest()[:32]
    return manifest


def write_manifest(manifest: ShardManifest, shard_dir: str) -> str:
    """Write manifest.json to shard directory. Returns path."""
    os.makedirs(shard_dir, exist_ok=True)
    path = os.path.join(shard_dir, "manifest.json")
    with open(path, "w") as f:
        json.dump(manifest.to_dict(), f, indent=2)
    return path


def read_manifest(shard_dir: str) -> Optional[ShardManifest]:
    """Read and validate a manifest from a shard directory."""
    path = os.path.join(shard_dir, "manifest.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        data = json.load(f)
    manifest = ShardManifest.from_dict(data)
    # Verify hash
    canonical = json.dumps({
        k: v for k, v in data.items()
        if k not in ("content_hash",)
    }, sort_keys=True)
    expected_hash = hashlib.sha256(canonical.encode()).hexdigest()[:32]
    if manifest.content_hash != expected_hash:
        raise ValueError(f"Manifest hash mismatch for {manifest.shard_id}: "
                         f"stored={manifest.content_hash[:8]} computed={expected_hash[:8]}")
    return manifest


def verify_all_manifests(shards_dir: str) -> dict:
    """Verify all manifests in a shards directory.

    Returns:
        {"valid": int, "invalid": int, "missing": int, "details": [...]}
    """
    result = {"valid": 0, "invalid": 0, "missing": 0, "details": []}
    base = Path(shards_dir)
    if not base.exists():
        result["missing"] = -1
        result["details"].append(f"Shards directory not found: {shards_dir}")
        return result

    for shard_dir in sorted(base.iterdir()):
        if not shard_dir.is_dir():
            continue
        try:
            manifest = read_manifest(str(shard_dir))
            if manifest is None:
                result["missing"] += 1
                result["details"].append(f"{shard_dir.name}: no manifest")
            else:
                result["valid"] += 1
                result["details"].append(
                    f"{shard_dir.name}: OK ({manifest.note_count} notes, "
                    f"{manifest.edge_count} edges, hash={manifest.content_hash[:8]})"
                )
        except (ValueError, json.JSONDecodeError) as e:
            result["invalid"] += 1
            result["details"].append(f"{shard_dir.name}: INVALID — {e}")

    return result


# ── Shard-level SQLite ─────────────────────────────────

SHARD_SCHEMA = """
CREATE TABLE IF NOT EXISTS shard_notes (
    note_id TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    title TEXT NOT NULL,
    aliases TEXT,
    tags TEXT,
    note_type TEXT,
    body TEXT,
    content_hash TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS shard_fts USING fts5(
    note_id UNINDEXED,
    title,
    tags,
    body,
    content='shard_notes',
    content_rowid='rowid'
);

CREATE TABLE IF NOT EXISTS shard_edges (
    edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_note_id TEXT NOT NULL,
    target_note_id TEXT,
    relation TEXT NOT NULL,
    variant TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    resolved INTEGER DEFAULT 1,
    source TEXT DEFAULT 'explicit'
);
"""


def create_shard_db(shard_dir: str) -> sqlite3.Connection:
    """Create a fresh shard SQLite database."""
    os.makedirs(shard_dir, exist_ok=True)
    db_path = os.path.join(shard_dir, "shard.db")
    conn = sqlite3.connect(db_path)
    conn.executescript(SHARD_SCHEMA)
    conn.commit()
    return conn
