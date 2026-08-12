"""Alias resolution for stable note identity at scale.

When vaults grow to millions of notes, file paths change, notes get renamed,
and titles collide. A global alias table provides stable identity resolution
that survives renames, moves, and merges.

Design:
    note_id: stable internal ID (sha256 of canonical path + creation salt)
    aliases: human-readable names that resolve to note_id
    resolution: direct match → alias match → fuzzy match (optional)
"""

import hashlib
import json
import sqlite3
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class NoteIdentity:
    """Stable identity for a note, surviving renames and moves."""
    note_id: str
    title: str
    file_path: str
    content_hash: str = ""
    aliases: list[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.aliases is None:
            self.aliases = []


# ── Identity generation ────────────────────────────────

def generate_note_id(title: str, file_path: str = "", salt: str = "") -> str:
    """Generate a stable note ID.

    Uses sha256 of normalized title + optional path + salt.
    Stable across renames if the title stays the same.
    """
    normalized = title.lower().strip()
    canonical = f"{normalized}|{file_path}|{salt}"
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def compute_content_hash(body: str) -> str:
    """Content hash for a note body (used for change detection)."""
    return hashlib.sha256(body.encode()).hexdigest()[:16]


# ── Alias store ────────────────────────────────────────

ALIAS_SCHEMA = """
CREATE TABLE IF NOT EXISTS aliases (
    alias TEXT NOT NULL,
    note_id TEXT NOT NULL,
    resolution_type TEXT DEFAULT 'title',  -- 'title', 'alias', 'fuzzy', 'manual'
    confidence REAL DEFAULT 1.0,
    source TEXT DEFAULT 'frontmatter',
    created_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (alias, note_id)
);

CREATE INDEX IF NOT EXISTS idx_aliases_alias ON aliases(alias);
CREATE INDEX IF NOT EXISTS idx_aliases_note ON aliases(note_id);
"""


class AliasStore:
    """Global alias resolution table.

    Can be stored in a shared SQLite DB or per-shard.
    For MVP, use a single shared aliases.db alongside shards.
    """

    def __init__(self, db_path: str = "vault_shards/aliases.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.executescript(ALIAS_SCHEMA)
        self.conn.commit()

    def register(self, note_id: str, title: str, aliases: list[str] = None,
                 file_path: str = "") -> None:
        """Register a note and its aliases in the alias store."""
        # Register title as primary alias
        self._insert(title, note_id, "title", 1.0, "frontmatter")
        # Register explicit aliases
        for alias in (aliases or []):
            if alias.lower() != title.lower():
                self._insert(alias, note_id, "alias", 0.95, "frontmatter")
        # Register filename-based alias (without .md)
        if file_path:
            stem = os.path.splitext(os.path.basename(file_path))[0]
            if stem.lower() != title.lower():
                self._insert(stem, note_id, "filename", 0.8, "auto")

    def _insert(self, alias: str, note_id: str, res_type: str,
                confidence: float, source: str) -> None:
        """Insert or update an alias."""
        alias_key = alias.lower().strip()
        if not alias_key:
            return
        self.conn.execute(
            """INSERT OR REPLACE INTO aliases (alias, note_id, resolution_type, confidence, source)
               VALUES (?, ?, ?, ?, ?)""",
            (alias_key, note_id, res_type, confidence, source)
        )

    def resolve(self, name: str) -> Optional[str]:
        """Resolve a name to a note_id.

        Tries: exact match → case-insensitive → fuzzy (todo).

        Returns note_id or None.
        """
        name_key = name.lower().strip()

        # Exact match
        row = self.conn.execute(
            "SELECT note_id, confidence FROM aliases WHERE alias = ? ORDER BY confidence DESC LIMIT 1",
            (name_key,)
        ).fetchone()
        if row:
            return row[0]

        # Prefix match (for partial names)
        row = self.conn.execute(
            "SELECT note_id, alias, confidence FROM aliases WHERE alias LIKE ? ORDER BY confidence DESC LIMIT 1",
            (f"{name_key}%",)
        ).fetchone()
        if row:
            return row[0]

        return None

    def resolve_batch(self, names: list[str]) -> dict[str, Optional[str]]:
        """Resolve multiple names at once."""
        return {name: self.resolve(name) for name in names}

    def lookup_note(self, note_id: str) -> list[str]:
        """Get all aliases for a note."""
        rows = self.conn.execute(
            "SELECT alias FROM aliases WHERE note_id = ? ORDER BY confidence DESC",
            (note_id,)
        ).fetchall()
        return [r[0] for r in rows]

    def stats(self) -> dict:
        """Return alias store statistics."""
        total = self.conn.execute("SELECT COUNT(*) FROM aliases").fetchone()[0]
        unique_notes = self.conn.execute(
            "SELECT COUNT(DISTINCT note_id) FROM aliases"
        ).fetchone()[0]
        by_type = {}
        for row in self.conn.execute(
            "SELECT resolution_type, COUNT(*) FROM aliases GROUP BY resolution_type"
        ):
            by_type[row[0]] = row[1]
        return {
            "total_aliases": total,
            "unique_notes": unique_notes,
            "by_type": by_type,
        }

    def close(self):
        self.conn.commit()
        self.conn.close()
