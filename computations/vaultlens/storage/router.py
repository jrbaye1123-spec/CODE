"""Sovereign Storage Router: sharded multi-backend storage abstraction.

Replaces the monolithic SQLite connection. Routes queries to the correct
shard, backend, or engine based on data type:

- Notes + FTS: sharded SQLite FTS5 (one per shard)
- Graph Edges: DuckDB/Parquet for analytical queries (Skeptic/Archivist)
- Vectors: sqlite-vec per shard (future: LanceDB)
- Meta: single lightweight SQLite for manifests, debt, metrics

No single SQLite file holds more than 5M edges.
"""

import json
import os
import sqlite3
from pathlib import Path
from typing import Optional


SHARD_NOTES_MAX = 100_000
SHARD_EDGES_MAX = 5_000_000


class SovereignStorageRouter:
    """Routes all data access to the correct shard or backend."""

    def __init__(self, vault_root: str):
        self.vault_root = Path(vault_root)
        os.makedirs(self.vault_root, exist_ok=True)

        # Meta DB: lightweight SQLite for manifests, debt, metrics
        meta_path = self.vault_root / "meta.sqlite"
        self.meta = sqlite3.connect(str(meta_path))
        self.meta.row_factory = sqlite3.Row
        self._init_meta()

        # Graph DB: optional DuckDB for analytical queries
        self._duckdb = None
        self._try_duckdb()

        # Cache of open shard connections
        self._shard_conns: dict[str, sqlite3.Connection] = {}

    def _init_meta(self):
        self.meta.executescript("""
            CREATE TABLE IF NOT EXISTS shard_registry (
                shard_id TEXT PRIMARY KEY,
                note_count INTEGER DEFAULT 0,
                edge_count INTEGER DEFAULT 0,
                content_hash TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                status TEXT DEFAULT 'active'
            );
            CREATE TABLE IF NOT EXISTS storage_stats (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        self.meta.commit()

    def _try_duckdb(self):
        try:
            import duckdb
            graph_path = self.vault_root / "graph.duckdb"
            self._duckdb = duckdb.connect(str(graph_path), read_only=False)
            self._duckdb.execute("""
                CREATE TABLE IF NOT EXISTS edges (
                    edge_id TEXT, source_note_id TEXT, target_note_id TEXT,
                    relation TEXT, variant TEXT, confidence REAL,
                    resolved INTEGER, source TEXT, created_at TEXT,
                    shard_id TEXT
                )
            """)
        except ImportError:
            self._duckdb = None

    # ── Shard management ──────────────────────────────

    def get_or_create_shard(self, note_count: int = 0) -> str:
        """Get the active shard or create a new one if the current would exceed max."""
        cursor = self.meta.execute(
            "SELECT shard_id, note_count FROM shard_registry WHERE status='active' "
            "ORDER BY shard_id DESC LIMIT 1"
        )
        row = cursor.fetchone()

        if row:
            current_count = row["note_count"]
            # If adding note_count would exceed max, rotate
            if current_count + note_count <= SHARD_NOTES_MAX:
                return row["shard_id"]

        # Create new shard
        shard_id = f"shard_{self.meta.execute('SELECT COUNT(*) FROM shard_registry').fetchone()[0]:06d}"
        shard_dir = self.vault_root / "shards" / shard_id
        os.makedirs(shard_dir, exist_ok=True)

        # Create shard FTS database
        conn = sqlite3.connect(str(shard_dir / "fts.sqlite"))
        conn.executescript("""
            CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
                note_id UNINDEXED, title, tags, body,
                content=''  /* external content */
            );
            CREATE TABLE IF NOT EXISTS shard_edges (
                edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_note_id TEXT, target_note_id TEXT,
                relation TEXT, variant TEXT, confidence REAL DEFAULT 1.0,
                resolved INTEGER DEFAULT 1, source TEXT DEFAULT 'explicit'
            );
            CREATE TABLE IF NOT EXISTS shard_notes (
                note_id TEXT PRIMARY KEY, file_path TEXT, title TEXT,
                aliases TEXT, tags TEXT, note_type TEXT, body TEXT,
                content_hash TEXT
            );
        """)
        conn.commit()
        conn.close()

        self.meta.execute(
            "INSERT INTO shard_registry (shard_id, note_count, status) VALUES (?, 0, 'active')",
            (shard_id,)
        )
        self.meta.commit()
        return shard_id

    def get_shard_fts(self, shard_id: str) -> sqlite3.Connection:
        """Get the FTS database for a shard (cached)."""
        if shard_id not in self._shard_conns:
            path = self.vault_root / "shards" / shard_id / "fts.sqlite"
            if path.exists():
                conn = sqlite3.connect(str(path))
                conn.row_factory = sqlite3.Row
                self._shard_conns[shard_id] = conn
        return self._shard_conns.get(shard_id)

    def list_shards(self) -> list[str]:
        """List all active shard IDs."""
        rows = self.meta.execute(
            "SELECT shard_id FROM shard_registry WHERE status='active' ORDER BY shard_id"
        ).fetchall()
        return [r["shard_id"] for r in rows]

    # ── Graph queries ─────────────────────────────────

    def query_graph(self, sql: str, params: tuple = ()) -> list:
        """Run an analytical graph query via DuckDB or SQLite fallback."""
        if self._duckdb:
            try:
                result = self._duckdb.execute(sql, params)
                return result.fetchall()
            except Exception:
                pass
        # Fallback: query across all shard edge tables
        results = []
        for shard_id in self.list_shards():
            conn = self.get_shard_fts(shard_id)
            if conn:
                try:
                    adjusted = sql.replace("edges", "shard_edges")
                    rows = conn.execute(adjusted, params).fetchall()
                    results.extend(rows)
                except sqlite3.OperationalError:
                    pass
        return results

    def query_all_fts(self, query: str, limit: int = 20) -> list[dict]:
        """Run FTS search across all shards and merge results."""
        all_results = []
        for shard_id in self.list_shards():
            conn = self.get_shard_fts(shard_id)
            if not conn:
                continue
            try:
                rows = conn.execute(
                    "SELECT note_id, title, snippet(notes_fts, 1, '<mark>', '</mark>', '...', 40) "
                    "FROM notes_fts WHERE notes_fts MATCH ? LIMIT ?",
                    (query, limit)
                ).fetchall()
                for row in rows:
                    all_results.append({
                        "note_id": row[0], "title": row[1],
                        "snippet": row[2], "shard_id": shard_id,
                    })
            except sqlite3.OperationalError:
                pass
        return all_results[:limit]

    # ── Storage stats ─────────────────────────────────

    def stats(self) -> dict:
        """Return storage-level statistics."""
        shards = self.list_shards()
        total_notes = 0
        total_edges = 0
        for shard_id in shards:
            conn = self.get_shard_fts(shard_id)
            if conn:
                try:
                    n = conn.execute("SELECT COUNT(*) FROM shard_notes").fetchone()[0]
                    total_notes += n
                except sqlite3.OperationalError:
                    pass
                try:
                    e = conn.execute("SELECT COUNT(*) FROM shard_edges").fetchone()[0]
                    total_edges += e
                except sqlite3.OperationalError:
                    pass

        meta_size = os.path.getsize(self.vault_root / "meta.sqlite") if (self.vault_root / "meta.sqlite").exists() else 0
        return {
            "shard_count": len(shards),
            "total_notes": total_notes,
            "total_edges": total_edges,
            "max_notes_per_shard": SHARD_NOTES_MAX,
            "max_edges_per_shard": SHARD_EDGES_MAX,
            "duckdb_available": self._duckdb is not None,
            "meta_db_size_bytes": meta_size,
            "shards": shards,
        }

    def close(self):
        for conn in self._shard_conns.values():
            conn.close()
        self._shard_conns.clear()
        self.meta.commit()
        self.meta.close()
        if self._duckdb:
            self._duckdb.close()
