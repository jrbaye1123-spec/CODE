"""
Vault RAG Engine — Continuous Learning Watcher
===============================================
Watches the vault for changes and triggers re-indexing.
Can also trigger periodic fine-tuning when enough new data accumulates.

Three modes:
  1. watcher: Monitor filesystem, auto-index on changes (debounced)
  2. periodic: Cron-friendly, check for changes and update if needed
  3. trainer: Check if enough new notes accumulated → trigger fine-tune
"""

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional


VAULT = Path.home() / "Desktop/backup-20260606/vault"
RAG_DIR = Path.home() / "gpt2_moe_1m/vault_rag"
STATE_FILE = RAG_DIR / "watcher_state.json"

# Minimum new notes before triggering fine-tune
MIN_NEW_NOTES_FOR_TRAIN = 20
# Debounce: wait this many seconds after last change before re-indexing
DEBOUNCE_SECONDS = 30
# Check interval for polling mode
POLL_INTERVAL = 60  # seconds


class VaultWatcher:
    """
    Watch vault for changes and trigger learning pipeline.

    Usage:
        # One-shot check (for cron):
        watcher = VaultWatcher()
        watcher.check_and_update()

        # Continuous watch (for daemon):
        watcher.watch()
    """

    def __init__(self):
        RAG_DIR.mkdir(parents=True, exist_ok=True)
        self.state = self._load_state()
        self._last_index_time = 0

    def _load_state(self) -> dict:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text())
        return {
            "last_index_time": 0,
            "last_train_time": 0,
            "total_notes_indexed": 0,
            "total_train_pairs": 0,
            "new_notes_since_train": 0,
            "file_hashes": {},
        }

    def _save_state(self):
        STATE_FILE.write_text(json.dumps(self.state, indent=2))

    def _scan_vault(self) -> dict[str, str]:
        """Scan all .md files and compute content hashes."""
        hashes = {}
        for md_file in VAULT.rglob("*.md"):
            parts = md_file.relative_to(VAULT).parts
            if any(p in {".git", ".obsidian", ".brain", "_hermes"} for p in parts):
                continue
            try:
                h = hashlib.md5(md_file.read_bytes(), usedforsecurity=False).hexdigest()
                hashes[str(md_file.relative_to(VAULT))] = h
            except Exception:
                pass
        return hashes

    def _diff_hashes(self, current: dict[str, str]) -> dict:
        """Compare current hashes with stored state."""
        old = self.state.get("file_hashes", {})

        added = {k: v for k, v in current.items() if k not in old}
        removed = {k for k in old if k not in current}
        changed = {k: v for k, v in current.items()
                   if k in old and old[k] != v}

        return {"added": added, "removed": removed, "changed": changed}

    def _run_indexer(self):
        """Run the embedding indexer."""
        print(f"[watcher] Running indexer...", file=sys.stderr)
        result = subprocess.run(
            ["python3", str(RAG_DIR / "indexer.py"), "build"],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0:
            self.state["last_index_time"] = int(time.time())
            self._save_state()
            print(f"[watcher] Indexer complete.", file=sys.stderr)
        else:
            print(f"[watcher] Indexer failed: {result.stderr[-200:]}", file=sys.stderr)

    def _run_trainer(self):
        """Generate new training pairs if enough new notes accumulated."""
        if self.state["new_notes_since_train"] < MIN_NEW_NOTES_FOR_TRAIN:
            return

        print(f"[watcher] {self.state['new_notes_since_train']} new notes — "
              f"generating training pairs...", file=sys.stderr)

        result = subprocess.run(
            ["python3", str(RAG_DIR / "trainer.py")],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0:
            self.state["last_train_time"] = int(time.time())
            self.state["new_notes_since_train"] = 0
            self._save_state()
            print(f"[watcher] Trainer complete.", file=sys.stderr)

            # Log training data size
            for f in RAG_DIR.glob("training_data/*.jsonl"):
                lines = len(f.read_text().strip().split("\n"))
                self.state["total_train_pairs"] += lines
            self._save_state()
        else:
            print(f"[watcher] Trainer failed: {result.stderr[-200:]}", file=sys.stderr)

    # ── One-shot check (cron mode) ───────────────────────────────────

    def check_and_update(self) -> dict:
        """
        Check for changes and update if needed.
        Returns summary dict for cron job output.
        """
        current_hashes = self._scan_vault()
        diff = self._diff_hashes(current_hashes)

        total_changes = len(diff["added"]) + len(diff["removed"]) + len(diff["changed"])

        if total_changes == 0:
            print(f"[watcher] No changes detected.", file=sys.stderr)
            return {"changed": False, "changes": 0}

        print(f"[watcher] Changes: +{len(diff['added'])} "
              f"-{len(diff['removed'])} "
              f"~{len(diff['changed'])}", file=sys.stderr)

        # Update state
        self.state["file_hashes"] = current_hashes
        self.state["new_notes_since_train"] += len(diff["added"]) + len(diff["changed"])
        self._save_state()

        # Re-index
        self._run_indexer()

        # Maybe train
        self._run_trainer()

        return {
            "changed": True,
            "changes": total_changes,
            "added": len(diff["added"]),
            "removed": len(diff["removed"]),
            "changed_files": len(diff["changed"]),
            "new_notes_since_train": self.state["new_notes_since_train"],
        }

    # ── Continuous watch (daemon mode) ───────────────────────────────

    def watch(self, poll_interval: int = POLL_INTERVAL):
        """
        Continuous watch loop. Polls for changes every N seconds.
        Use for daemon/background mode.
        """
        print(f"[watcher] Starting continuous watch "
              f"(poll every {poll_interval}s)...", file=sys.stderr)

        while True:
            try:
                result = self.check_and_update()
                if result["changed"]:
                    print(f"[watcher] Updated. {result['changes']} files changed.", file=sys.stderr)
                time.sleep(poll_interval)
            except KeyboardInterrupt:
                print(f"\n[watcher] Stopped.", file=sys.stderr)
                break
            except Exception as e:
                print(f"[watcher] Error: {e}", file=sys.stderr)
                time.sleep(poll_interval * 5)  # Back off on errors


# ── CLI ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Vault continuous learning watcher")
    parser.add_argument("mode", nargs="?", default="check",
                        choices=["check", "watch", "status"],
                        help="check = one-shot, watch = continuous, status = show state")
    parser.add_argument("--interval", type=int, default=POLL_INTERVAL,
                        help=f"Poll interval in seconds (default: {POLL_INTERVAL})")
    args = parser.parse_args()

    watcher = VaultWatcher()

    if args.mode == "status":
        print(json.dumps(watcher.state, indent=2))
    elif args.mode == "check":
        result = watcher.check_and_update()
        print(json.dumps(result))
    elif args.mode == "watch":
        watcher.watch(poll_interval=args.interval)
