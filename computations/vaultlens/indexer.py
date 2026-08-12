"""Indexer: builds the SQLite database from a directory of markdown notes.

Incremental indexing using content hashes to avoid re-processing unchanged files.
"""

import os
import hashlib
import sqlite3
import json
import time
from pathlib import Path
from typing import Optional

from .parser import parse_note, ParsedNote
from .graph_store import GraphStore


def _hash_content(content: str) -> str:
    """SHA-256 hash of note content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _resolve_target(note_id: str, target_title: str, title_to_id: dict[str, str],
                    alias_to_id: dict[str, str]) -> tuple[Optional[str], str]:
    """Resolve a link target title to a note ID.

    Returns:
        (resolved_note_id or None, match_type: 'title', 'alias', 'unresolved')
    """
    # Direct title match
    from .parser import _generate_note_id
    target_slug = _generate_note_id(target_title)
    if target_slug in title_to_id:
        return title_to_id[target_slug], "title"

    # Alias match
    if target_title.lower() in alias_to_id:
        return alias_to_id[target_title.lower()], "alias"

    return None, "unresolved"


def index_vault(vault_path: str, db_path: str = ".vaultlens/vaultlens.db",
                rebuild: bool = False, verbose: bool = False) -> dict:
    """Index a directory of markdown notes into the VaultLens database.

    Args:
        vault_path: Path to directory containing .md files
        db_path: Path to SQLite database file
        rebuild: If True, drop and recreate all tables
        verbose: Print progress information

    Returns:
        Dict with indexing statistics
    """
    start_time = time.time()

    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    # Connect to database
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # Load schema
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path) as f:
        schema_sql = f.read()

    if rebuild:
        conn.executescript("DROP TABLE IF EXISTS notes_fts; DROP TABLE IF EXISTS eval_results; DROP TABLE IF EXISTS eval_runs; DROP TABLE IF EXISTS edges; DROP TABLE IF EXISTS proposals; DROP TABLE IF EXISTS notes; DROP TABLE IF EXISTS query_log;")
    conn.executescript(schema_sql)

    # Build lookup maps: title -> note_id, alias -> note_id
    title_to_id: dict[str, str] = {}
    alias_to_id: dict[str, str] = {}

    # Load existing notes for incremental update
    existing_hashes: dict[str, str] = {}  # file_path -> content_hash
    cursor = conn.execute("SELECT file_path, content_hash FROM notes")
    for row in cursor:
        existing_hashes[row[0]] = row[1]

    # Find all markdown files
    vault = Path(vault_path)
    md_files = sorted(vault.rglob("*.md"))

    stats = {
        "total_files": len(md_files),
        "new_files": 0,
        "updated_files": 0,
        "skipped_files": 0,
        "errors": 0,
        "total_notes": 0,
        "total_edges": 0,
        "unresolved_links": 0,
        "variants_found": {},
    }

    # First pass: parse all notes, build title->id map
    parsed_notes: list[tuple[Path, ParsedNote]] = []
    for md_file in md_files:
        try:
            rel_path = str(md_file.relative_to(vault))
            content = md_file.read_text(encoding="utf-8")
            content_hash = _hash_content(content)

            # Skip unchanged files (incremental)
            if not rebuild and rel_path in existing_hashes and existing_hashes[rel_path] == content_hash:
                stats["skipped_files"] += 1
                # Still need to load existing note for title map
                cursor = conn.execute(
                    "SELECT note_id, title, aliases FROM notes WHERE file_path = ?", (rel_path,)
                )
                row = cursor.fetchone()
                if row:
                    note_id, title, aliases_json = row
                    title_to_id[note_id] = note_id  # use note_id as slug
                    if title.lower():
                        title_to_id[title.lower().replace(" ", "-")] = note_id
                    if aliases_json:
                        for alias in json.loads(aliases_json or "[]"):
                            alias_to_id[alias.lower()] = note_id
                continue

            note = parse_note(str(rel_path), content)
            parsed_notes.append((md_file, note))

            # Update title maps
            title_to_id[note.note_id] = note.note_id
            title_slug = note.title.lower().replace(" ", "-")
            if title_slug != note.note_id:
                title_to_id[title_slug] = note.note_id
            for alias in note.aliases:
                alias_to_id[alias.lower()] = note.note_id

            if rel_path in existing_hashes:
                stats["updated_files"] += 1
            else:
                stats["new_files"] += 1
        except Exception as e:
            stats["errors"] += 1
            if verbose:
                print(f"  ERROR parsing {md_file}: {e}")

    # Second pass: insert notes and resolve links
    for md_file, note in parsed_notes:
        rel_path = str(md_file.relative_to(vault))

        try:
            # Upsert note
            aliases_json = json.dumps(note.aliases)
            tags_json = json.dumps(note.tags)

            conn.execute("""
                INSERT OR REPLACE INTO notes (note_id, file_path, title, aliases, tags, note_type, created_at, modified_at, content_hash, body)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                note.note_id, rel_path, note.title, aliases_json, tags_json,
                note.note_type, note.created_at or "", note.modified_at or "",
                _hash_content(md_file.read_text(encoding="utf-8")), note.body
            ))

            stats["total_notes"] += 1

            # Insert edges from typed relations
            for rel in note.typed_relations:
                target_id, match_type = _resolve_target(
                    note.note_id, rel["target"], title_to_id, alias_to_id
                )
                resolved = 1 if target_id is not None else 0

                conn.execute("""
                    INSERT INTO edges (source_note_id, target_note_id, target_title, relation, variant, text_span, file_path, line_number, resolved)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    note.note_id,
                    target_id,
                    rel["target"] if not resolved else None,
                    rel["relation"],
                    rel["variant"],
                    rel["text_span"],
                    rel_path,
                    rel["line_number"],
                    resolved,
                ))

                stats["total_edges"] += 1
                variant_count = stats["variants_found"].get(rel["variant"], 0)
                stats["variants_found"][rel["variant"]] = variant_count + 1

                if not resolved:
                    stats["unresolved_links"] += 1

            # Insert edges from regular wikilinks (untyped -> generic variant)
            for link in note.links:
                # Skip if already captured as typed relation
                target = link["target"]
                already_typed = any(
                    r["target"] == target for r in note.typed_relations
                )
                if already_typed:
                    continue

                target_id, match_type = _resolve_target(
                    note.note_id, target, title_to_id, alias_to_id
                )
                resolved = 1 if target_id is not None else 0

                conn.execute("""
                    INSERT INTO edges (source_note_id, target_note_id, target_title, relation, variant, text_span, file_path, line_number, resolved)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    note.note_id,
                    target_id,
                    target if not resolved else None,
                    "links-to",
                    "generic",
                    link["text_span"],
                    rel_path,
                    link["line_number"],
                    resolved,
                ))

                stats["total_edges"] += 1
                variant_count = stats["variants_found"].get("generic", 0)
                stats["variants_found"]["generic"] = variant_count + 1

                if not resolved:
                    stats["unresolved_links"] += 1

        except Exception as e:
            stats["errors"] += 1
            if verbose:
                print(f"  ERROR inserting {md_file}: {e}")

    conn.commit()

    # v0.2: Load approved edges from sidecar YAML and JSONL
    sidecar_stats = _load_approved_edges(conn, vault, title_to_id, alias_to_id, stats)
    stats = sidecar_stats

    # Rebuild FTS after bulk insert (FTS5 with content= external table needs manual sync)
    conn.execute("INSERT INTO notes_fts(notes_fts) VALUES ('rebuild')")
    conn.commit()

    elapsed = time.time() - start_time
    stats["elapsed_seconds"] = round(elapsed, 2)
    stats["db_size_bytes"] = os.path.getsize(db_path) if os.path.exists(db_path) else 0

    conn.close()
    return stats


