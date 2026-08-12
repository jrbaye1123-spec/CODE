#!/usr/bin/env python3
"""
emit-report.py — Assemble the final JSON strip report from a JSONL journal
                 and environment variables.

Called by strip-binaries.sh after all processing is complete.

Usage:
  python3 emit-report.py <report_file> <journal_file>

The journal file contains one JSON object per line (JSONL format),
each with a "type" field: "stripped", "skipped", or "rollback".
"""
import json
import os
import sys


def main():
    if len(sys.argv) < 3:
        print("Usage: emit-report.py <report_file> <journal_file>", file=sys.stderr)
        return 1

    report_file = sys.argv[1]
    journal_file = sys.argv[2]

    stripped = []
    skipped = []
    rollbacks = []
    scanned = 0
    total_saved = 0

    # Read the journal
    try:
        with open(journal_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                entry_type = entry.pop("type", "unknown")
                scanned += 1

                if entry_type == "stripped":
                    stripped.append(entry)
                    total_saved += entry.get("saved", 0)
                elif entry_type == "skipped":
                    skipped.append(entry)
                elif entry_type == "rollback":
                    rollbacks.append(entry)
    except FileNotFoundError:
        pass  # No journal = empty report

    # Human-readable byte total
    bytes_saved = total_saved
    if bytes_saved >= 1024 * 1024:
        bytes_human = f"{bytes_saved / (1024 * 1024):.1f} MiB"
    elif bytes_saved >= 1024:
        bytes_human = f"{bytes_saved / 1024:.1f} KiB"
    else:
        bytes_human = f"{bytes_saved} bytes"

    report = {
        "tool": "strip-binaries.sh",
        "strip_binary": os.environ.get("REPORT_STRIP_BIN", "strip"),
        "strip_flags": os.environ.get("REPORT_STRIP_FLAGS", "--strip-unneeded"),
        "target_directory": os.environ.get("REPORT_TARGET", ""),
        "manifest_source": os.environ.get("REPORT_MANIFEST", ""),
        "dry_run": os.environ.get("REPORT_DRY_RUN", "false") == "true",
        "timestamp": os.environ.get("REPORT_TIMESTAMP", ""),
        "summary": {
            "total_scanned": scanned,
            "stripped": len(stripped),
            "skipped": len(skipped),
            "rollbacks": len(rollbacks),
            "bytes_saved": total_saved,
            "bytes_saved_human": bytes_human,
        },
        "stripped": stripped,
        "skipped": skipped,
        "rollbacks": rollbacks,
    }

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    # Print summary to stderr for the bash script's output
    print(f"  Scanned:   {scanned}", file=sys.stderr)
    print(f"  Stripped:  {len(stripped)}", file=sys.stderr)
    print(f"  Skipped:   {len(skipped)}", file=sys.stderr)
    print(f"  Rollbacks: {len(rollbacks)}", file=sys.stderr)
    print(f"  Saved:     {bytes_human}", file=sys.stderr)
    print(f"  Report:    {report_file}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
