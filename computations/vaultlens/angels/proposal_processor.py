"""Proposal Processor: ingests queued proposals and creates new edges.

Reads from the proposals table, validates against existing edges,
and creates new edges with HMAC signatures through the standard pipeline.
This allows the graph to grow autonomously from its own queue.
"""

import sqlite3
import json
import os
from datetime import datetime


def process_proposals(vault_db_path: str, batch_size: int = 10,
                      min_confidence: float = 0.3,
                      dry_run: bool = True) -> dict:
    """Process pending proposals and create new edges.

    Args:
        vault_db_path: Path to vault SQLite database
        batch_size: Max proposals to process per run
        min_confidence: Minimum confidence to auto-approve
        dry_run: If True, only report what would change

    Returns:
        Dict with processed, created, skipped, rejected counts
    """
    conn = sqlite3.connect(vault_db_path)
    conn.row_factory = sqlite3.Row

    # Check if proposals table exists
    try:
        proposals = conn.execute(
            "SELECT * FROM proposals WHERE status = 'pending' "
            "ORDER BY confidence DESC LIMIT ?",
            (batch_size,)
        ).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return {"processed": 0, "created": 0, "skipped": 0, "rejected": 0,
                "error": "No proposals table found"}

    stats = {"processed": 0, "created": 0, "skipped": 0, "rejected": 0,
             "details": []}

    for prop in proposals:
        pid = prop["proposal_id"]
        stats["processed"] += 1

        confidence = float(prop["confidence"] or 0.5)
        source_title = str(prop["source_title"] or "")
        target_title = str(prop["target_title"] or "")

        if confidence < min_confidence:
            if not dry_run:
                conn.execute(
                    "UPDATE proposals SET status = 'rejected', "
                    "reviewed_at = datetime('now') WHERE proposal_id = ?",
                    (pid,)
                )
            stats["rejected"] += 1
            stats["details"].append(
                f"REJECTED {pid}: confidence {confidence:.2f} < {min_confidence}"
            )
            continue

        # Check if edge already exists
        from ..parser import _generate_note_id
        source_id = _generate_note_id(source_title)
        target_id = _generate_note_id(target_title)

        existing = conn.execute(
            "SELECT COUNT(*) FROM edges WHERE source_note_id = ? "
            "AND target_note_id = ? AND relation = ?",
            (source_id, target_id, prop["relation"])
        ).fetchone()[0]

        if existing > 0:
            if not dry_run:
                conn.execute(
                    "UPDATE proposals SET status = 'duplicate', "
                    "reviewed_at = datetime('now') WHERE proposal_id = ?",
                    (pid,)
                )
            stats["skipped"] += 1
            stats["details"].append(
                f"SKIPPED {pid}: edge {source_title} --{prop['relation']}--> "
                f"{target_title} already exists"
            )
            continue

        # Create edge
        if not dry_run:
            # Write to approved JSONL
            vault_dir = os.path.dirname(vault_db_path)
            jsonl_path = os.path.join(vault_dir, "approved_edges.jsonl")

            edge_record = {
                "source_title": source_title,
                "target": target_title,
                "relation": prop["relation"],
                "variant": prop["variant"],
                "confidence": confidence,
                "evidence_span": (prop["evidence_span"] or ""),
                "proposal_id": pid,
                "approved_at": datetime.now().isoformat(),
            }

            # Sign if secret available
            from ..proposal_security import sign_proposal, get_secret
            secret = get_secret()
            if secret:
                edge_record["signature"] = sign_proposal(edge_record, secret)

            os.makedirs(os.path.dirname(jsonl_path) or ".", exist_ok=True)
            with open(jsonl_path, "a") as f:
                f.write(json.dumps(edge_record) + "\n")

            # Mark proposal as approved
            conn.execute(
                "UPDATE proposals SET status = 'approved', "
                "reviewed_at = datetime('now') WHERE proposal_id = ?",
                (pid,)
            )

        stats["created"] += 1
        stats["details"].append(
            f"CREATED {pid}: {source_title} --{prop['relation']}--> "
            f"{target_title} ({prop['variant']}, conf={confidence:.2f})"
        )

    if not dry_run:
        conn.commit()

    conn.close()
    return stats
