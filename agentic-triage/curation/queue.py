#!/usr/bin/env python3
"""Curation queue — generates a prioritized work queue from gate output.

Makes the knowledge engineer's work queue explicit.

Usage:
    python -m curation.queue /path/to/vault
    python -m curation.queue /path/to/vault --dir wiki/agents
    python -m curation.queue /path/to/vault --json
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
import json

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from curation.gate import EpistemicGate


def generate_queue(vault_path: str, directory: str = None):
    """Generate a prioritized curation queue from gate output.

    Returns list of dicts sorted by priority.
    """
    gate = EpistemicGate(vault_path)

    if directory:
        result = gate.scan_directory(directory)
    else:
        result = gate.scan()

    queue = []

    # Priority 1: Parse failures — can't even evaluate
    for pf in result.parse_failures:
        queue.append({
            "priority": 1,
            "file": pf["file"],
            "reason": pf["reason"],
            "message": pf.get("message", "")[:200],
            "action": "repair",
            "details": "Fix YAML frontmatter before evaluation is possible.",
        })

    # Priority 2: Missing required fields — structural gap
    for mf in result.missing_fields:
        queue.append({
            "priority": 2,
            "file": mf["file"],
            "reason": mf["reason"],
            "field": mf.get("field", "provenance_status"),
            "message": mf.get("message", "")[:200],
            "action": "add_metadata",
            "details": f"Add {mf.get('field', 'provenance_status')} to frontmatter.",
        })

    # Priority 3: Ineligible status — needs review
    for ie in result.ineligible_status:
        action = "review"
        if ie["reason"] == "provenance_incomplete":
            action = "review"
        elif ie["reason"] == "expired_exception":
            action = "renew_or_quarantine"
        elif ie["reason"] == "quarantined":
            action = "review_or_remove"
        elif ie["reason"] == "incomplete_exception":
            action = "complete_exception"

        queue.append({
            "priority": 3,
            "file": ie["file"],
            "reason": ie["reason"],
            "message": ie.get("message", "")[:200],
            "action": action,
            "details": ie.get("message", "Needs knowledge engineer review."),
        })

    # Priority 4: Warnings — recommendations
    for w in result.warnings:
        queue.append({
            "priority": 4,
            "file": w["file"],
            "reason": w.get("reason", "warning"),
            "message": w.get("message", "")[:200],
            "action": "review",
            "details": w.get("message", ""),
        })

    # Sort by priority
    queue.sort(key=lambda x: (x["priority"], x["file"]))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "vault": vault_path,
        "total_files": result.total_files,
        "queue_size": len(queue),
        "by_priority": {
            1: len([q for q in queue if q["priority"] == 1]),
            2: len([q for q in queue if q["priority"] == 2]),
            3: len([q for q in queue if q["priority"] == 3]),
            4: len([q for q in queue if q["priority"] == 4]),
        },
        "items": queue,
    }


def print_queue(queue_data: dict):
    """Print a human-readable curation queue."""
    print()
    print("=" * 60)
    print("  CURATION QUEUE")
    print("=" * 60)
    print(f"  Generated: {queue_data['generated_at']}")
    print(f"  Vault:     {queue_data['vault']}")
    print(f"  Files:     {queue_data['total_files']} scanned")
    print(f"  Queue:     {queue_data['queue_size']} items")
    print()

    priority_labels = {
        1: "🔴 PRIORITY 1 — Parse Failures (repair first)",
        2: "🟡 PRIORITY 2 — Missing Metadata",
        3: "🟠 PRIORITY 3 — Needs Review",
        4: "⚪ PRIORITY 4 — Warnings",
    }

    current_priority = None
    for item in queue_data["items"]:
        if item["priority"] != current_priority:
            current_priority = item["priority"]
            count = queue_data["by_priority"].get(current_priority, 0)
            if count > 0:
                print(f"  {priority_labels.get(current_priority, '')} ({count})")
                print(f"  {'─' * 50}")
        print(f"  📄 {item['file']}")
        print(f"     action: {item['action']}")
        print(f"     reason: {item['reason']}")
        if item.get("details"):
            print(f"     {item['details'][:120]}")
        print()

    # Summary
    print(f"  {'─' * 50}")
    total_p1 = queue_data["by_priority"].get(1, 0)
    if total_p1 > 0:
        print(f"  ⚠ {total_p1} files cannot be evaluated — fix YAML first.")
    total_p2 = queue_data["by_priority"].get(2, 0)
    if total_p2 > 0:
        print(f"  ⚠ {total_p2} files missing provenance_status.")
    total_p3 = queue_data["by_priority"].get(3, 0)
    if total_p3 > 0:
        print(f"  📋 {total_p3} files need knowledge engineer review.")
    print(f"  {'=' * 60}")
    print()


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m curation.queue <vault_path> [--dir <subdir>] [--json] [--limit N]")
        sys.exit(1)

    vault_path = sys.argv[1]
    output_json = "--json" in sys.argv

    directory = None
    limit = None
    for i, arg in enumerate(sys.argv):
        if arg == "--dir" and i + 1 < len(sys.argv):
            directory = sys.argv[i + 1]
        if arg == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])

    queue_data = generate_queue(vault_path, directory=directory)

    if limit:
        queue_data["items"] = queue_data["items"][:limit]
        queue_data["queue_size"] = len(queue_data["items"])

    if output_json:
        print(json.dumps(queue_data, indent=2, default=str))
    else:
        print_queue(queue_data)


if __name__ == "__main__":
    main()
