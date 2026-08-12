#!/usr/bin/env python3
"""DS Cloud Epistemic Supply Chain — Admission Gate Scripts

Three automation hooks that implement the hard gate between raw vault content
and machine-facing index. These are the operational enforcement of the pivot:

    1. quarantine_watcher.py  — Tags new uploads as status: quarantine (State A)
    2. index_admission_gate.py — Blocks index build unless epistemic_status: approved (State B)
    3. provenance_audit.py     — Nightly scan flips degraded flag if unvetted entries exist

Usage:
    python3 quarantine_watcher.py --bucket raw-vault --watch-path /data/raw
    python3 index_admission_gate.py --vault /data/vault --output /data/index/index.json
    python3 provenance_audit.py --index /data/index/index.json --feature-flag /etc/flags/provenance_degraded

Author: Knowledge Engineer / Epistemic Control Authority
Pivot date: 2026-08-06
"""

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ─── Shared utilities ───────────────────────────────────────────────────────

def log_event(event_type: str, details: dict, log_path: str = "data/logs/epistemic_gate.jsonl"):
    """Append an immutable audit event to the epistemic gate log."""
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "details": details,
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def compute_checksum(path: str) -> str:
    """SHA-256 checksum of file contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ─── Script 1: Quarantine Watcher ──────────────────────────────────────────

def quarantine_watcher(watch_path: str, poll_interval: int = 10):
    """Watch a directory for new uploads. Tag every new file as status: quarantine.

    This implements State A (Quarantine): raw, transformable, NOT executable.
    No indexer watches this bucket. Files only become index-eligible after
    explicit epistemic review via the admission gate.

    Args:
        watch_path: Directory to monitor for new files.
        poll_interval: Seconds between scans. Default 10s.
    """
    watch = Path(watch_path)
    watch.mkdir(parents=True, exist_ok=True)

    # Track seen files by checksum to handle renames and overwrites
    seen: dict[str, str] = {}  # checksum -> filename
    quarantine_log = watch / ".quarantine_manifest.jsonl"

    print(f"[quarantine_watcher] Watching: {watch.resolve()}")
    print(f"[quarantine_watcher] Policy: All new uploads enter State A (quarantine).")

    try:
        while True:
            current_files = {
                str(f.resolve()): f.name
                for f in watch.rglob("*")
                if f.is_file()
                and not f.name.startswith(".")
                and f.suffix in (".md", ".json", ".txt")
            }

            for full_path, filename in current_files.items():
                try:
                    csum = compute_checksum(full_path)
                except (IOError, PermissionError):
                    continue

                if csum not in seen:
                    # New file detected — apply quarantine tag
                    seen[csum] = filename
                    quarantine_entry = {
                        "file": filename,
                        "path": full_path,
                        "checksum": csum,
                        "status": "quarantine",
                        "tagged_at": datetime.now(timezone.utc).isoformat(),
                        "admission_status": "pending_review",
                    }

                    with open(quarantine_log, "a") as f:
                        f.write(json.dumps(quarantine_entry) + "\n")

                    log_event("quarantine_tagged", {
                        "file": filename,
                        "checksum": csum[:16],
                        "action": "Entered State A — quarantine",
                    })

                    print(f"  [QUARANTINE] {filename} → State A (not indexable)")

            time.sleep(poll_interval)

    except KeyboardInterrupt:
        print(f"\n[quarantine_watcher] Stopped. {len(seen)} files quarantined.")


# ─── Script 2: Index Admission Gate ────────────────────────────────────────

# Required frontmatter fields for epistemic eligibility
REQUIRED_PROVENANCE_FIELDS = [
    "provenance_status",
    "source_classification",
    "reviewer",
    "reviewed_at",
]

# Fields additionally required when provenance_level is "exception"
EXCEPTION_FIELDS = [
    "exception_owner",
    "exception_expires_at",
    "exception_reason",
]

# Valid provenance status values
VALID_PROVENANCE_STATUS = {"verified", "exception"}

# Valid source classifications
VALID_SOURCE_CLASSIFICATIONS = {"governed", "derived", "exception"}


def _parse_frontmatter_safe(filepath: Path) -> tuple[Optional[dict], Optional[str]]:
    """Try to parse frontmatter from a note file.

    Returns:
        (metadata_dict, error_string). If successful, error is None.
        If the parser fails or frontmatter is malformed, metadata is None.
    """
    try:
        text = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return None, f"File read error: {e}"

    try:
        import frontmatter as fm
        post = fm.loads(text)
        return (dict(post.metadata) if post.metadata else {}, None)
    except ImportError:
        return None, "Parser unavailable — install python-frontmatter"
    except Exception as e:
        return None, f"Parse error: {e}"


def _check_eligibility(metadata: dict, filepath: Path) -> tuple[bool, list[str]]:
    """Check if a note's frontmatter satisfies epistemic eligibility.

    Returns:
        (is_eligible, list_of_rejection_reasons)
    """
    reasons = []

    # Check required fields exist and are non-empty
    for field in REQUIRED_PROVENANCE_FIELDS:
        val = metadata.get(field)
        if val is None or (isinstance(val, str) and not val.strip()):
            reasons.append(f"missing_required_field: {field}")

    # Check provenance_status value
    ps = metadata.get("provenance_status", "")
    if ps and ps not in VALID_PROVENANCE_STATUS:
        reasons.append(f"invalid_provenance_status: '{ps}' (expected: verified | exception)")

    # Check source_classification value
    sc = metadata.get("source_classification", "")
    if sc and sc not in VALID_SOURCE_CLASSIFICATIONS:
        reasons.append(f"invalid_source_classification: '{sc}' (expected: governed | derived | exception)")

    # If exception, require additional fields
    if ps == "exception":
        for field in EXCEPTION_FIELDS:
            val = metadata.get(field)
            if val is None or (isinstance(val, str) and not val.strip()):
                reasons.append(f"missing_exception_field: {field}")

        # Check expiry
        expires = metadata.get("exception_expires_at")
        if expires:
            try:
                from datetime import datetime as dt
                expiry = dt.fromisoformat(str(expires).replace("Z", "+00:00"))
                if expiry < dt.now(timezone.utc):
                    reasons.append("exception_expired")
            except (ValueError, TypeError):
                reasons.append("invalid_exception_expiry_date")

    return (len(reasons) == 0, reasons)


def index_admission_gate(
    vault_path: str,
    output_path: str,
    mode: str = "audit",
    alert_webhook: Optional[str] = None,
):
    """Build the machine-facing index from epistemically-approved notes.

    Two modes:
      - audit: Report eligibility counts and rejection reasons. Never fails.
               Safe for rollout while metadata schema is stabilizing.
      - enforce: Hard gate. Fails if any candidate for indexing is unvetted,
                 unparsable, or missing required provenance fields. Parse
                 failures are treated as provenance failures.

    Implements the transition from State A (quarantine) to State B (index).

    Args:
        vault_path: Root of the vault/wiki directory.
        output_path: Where to write the index JSON (enforce mode, if passed).
        mode: 'audit' or 'enforce'.
        alert_webhook: Optional Slack/Teams webhook URL for blocking alerts.

    Returns:
        dict with gate report including eligibility breakdown.
    """
    vault = Path(vault_path)
    output = Path(output_path)

    if not vault.exists():
        print(f"[admission_gate] ERROR: Vault path not found: {vault}")
        sys.exit(1)

    if mode not in ("audit", "enforce"):
        print(f"[admission_gate] ERROR: Unknown mode '{mode}'. Use 'audit' or 'enforce'.")
        sys.exit(1)

    # ── Scan and classify every note ──
    total_notes = 0
    parsed_ok = 0
    parse_failed = 0
    parse_errors: list[dict] = []
    eligible = 0
    eligible_entries: list[dict] = []
    rejected = 0
    rejection_reasons: dict[str, int] = {}
    rejected_entries: list[dict] = []

    for note_file in sorted(vault.rglob("*.md")):
        # Skip agent-writeable directories and hidden files
        if any(part.startswith(".") for part in note_file.parts):
            continue
        if any(skip in str(note_file) for skip in ["triage-reports", "provenance-logs", "tension-reports"]):
            continue

        total_notes += 1
        metadata, parse_error = _parse_frontmatter_safe(note_file)

        if parse_error or metadata is None:
            parse_failed += 1
            parse_errors.append({
                "path": str(note_file),
                "error": parse_error or "Unknown parse failure",
            })
            rejected += 1
            if "parse_failed" not in rejection_reasons:
                rejection_reasons["parse_failed"] = 0
            rejection_reasons["parse_failed"] += 1
            rejected_entries.append({
                "path": str(note_file),
                "title": note_file.stem,
                "rejection_reasons": [parse_error or "parse_failed"],
            })
            continue

        parsed_ok += 1
        is_eligible, reasons = _check_eligibility(metadata, note_file)

        if is_eligible:
            eligible += 1
            eligible_entries.append({
                "path": str(note_file),
                "title": metadata.get("title", note_file.stem),
                "provenance_status": metadata.get("provenance_status"),
                "source_classification": metadata.get("source_classification"),
                "reviewer": metadata.get("reviewer"),
                "reviewed_at": metadata.get("reviewed_at"),
            })
        else:
            rejected += 1
            for reason in reasons:
                rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
            rejected_entries.append({
                "path": str(note_file),
                "title": metadata.get("title", note_file.stem),
                "rejection_reasons": reasons,
            })

    # ── Compute Index Eligibility Rate ──
    index_eligibility_rate = eligible / total_notes if total_notes > 0 else 0.0

    # ── Build gate report ──
    gate = "index-eligibility"
    report = {
        "gate": gate,
        "mode": mode,
        "build_timestamp": datetime.now(timezone.utc).isoformat(),
        "vault_path": str(vault.resolve()),
        "total_notes": total_notes,
        "parsed_ok": parsed_ok,
        "parse_failed": parse_failed,
        "missing_required_fields": rejection_reasons.get("missing_required_field", 0),
        "eligible": eligible,
        "rejected": rejected,
        "index_eligibility_rate": round(index_eligibility_rate, 4),
        "rejection_reasons": rejection_reasons,
        "rejected_entries": rejected_entries[:50],  # Cap for readability
        "parse_errors": parse_errors[:50],
        "build_status": "",
        "index_path": None,
        "governance_action": "",
    }

    # ── Audit mode: report only, never fail ──
    if mode == "audit":
        report["build_status"] = "AUDIT — REPORT ONLY"
        report["governance_action"] = (
            f"Audit complete. {eligible}/{total_notes} notes eligible "
            f"({index_eligibility_rate:.1%}). {rejected} rejected: "
            + ", ".join(f"{k}: {v}" for k, v in sorted(rejection_reasons.items()))
            + ". Switch to enforce mode when metadata schema is stable."
        )
        report["index_path"] = None

        log_event("gate_audit", {
            "mode": "audit",
            "total": total_notes,
            "eligible": eligible,
            "rejected": rejected,
            "parse_failed": parse_failed,
        })

        print(f"[admission_gate] AUDIT: {eligible}/{total_notes} eligible ({index_eligibility_rate:.1%})")
        print(f"[admission_gate] {parsed_ok} parsed, {parse_failed} parse failures, {rejected} rejected")
        if rejection_reasons:
            for reason, count in sorted(rejection_reasons.items()):
                print(f"  - {reason}: {count}")
        if parse_errors:
            print(f"[admission_gate] ⚠ {parse_failed} parse failures (install python-frontmatter to resolve)")

    # ── Enforce mode: hard gate ──
    else:  # enforce
        failures = []

        if parse_failed > 0:
            failures.append(f"parse_failed: {parse_failed} notes could not be parsed")
        if rejected > 0:
            failures.append(f"rejected: {rejected} notes failed epistemic eligibility")
        if eligible == 0 and total_notes > 0:
            failures.append("eligible: 0 — no notes passed the gate (check parser and metadata schema)")

        if failures:
            report["build_status"] = "BLOCKED — EPISTEMIC GATE FAILED"
            report["governance_action"] = (
                f"Gate enforcement blocked index build. "
                + "; ".join(failures)
                + ". All dependent outputs flagged as provenance: degraded. "
                "Epistemic control owner must resolve before rebuild."
            )

            alert_msg = (
                f"⛔ INGESTION BLOCKED — EPISTEMIC GATE (enforce mode)\n"
                f"   Vault: {vault}\n"
                f"   Parsed: {parsed_ok}, Parse failures: {parse_failed}\n"
                f"   Eligible: {eligible}, Rejected: {rejected}\n"
            )
            for reason, count in sorted(rejection_reasons.items()):
                alert_msg += f"   - {reason}: {count}\n"

            log_event("gate_blocked_enforce", report)

            if alert_webhook:
                _send_webhook(alert_webhook, alert_msg)
            else:
                print(f"\n{alert_msg}")
                for entry in rejected_entries[:10]:
                    print(f"   REJECTED: {entry['title']} — {', '.join(entry['rejection_reasons'])}")
                if len(rejected_entries) > 10:
                    print(f"   ... and {len(rejected_entries) - 10} more")
        else:
            # Build index from eligible entries
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(eligible_entries, indent=2, ensure_ascii=False))

            report["build_status"] = "PASSED — EPISTEMIC GATE CLEARED"
            report["index_path"] = str(output.resolve())
            report["governance_action"] = f"Index built successfully. {eligible} entries with verified provenance."

            log_event("gate_passed_enforce", {
                "eligible": eligible,
                "output": str(output.resolve()),
            })

            print(f"[admission_gate] ENFORCE PASSED: {eligible} approved notes indexed.")
            print(f"[admission_gate] Index: {output.resolve()}")

    # Write gate report
    report_dir = output.parent if mode == "enforce" else Path("data/logs")
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"gate_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps(report, indent=2))
    report["report_path"] = str(report_path.resolve())

    return report


# ─── Script 3: Provenance Audit ────────────────────────────────────────────

def provenance_audit(
    index_path: str,
    feature_flag_path: Optional[str] = None,
    alert_webhook: Optional[str] = None,
):
    """Nightly scan of the machine-facing index for unvetted entries.

    If any entry has provenance_status != "verified", the provenance_degraded
    feature flag is flipped ON, and all outputs will carry the
    ⚠️ PROVENANCE DEGRADED header until cleared.

    This implements the ongoing enforcement: the index must never silently
    contain unvetted content.

    Args:
        index_path: Path to the current index JSON file.
        feature_flag_path: Path to a feature flag file. If provided, the flag
                          is set to "on" when degraded entries are found.
        alert_webhook: Optional Slack/Teams webhook for alerts.
    """
    index_file = Path(index_path)
    flag_file = Path(feature_flag_path) if feature_flag_path else None

    if not index_file.exists():
        print(f"[provenance_audit] No index found at {index_file}. Skipping audit.")
        return {"status": "no_index", "unvetted_count": 0}

    entries = json.loads(index_file.read_text())
    unvetted = [e for e in entries if e.get("provenance_status") != "verified"]
    verified = [e for e in entries if e.get("provenance_status") == "verified"]

    report = {
        "audit_timestamp": datetime.now(timezone.utc).isoformat(),
        "index_path": str(index_file.resolve()),
        "total_entries": len(entries),
        "verified_entries": len(verified),
        "unvetted_entries": len(unvetted),
        "unvetted_detail": [
            {
                "path": e["path"],
                "title": e["title"],
                "provenance_status": e.get("provenance_status", "unknown"),
                "admission_authority": e.get("admission_authority", "none"),
            }
            for e in unvetted
        ],
        "degraded_flag_set": False,
        "action": "",
    }

    if unvetted:
        # Flip the degraded flag
        if flag_file:
            flag_file.parent.mkdir(parents=True, exist_ok=True)
            flag_file.write_text("on")
            report["degraded_flag_set"] = True

        report["action"] = (
            f"PROVENANCE DEGRADED: {len(unvetted)} unvetted entries found. "
            "All outputs flagged with ⚠️ PROVENANCE DEGRADED until cleared. "
            "Epistemic control owner must review and approve or quarantine."
        )

        alert_msg = (
            f"⚠️  PROVENANCE DEGRADED\n"
            f"   Index: {index_file}\n"
            f"   Unvetted entries: {len(unvetted)}/{len(entries)}\n"
            f"   Action: Degraded flag ON. Outputs carry warning until resolved.\n"
        )
        for e in unvetted[:5]:
            alert_msg += f"   - {e['title']} ({e.get('provenance_status', 'unknown')})\n"
        if len(unvetted) > 5:
            alert_msg += f"   ... and {len(unvetted) - 5} more\n"

        log_event("provenance_degraded", report)

        if alert_webhook:
            _send_webhook(alert_webhook, alert_msg)
        else:
            print(f"\n{alert_msg}")

    else:
        # Clear the degraded flag
        if flag_file and flag_file.exists():
            flag_file.write_text("off")
            report["degraded_flag_set"] = False

        report["action"] = "All entries verified. Provenance status: clean."
        log_event("provenance_clean", report)
        print(f"[provenance_audit] CLEAN: {len(entries)} entries, all verified.")

    # Write audit report
    audit_log = index_file.parent / f"audit_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    audit_log.write_text(json.dumps(report, indent=2))

    return report


def _send_webhook(url: str, message: str):
    """Send alert to Slack/Teams webhook. Best-effort, non-blocking."""
    try:
        import urllib.request
        payload = json.dumps({"text": message}).encode()
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f"[webhook] Failed to send alert: {e}")


# ─── CLI ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="DS Cloud Epistemic Supply Chain — Admission Gate Scripts",
        epilog="Data is input. Knowledge is approved input. The index must never confuse the two.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # quarantine_watcher
    qw = sub.add_parser("quarantine", help="Watch directory, tag new uploads as quarantine")
    qw.add_argument("--watch-path", required=True, help="Directory to monitor")
    qw.add_argument("--poll-interval", type=int, default=10, help="Seconds between scans")

    # index_admission_gate
    ig = sub.add_parser("admit", help="Build index with epistemic admission gate")
    ig.add_argument("--vault", required=True, help="Path to vault/wiki root")
    ig.add_argument("--output", required=True, help="Path for index JSON output")
    ig.add_argument("--mode", choices=["audit", "enforce"], default="audit",
                    help="Gate mode: audit (report only) or enforce (hard fail)")
    ig.add_argument("--alert-webhook", help="Slack/Teams webhook for blocking alerts")

    # provenance_audit
    pa = sub.add_parser("audit", help="Nightly provenance audit of the index")
    pa.add_argument("--index", required=True, help="Path to index JSON")
    pa.add_argument("--feature-flag", help="Path to feature flag file")
    pa.add_argument("--alert-webhook", help="Slack/Teams webhook for alerts")

    args = parser.parse_args()

    if args.command == "quarantine":
        quarantine_watcher(args.watch_path, args.poll_interval)
    elif args.command == "admit":
        result = index_admission_gate(
            args.vault, args.output, mode=args.mode, alert_webhook=args.alert_webhook
        )
        if result["build_status"].startswith("BLOCKED"):
            sys.exit(1)
    elif args.command == "audit":
        result = provenance_audit(args.index, args.feature_flag, args.alert_webhook)
        if result["unvetted_entries"] > 0:
            sys.exit(1)


if __name__ == "__main__":
    main()