def _load_approved_edges(conn: sqlite3.Connection, vault: Path,
                         title_to_id: dict[str, str], alias_to_id: dict[str, str],
                         stats: dict) -> dict:
    """Load approved edges from sidecar .vaultlens.yaml files and .vaultlens/approved_edges.jsonl.

    Sidecar files: <note>.vaultlens.yaml
    JSONL: .vaultlens/approved_edges.jsonl
    """
    edges_loaded = 0

    # 1. Load from .vaultlens/approved_edges.jsonl
    jsonl_path = vault / ".vaultlens" / "approved_edges.jsonl"
    if jsonl_path.exists():
        try:
            # Verify integrity before loading
            from .proposal_security import verify_jsonl_integrity, get_secret
            secret = get_secret()
            integrity = verify_jsonl_integrity(str(jsonl_path), secret)
            if not integrity["valid"]:
                if integrity["tampered"]:
                    print(f"  WARNING: {len(integrity['tampered'])} signed proposals have been tampered with!")
                if integrity["errors"]:
                    for err in integrity["errors"]:
                        print(f"  WARNING: {err}")

            for line in jsonl_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                edge = json.loads(line)

                # Skip tampered edges if secret is set
                stored_sig = edge.get("signature", "")
                if secret and stored_sig:
                    from .proposal_security import verify_proposal
                    if not verify_proposal(edge, secret, stored_sig):
                        continue

                edges_loaded += _insert_approved_edge(
                    conn, edge, title_to_id, alias_to_id, "jsonl"
                )
        except Exception:
            pass

    # 2. Load from sidecar .vaultlens.yaml files
    for sidecar in sorted(vault.rglob("*.vaultlens.yaml")):
        try:
            content = sidecar.read_text(encoding="utf-8")
            # Simple YAML parsing (avoid PyYAML dependency)
            edges_data = _parse_simple_yaml_edges(content)
            for edge in edges_data:
                edges_loaded += _insert_approved_edge(
                    conn, edge, title_to_id, alias_to_id, "sidecar"
                )
        except Exception:
            pass

    stats["sidecar_edges_loaded"] = edges_loaded
    return stats


