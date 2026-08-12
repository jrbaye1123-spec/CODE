"""Observability layer — live health dashboard for the epistemic supply chain.

The fourth implicit layer: proves the index eligibility gate is working at 3:00 AM.
- Metric: Index_Eligibility_Rate
- Alert: Red banner if rate < 100%
- Audit Trail: Signed immutable daily log

This turns the governance trilogy into an enforceable SLA.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import json
import hashlib
import os


@dataclass
class HealthSnapshot:
    """A single point-in-time health check of the index."""
    timestamp: str
    total_index_entries: int
    unvetted_entries: int
    eligibility_rate: float  # 0.0 to 1.0
    provenance_complete: bool
    degraded_outputs_count: int
    active_exceptions: int
    gate_status: str  # "healthy", "degraded", "paused"
    signed_hash: str = ""


@dataclass
class AuditEntry:
    """A signed immutable audit log entry."""
    timestamp: str
    snapshot: HealthSnapshot
    signature: str  # SHA-256 of snapshot
    previous_signature: str  # Chain to previous entry — tamper-evident


class IndexHealthMonitor:
    """Monitors the index eligibility gate and produces health snapshots.

    Proves the law is being kept. Not a document — a running system.
    """

    def __init__(self, storage_path: str = "data/observability"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.audit_log_path = self.storage_path / "audit_chain.jsonl"
        self.dashboard_path = self.storage_path / "dashboard.json"

    def take_snapshot(
        self,
        total_index_entries: int,
        unvetted_entries: int,
        degraded_outputs_count: int = 0,
        active_exceptions: int = 0,
    ) -> HealthSnapshot:
        """Take a health snapshot of the index.

        Args:
            total_index_entries: Total entries in the machine-facing index.
            unvetted_entries: Entries missing epistemic_status = approved.
            degraded_outputs_count: Outputs currently flagged provenance: degraded.
            active_exceptions: Active timeboxed exceptions.
        """
        eligibility_rate = (
            1.0 if total_index_entries == 0
            else (total_index_entries - unvetted_entries) / total_index_entries
        )
        provenance_complete = unvetted_entries == 0

        if not provenance_complete and active_exceptions > 0:
            gate_status = "degraded"
        elif not provenance_complete:
            gate_status = "paused"
        else:
            gate_status = "healthy"

        timestamp = datetime.now(timezone.utc).isoformat()

        snapshot = HealthSnapshot(
            timestamp=timestamp,
            total_index_entries=total_index_entries,
            unvetted_entries=unvetted_entries,
            eligibility_rate=eligibility_rate,
            provenance_complete=provenance_complete,
            degraded_outputs_count=degraded_outputs_count,
            active_exceptions=active_exceptions,
            gate_status=gate_status,
        )

        # Sign the snapshot
        snapshot.signed_hash = self._sign(snapshot)

        # Write to audit chain
        self._append_audit(snapshot)

        # Update dashboard
        self._update_dashboard(snapshot)

        return snapshot

    def get_current_status(self) -> dict:
        """Get the current health status for dashboard display."""
        if not self.dashboard_path.exists():
            return {
                "status": "unknown",
                "message": "No health snapshots taken yet. Run take_snapshot() first.",
                "eligibility_rate": None,
                "gate_status": "initializing",
            }

        data = json.loads(self.dashboard_path.read_text())
        eligibility_rate = data.get("eligibility_rate", 0)

        if eligibility_rate >= 1.0:
            banner = "green"
            message = "✅ Index healthy. All entries vetted. Provenance complete."
        elif eligibility_rate >= 0.95 and data.get("active_exceptions", 0) > 0:
            banner = "yellow"
            message = f"⚠️  Index degraded. {data['unvetted_entries']} unvetted entries (exceptions active)."
        else:
            banner = "red"
            message = f"🚨 INDEX PAUSED. {data['unvetted_entries']} unvetted entries. All workflows halted."

        return {
            **data,
            "banner": banner,
            "message": message,
        }

    def verify_audit_chain(self) -> dict:
        """Verify the tamper-evident audit chain.

        Checks that every entry's hash matches and the chain is unbroken.
        Returns verification status and details.
        """
        if not self.audit_log_path.exists():
            return {"verified": True, "entries": 0, "message": "No audit entries yet."}

        entries = []
        with open(self.audit_log_path) as f:
            for line in f:
                entries.append(json.loads(line))

        if not entries:
            return {"verified": True, "entries": 0, "message": "Empty audit chain."}

        failures = []
        prev_sig = None

        for i, entry in enumerate(entries):
            # Verify internal hash
            snapshot_data = entry["snapshot"]
            computed = self._hash_snapshot_data(snapshot_data)
            if computed != entry["signature"]:
                failures.append(f"Entry {i}: hash mismatch (computed={computed[:16]} != stored={entry['signature'][:16]})")

            # Verify chain link
            stored_prev = entry.get("previous_signature", "")
            if i > 0 and stored_prev != prev_sig:
                failures.append(f"Entry {i}: chain broken (expected prev={prev_sig[:16] if prev_sig else 'none'}, got={stored_prev[:16] if stored_prev else 'none'})")

            prev_sig = entry["signature"]

        return {
            "verified": len(failures) == 0,
            "entries": len(entries),
            "failures": failures,
            "first_entry": entries[0]["snapshot"]["timestamp"] if entries else None,
            "last_entry": entries[-1]["snapshot"]["timestamp"] if entries else None,
        }

    def print_dashboard(self):
        """Print a human-readable dashboard to stdout."""
        status = self.get_current_status()
        banner_map = {"green": "🟢", "yellow": "🟡", "red": "🔴"}

        print()
        print("=" * 50)
        print(f"  INDEX ELIGIBILITY DASHBOARD  {banner_map.get(status.get('banner', 'green'), '⚪')}")
        print("=" * 50)
        print(f"  Status:     {status.get('gate_status', 'unknown').upper()}")
        print(f"  Rate:       {status.get('eligibility_rate', 0):.1%}")
        print(f"  Entries:    {status.get('total_index_entries', 0)} total, {status.get('unvetted_entries', 0)} unvetted")
        print(f"  Exceptions: {status.get('active_exceptions', 0)} active")
        print(f"  Degraded:   {status.get('degraded_outputs_count', 0)} outputs")
        print(f"  Last check: {status.get('timestamp', 'never')}")
        print(f"  ──────────────────────────────────")
        print(f"  {status.get('message', '')}")
        print("=" * 50)

        # Verify audit chain
        verification = self.verify_audit_chain()
        chain_icon = "🔗" if verification["verified"] else "💔"
        print(f"  {chain_icon} Audit chain: {'VERIFIED' if verification['verified'] else 'BROKEN'} ({verification['entries']} entries)")
        if verification["failures"]:
            for f in verification["failures"]:
                print(f"    ⚠ {f}")
        print()

    # --- Internal ---

    def _sign(self, snapshot: HealthSnapshot) -> str:
        """Create a SHA-256 signature of the snapshot data."""
        data = {
            "timestamp": snapshot.timestamp,
            "total_index_entries": snapshot.total_index_entries,
            "unvetted_entries": snapshot.unvetted_entries,
            "eligibility_rate": snapshot.eligibility_rate,
            "provenance_complete": snapshot.provenance_complete,
            "degraded_outputs_count": snapshot.degraded_outputs_count,
            "active_exceptions": snapshot.active_exceptions,
            "gate_status": snapshot.gate_status,
        }
        return self._hash_snapshot_data(data)

    def _hash_snapshot_data(self, data: dict) -> str:
        """Hash snapshot data deterministically."""
        canonical = json.dumps(data, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def _append_audit(self, snapshot: HealthSnapshot):
        """Append to the tamper-evident audit chain."""
        # Get previous signature for chain linking
        prev_sig = ""
        if self.audit_log_path.exists():
            with open(self.audit_log_path) as f:
                lines = f.readlines()
                if lines:
                    last = json.loads(lines[-1])
                    prev_sig = last.get("signature", "")

        entry = AuditEntry(
            timestamp=snapshot.timestamp,
            snapshot=snapshot,
            signature=snapshot.signed_hash,
            previous_signature=prev_sig,
        )

        with open(self.audit_log_path, "a") as f:
            f.write(json.dumps({
                "timestamp": entry.timestamp,
                "snapshot": {
                    "timestamp": snapshot.timestamp,
                    "total_index_entries": snapshot.total_index_entries,
                    "unvetted_entries": snapshot.unvetted_entries,
                    "eligibility_rate": snapshot.eligibility_rate,
                    "provenance_complete": snapshot.provenance_complete,
                    "degraded_outputs_count": snapshot.degraded_outputs_count,
                    "active_exceptions": snapshot.active_exceptions,
                    "gate_status": snapshot.gate_status,
                },
                "signature": entry.signature,
                "previous_signature": entry.previous_signature,
            }) + "\n")

    def _update_dashboard(self, snapshot: HealthSnapshot):
        """Update the live dashboard JSON."""
        self.dashboard_path.write_text(json.dumps({
            "timestamp": snapshot.timestamp,
            "total_index_entries": snapshot.total_index_entries,
            "unvetted_entries": snapshot.unvetted_entries,
            "eligibility_rate": snapshot.eligibility_rate,
            "provenance_complete": snapshot.provenance_complete,
            "degraded_outputs_count": snapshot.degraded_outputs_count,
            "active_exceptions": snapshot.active_exceptions,
            "gate_status": snapshot.gate_status,
            "signed_hash": snapshot.signed_hash,
        }, indent=2))


# --- Daily Cron Job ---

def daily_health_check(index_path: str = "data/vault_index/index.json",
                       observability_path: str = "data/observability",
                       exceptions_log_path: str = "data/logs/exceptions.jsonl") -> dict:
    """Run the daily health check — designed to be called from a cron job.

    Returns a dict suitable for logging or alerting.
    """
    monitor = IndexHealthMonitor(storage_path=observability_path)

    # Count index entries
    index_file = Path(index_path)
    total = 0
    if index_file.exists():
        try:
            index_data = json.loads(index_file.read_text())
            total = len(index_data) if isinstance(index_data, list) else 0
        except (json.JSONDecodeError, FileNotFoundError):
            total = 0

    # Count unvetted entries (those without epistemic_status = approved)
    unvetted = 0
    if index_file.exists():
        try:
            index_data = json.loads(index_file.read_text())
            if isinstance(index_data, list):
                unvetted = sum(
                    1 for entry in index_data
                    if entry.get("epistemic_status") != "approved"
                )
        except (json.JSONDecodeError, FileNotFoundError):
            unvetted = 0

    # Count active exceptions
    active_exceptions = 0
    exceptions_file = Path(exceptions_log_path)
    if exceptions_file.exists():
        try:
            with open(exceptions_file) as f:
                for line in f:
                    exc = json.loads(line)
                    if not exc.get("expired", False):
                        active_exceptions += 1
        except (json.JSONDecodeError, FileNotFoundError):
            active_exceptions = 0

    # Count degraded outputs
    degraded = 0
    logs_dir = Path("data/logs")
    if logs_dir.exists():
        for output_file in logs_dir.glob("output_*.json"):
            try:
                data = json.loads(output_file.read_text())
                if data.get("provenance_level") == "degraded":
                    degraded += 1
            except (json.JSONDecodeError, FileNotFoundError):
                pass

    snapshot = monitor.take_snapshot(
        total_index_entries=total,
        unvetted_entries=unvetted,
        degraded_outputs_count=degraded,
        active_exceptions=active_exceptions,
    )

    return {
        "snapshot": {
            "timestamp": snapshot.timestamp,
            "eligibility_rate": snapshot.eligibility_rate,
            "gate_status": snapshot.gate_status,
            "total_entries": total,
            "unvetted": unvetted,
            "degraded_outputs": degraded,
            "active_exceptions": active_exceptions,
        },
        "dashboard": monitor.get_current_status(),
        "audit_chain_verified": monitor.verify_audit_chain()["verified"],
    }


# --- CLI for standalone use ---

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "check":
        result = daily_health_check()
        monitor = IndexHealthMonitor()
        monitor.print_dashboard()
        if result["snapshot"]["eligibility_rate"] < 0.95 and result["snapshot"]["active_exceptions"] == 0:
            print("🚨 CRITICAL: Index eligibility rate below 95% with no active exceptions. Gate is failing.")
            sys.exit(1)
        elif result["snapshot"]["gate_status"] == "paused":
            print("🚨 CRITICAL: Gate is PAUSED. Unvetted entries detected without exceptions.")
            sys.exit(1)
        else:
            sys.exit(0)

    elif len(sys.argv) > 1 and sys.argv[1] == "verify":
        monitor = IndexHealthMonitor()
        verification = monitor.verify_audit_chain()
        if verification["verified"]:
            print(f"🔗 Audit chain VERIFIED — {verification['entries']} entries intact")
            sys.exit(0)
        else:
            print(f"💔 Audit chain BROKEN — {len(verification['failures'])} failures")
            for f in verification["failures"]:
                print(f"  {f}")
            sys.exit(1)

    else:
        # Default: run health check and print dashboard
        result = daily_health_check()
        monitor = IndexHealthMonitor()
        monitor.print_dashboard()
