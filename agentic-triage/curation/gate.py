#!/usr/bin/env python3
"""Epistemic Gate — actionable index eligibility scanner with file-level diagnostics.

Scans the vault for:
- parse_failed: YAML frontmatter that can't be parsed
- missing_required_field: Notes missing provenance_status
- ungoverned: Notes without complete provenance

Outputs file-level rejection details so every block can be fixed without hunting.
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
import frontmatter


# Required fields for index eligibility
REQUIRED_FIELDS = [
    "provenance_status",  # complete | incomplete | exception
]

# Valid provenance_status values
VALID_STATUSES = {"complete", "incomplete", "exception", "quarantined"}

# Additional recommended fields (warned but not blocked)
RECOMMENDED_FIELDS = [
    "provenance_level",   # verified | degraded | exception | unknown
    "source",             # [[linked-source-note]]
    "reviewer",           # @knowledge-engineer
    "reviewed_at",        # YYYY-MM-DD
]


class GateResult:
    """Result of running the epistemic gate against the vault."""

    def __init__(self):
        self.mode = "enforce"
        self.total_files = 0
        self.parse_failures: list[dict] = []
        self.missing_fields: list[dict] = []
        self.ineligible_status: list[dict] = []
        self.eligible: list[dict] = []
        self.warnings: list[dict] = []
        self.passed = True

    @property
    def parse_failed_count(self) -> int:
        return len(self.parse_failures)

    @property
    def missing_field_count(self) -> int:
        return len(self.missing_fields)

    @property
    def ineligible_count(self) -> int:
        return len(self.ineligible_status)

    @property
    def eligible_count(self) -> int:
        return len(self.eligible)

    @property
    def rejected_count(self) -> int:
        return self.parse_failed_count + self.missing_field_count + self.ineligible_count

    def to_dict(self) -> dict:
        return {
            "gate": "index-eligibility",
            "mode": self.mode,
            "passed": self.passed,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_files": self.total_files,
            "parse_failed": self.parse_failed_count,
            "missing_required_field": self.missing_field_count,
            "ineligible_status": self.ineligible_count,
            "eligible": self.eligible_count,
            "rejected": self.rejected_count,
            "rejections": {
                "parse_failures": self.parse_failures,
                "missing_fields": self.missing_fields,
                "ineligible_status": self.ineligible_status,
            },
            "warnings": self.warnings,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


class EpistemicGate:
    """Scans vault for index eligibility with actionable file-level diagnostics."""

    def __init__(self, vault_path: str, quarantine_path: Optional[str] = None):
        self.vault_path = Path(vault_path)
        self.quarantine_path = Path(quarantine_path) if quarantine_path else None

    def scan(self, paths: Optional[list[Path]] = None, file_pattern: str = "*.md") -> GateResult:
        """Scan vault for index eligibility.

        Args:
            paths: Specific paths to scan (default: entire vault).
            file_pattern: Glob pattern for note files.

        Returns:
            GateResult with file-level rejection details.
        """
        result = GateResult()

        if paths:
            files = paths
        else:
            files = list(self.vault_path.rglob(file_pattern))

        # Exclude quarantine directory
        if self.quarantine_path:
            files = [f for f in files if not str(f).startswith(str(self.quarantine_path))]

        result.total_files = len(files)

        for file_path in sorted(files):
            try:
                self._check_file(file_path, result)
            except Exception as e:
                result.parse_failures.append({
                    "file": str(file_path.relative_to(self.vault_path)),
                    "absolute_path": str(file_path),
                    "reason": "parse_failed",
                    "message": str(e),
                })

        # Gate decision
        result.passed = (
            result.parse_failed_count == 0
            and result.missing_field_count == 0
            and result.ineligible_count == 0
        )

        return result

    def scan_directory(self, directory: str) -> GateResult:
        """Scan a specific directory within the vault."""
        dir_path = self.vault_path / directory
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {dir_path}")
        return self.scan(paths=list(dir_path.rglob("*.md")))

    def scan_file(self, file_path: str) -> GateResult:
        """Scan a single file."""
        full_path = self.vault_path / file_path if not file_path.startswith(str(self.vault_path)) else Path(file_path)
        return self.scan(paths=[full_path])

    def _check_file(self, file_path: Path, result: GateResult):
        """Check a single file for index eligibility."""
        rel_path = str(file_path.relative_to(self.vault_path))

        # Parse frontmatter
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            post = frontmatter.loads(content)
            metadata = post.metadata or {}
        except Exception as e:
            result.parse_failures.append({
                "file": rel_path,
                "absolute_path": str(file_path),
                "reason": "parse_failed",
                "message": str(e),
            })
            return

        # Check required field: provenance_status
        if "provenance_status" not in metadata:
            result.missing_fields.append({
                "file": rel_path,
                "absolute_path": str(file_path),
                "reason": "missing_required_field",
                "field": "provenance_status",
                "message": "No provenance_status in frontmatter. Add: provenance_status: complete|incomplete|exception|quarantined",
            })
            return

        # Check provenance_status value
        status = str(metadata["provenance_status"]).strip().lower()
        if status not in VALID_STATUSES:
            result.ineligible_status.append({
                "file": rel_path,
                "absolute_path": str(file_path),
                "reason": "invalid_provenance_status",
                "field": "provenance_status",
                "value": status,
                "valid_values": sorted(VALID_STATUSES),
                "message": f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}",
            })
            return

        # Status-specific checks
        if status == "complete":
            # Recommendation: have reviewer and reviewed_at
            missing_rec = []
            if "reviewer" not in metadata:
                missing_rec.append("reviewer")
            if "reviewed_at" not in metadata:
                missing_rec.append("reviewed_at")
            if missing_rec:
                result.warnings.append({
                    "file": rel_path,
                    "reason": "missing_recommended_field",
                    "fields": missing_rec,
                    "message": f"provenance_status is 'complete' but missing recommended fields: {missing_rec}. Add reviewer and reviewed_at for full auditability.",
                })
            result.eligible.append({
                "file": rel_path,
                "status": status,
                "index_eligible": True,
            })

        elif status == "exception":
            # Must have exception_owner and exception_expires_at
            exception_issues = []
            if "exception_owner" not in metadata:
                exception_issues.append("exception_owner")
            if "exception_expires_at" not in metadata:
                exception_issues.append("exception_expires_at")
            if exception_issues:
                result.ineligible_status.append({
                    "file": rel_path,
                    "absolute_path": str(file_path),
                    "reason": "incomplete_exception",
                    "missing_fields": exception_issues,
                    "message": f"Exception requires: exception_owner AND exception_expires_at. Missing: {exception_issues}",
                })
            else:
                # Check if exception is expired
                try:
                    expiry = metadata["exception_expires_at"]
                    if isinstance(expiry, str) and expiry < datetime.now(timezone.utc).strftime("%Y-%m-%d"):
                        result.ineligible_status.append({
                            "file": rel_path,
                            "absolute_path": str(file_path),
                            "reason": "expired_exception",
                            "expires_at": expiry,
                            "message": f"Exception expired on {expiry}. Renew or quarantine.",
                        })
                    else:
                        result.eligible.append({
                            "file": rel_path,
                            "status": status,
                            "index_eligible": True,
                            "degraded": True,
                        })
                except (ValueError, TypeError):
                    result.warnings.append({
                        "file": rel_path,
                        "reason": "unparseable_expiry",
                        "message": f"Cannot parse exception_expires_at. Use YYYY-MM-DD format.",
                    })

        elif status == "incomplete":
            result.ineligible_status.append({
                "file": rel_path,
                "absolute_path": str(file_path),
                "reason": "provenance_incomplete",
                "message": "Note marked incomplete. Complete provenance review or set to quarantined.",
            })

        elif status == "quarantined":
            result.ineligible_status.append({
                "file": rel_path,
                "absolute_path": str(file_path),
                "reason": "quarantined",
                "message": "Note is quarantined. Review and promote to complete or keep in quarantine.",
            })


def print_gate_report(result: GateResult):
    """Print a human-readable gate report to stdout."""
    passed = result.passed
    banner = "🟢" if passed else "🔴"

    print()
    print("=" * 60)
    print(f"  {banner} EPISTEMIC GATE — INDEX ELIGIBILITY SCAN")
    print("=" * 60)
    print(f"  Mode:    {result.mode}")
    print(f"  Files:   {result.total_files} scanned")
    print(f"  Parse:   {result.parse_failed_count} failed, {result.total_files - result.parse_failed_count} ok")
    print(f"  Status:  {result.eligible_count} eligible, {result.rejected_count} rejected")
    print(f"  Gate:    {'PASSED' if passed else 'BLOCKED'}")
    print()

    # Parse failures
    if result.parse_failures:
        print(f"  ── PARSE FAILURES ({result.parse_failed_count}) ──")
        for pf in result.parse_failures[:10]:
            print(f"  📄 {pf['file']}")
            print(f"     reason: {pf['reason']}")
            print(f"     {pf['message'][:120]}")
        if result.parse_failed_count > 10:
            print(f"  ... and {result.parse_failed_count - 10} more")
        print()

    # Missing required fields
    if result.missing_fields:
        print(f"  ── MISSING provenance_status ({result.missing_field_count}) ──")
        for mf in result.missing_fields[:5]:
            print(f"  📄 {mf['file']}")
            print(f"     add: provenance_status: complete|incomplete|exception|quarantined")
        if result.missing_field_count > 5:
            print(f"  ... and {result.missing_field_count - 5} more")
        print()

    # Ineligible status
    if result.ineligible_status:
        print(f"  ── INELIGIBLE STATUS ({result.ineligible_count}) ──")
        for ie in result.ineligible_status[:5]:
            print(f"  📄 {ie['file']}")
            print(f"     reason: {ie['reason']}")
            print(f"     {ie.get('message', '')[:120]}")
        if result.ineligible_count > 5:
            print(f"  ... and {result.ineligible_count - 5} more")
        print()

    # Warnings
    if result.warnings:
        print(f"  ── WARNINGS ({len(result.warnings)}) ──")
        for w in result.warnings[:5]:
            print(f"  📄 {w['file']}")
            print(f"     {w['message'][:120]}")
        if len(result.warnings) > 5:
            print(f"  ... and {len(result.warnings) - 5} more")
        print()

    # Eligible
    if result.eligible:
        print(f"  ── ELIGIBLE ({result.eligible_count}) ──")
        for e in result.eligible[:3]:
            degraded = " ⚠️ DEGRADED" if e.get("degraded") else ""
            print(f"  ✅ {e['file']} ({e['status']}{degraded})")
        if result.eligible_count > 3:
            print(f"  ... and {result.eligible_count - 3} more")

    print()
    print(f"  Gate result: {'✅ PASSED' if passed else '⛔ BLOCKED'}")
    print("=" * 60)


# --- CLI ---

def main():
    if len(sys.argv) < 2:
        print("Usage: python -m curation.gate <vault_path> [--json] [--dir <subdir>] [--file <file>]")
        print()
        print("Examples:")
        print("  python -m curation.gate /home/nakamichi/workspace/rbaye/vault")
        print("  python -m curation.gate /home/nakamichi/workspace/rbaye/vault --json")
        print("  python -m curation.gate /home/nakamichi/workspace/rbaye/vault --dir wiki/agents")
        print("  python -m curation.gate /home/nakamichi/workspace/rbaye/vault --file wiki/agents/axiom-taxonomy.md")
        sys.exit(1)

    vault_path = sys.argv[1]
    output_json = "--json" in sys.argv

    # Directory or file filter
    dir_filter = None
    file_filter = None
    for i, arg in enumerate(sys.argv):
        if arg == "--dir" and i + 1 < len(sys.argv):
            dir_filter = sys.argv[i + 1]
        if arg == "--file" and i + 1 < len(sys.argv):
            file_filter = sys.argv[i + 1]

    gate = EpistemicGate(vault_path)

    if file_filter:
        result = gate.scan_file(file_filter)
    elif dir_filter:
        result = gate.scan_directory(dir_filter)
    else:
        result = gate.scan()

    if output_json:
        print(result.to_json())
    else:
        print_gate_report(result)

    sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