def _insert_approved_edge(conn: sqlite3.Connection, edge: dict,
                          title_to_id: dict[str, str], alias_to_id: dict[str, str],
                          source_type: str) -> int:
    """Insert a single approved edge into the database. Returns 1 if inserted."""
    source_title = edge.get("source_title", "")
    target_title = edge.get("target", edge.get("target_title", ""))
    relation = edge.get("relation", "links-to")
    variant = edge.get("variant", "generic")
    confidence = edge.get("confidence", 1.0)
    evidence = edge.get("evidence_span", "")
    proposal_id = edge.get("proposal_id", "")

    # Generate note IDs
    from .parser import _generate_note_id
    source_id = _generate_note_id(source_title)
    target_id = _generate_note_id(target_title)

    # Resolve targets
    source_resolved, _ = _resolve_target("", source_title, title_to_id, alias_to_id)
    target_resolved, _ = _resolve_target("", target_title, title_to_id, alias_to_id)

    if source_resolved:
        source_id = source_resolved
    if target_resolved:
        target_id = target_resolved

    resolved = 1 if target_resolved else 0

    try:
        conn.execute("""
            INSERT INTO edges (source_note_id, target_note_id, target_title, relation,
                              variant, text_span, file_path, line_number, confidence,
                              resolved, source, proposal_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            source_id,
            target_id if resolved else None,
            target_title if not resolved else None,
            relation,
            variant,
            evidence,
            f"_{source_type}_",
            0,
            confidence,
            resolved,
            f"approved_{source_type}",
            proposal_id or "",
        ))
        return 1
    except sqlite3.IntegrityError:
        return 0


def _parse_simple_yaml_edges(content: str) -> list[dict]:
    """Parse approved_edges from a simple YAML structure without PyYAML."""
    edges = []
    in_edges = False
    current_edge: dict = {}

    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("approved_edges:"):
            in_edges = True
            continue
        if in_edges:
            if stripped.startswith("- relation:") or stripped.startswith("- target:"):
                if current_edge:
                    edges.append(current_edge)
                    current_edge = {}
            if ":" in stripped:
                key, _, value = stripped.partition(":")
                key = key.strip().lstrip("-").strip()
                value = value.strip().strip('"').strip("'")
                current_edge[key] = value

    if current_edge:
        edges.append(current_edge)
    return edges


def print_stats(stats: dict) -> None:
    """Pretty-print indexing statistics."""
    print(f"\n{'='*60}")
    print(f"  VaultLens Indexing Complete")
    print(f"{'='*60}")
    print(f"  Files scanned:    {stats['total_files']:>6d}")
    print(f"  New files:        {stats['new_files']:>6d}")
    print(f"  Updated files:    {stats['updated_files']:>6d}")
    print(f"  Skipped:          {stats['skipped_files']:>6d}")
    print(f"  Errors:           {stats['errors']:>6d}")
    print(f"  Total notes:      {stats['total_notes']:>6d}")
    print(f"  Total edges:      {stats['total_edges']:>6d}")
    print(f"  Unresolved links: {stats['unresolved_links']:>6d}")
    if stats.get("variants_found"):
        print(f"\n  Variants:")
        for variant, count in sorted(stats["variants_found"].items()):
            print(f"    {variant:20s} {count:>6d}")
    if stats.get("sidecar_edges_loaded"):
        print(f"\n  Sidecar edges loaded: {stats['sidecar_edges_loaded']}")
    print(f"\n  Time: {stats['elapsed_seconds']}s")
    size_mb = stats.get("db_size_bytes", 0) / (1024 * 1024)
    print(f"  DB size: {size_mb:.2f} MB")
    print(f"{'='*60}\n")
