#!/usr/bin/env python3
"""
ledgot — Domain-agnostic hash-chain architecture.
The chain doesn't care what it records — it only cares that it records.

This is the reference implementation that Nobody Ledger, Exile Ledger,
and Vampire Ledger all inherit from. Same hash chain. Same verification.
Same persistence pattern. The boundary rule is domain-specific.

Zero dependencies. Standard library only.
"""

import hashlib
import json
import re
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ── Constants ──────────────────────────────────────────────────────────
MAX_ENTRIES = 10_000


def _sha256(material: str) -> str:
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Ledgot ─────────────────────────────────────────────────────────────
class Ledgot:
    """
    Domain-agnostic hash chain.

    Five-field hash material (pipe-separated, UTF-8, SHA256):
        previous_hash | timestamp | entity | event | how

    Persistence: single JSON — {entries, count, nullified_indices}

    The chain is not secured by permissions. It is secured by mathematics.
    """

    def __init__(
        self,
        chain_path: str = "ledgot_chain.json",
        genesis_entity: str = "origin",
        genesis_event: str = "genesis",
        genesis_how: str = "The chain begins.",
    ):
        self.chain_path = Path(chain_path)
        self.genesis_entity = genesis_entity
        self.genesis_event = genesis_event
        self.genesis_how = genesis_how
        self.entries: list[dict] = []
        self.nullified: set[int] = set()
        self._load_or_genesis()

    # ── Persistence ──────────────────────────────────────────────────

    def _load_or_genesis(self):
        if self.chain_path.exists():
            try:
                data = json.loads(self.chain_path.read_text())
                self.entries = data["entries"]
                rebuilt = self._rebuild_nullified()
                persisted = set(data.get("nullified_indices", []))
                self.nullified = rebuilt | persisted
            except (json.JSONDecodeError, KeyError):
                raise RuntimeError(
                    f"Corrupted chain: {self.chain_path}. "
                    "The chain is either intact or it is dead."
                )
        else:
            self._create_genesis()

    def _create_genesis(self):
        ts = _utc_now()
        entry = {
            "index": 0,
            "timestamp": ts,
            "entity": self.genesis_entity,
            "event": self.genesis_event,
            "how": self.genesis_how,
            "previous_hash": "",
            "hash": _sha256(
                f"|{ts}|{self.genesis_entity}|"
                f"{self.genesis_event}|{self.genesis_how}"
            ),
        }
        self.entries = [entry]
        self.nullified = set()
        self._save()

    def _save(self):
        payload = {
            "entries": self.entries,
            "count": len(self.entries),
            "nullified_indices": sorted(self.nullified),
        }
        self.chain_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False)
        )

    def _rebuild_nullified(self) -> set[int]:
        """Scan for NULLIFY events, parse how field for target indices."""
        result: set[int] = set()
        for entry in self.entries:
            if entry["event"] == "nullify":
                how = entry["how"]
                for token in how.replace(",", " ").split():
                    try:
                        idx = int(token)
                        if 0 <= idx < len(self.entries):
                            result.add(idx)
                    except ValueError:
                        continue
        return result

    # ── Core: raw_append ─────────────────────────────────────────────

    def raw_append(self, entity: str, event: str, how: str) -> str:
        """
        The core. Takes entity, event, how. Computes the hash.
        Appends to the staged list. Saves. Returns the hash.
        Everything else is policy layered on top.
        """
        prev_hash = self.entries[-1]["hash"] if self.entries else ""
        idx = len(self.entries)
        ts = _utc_now()
        material = f"{prev_hash}|{ts}|{entity}|{event}|{how}"
        entry_hash = _sha256(material)

        entry = {
            "index": idx,
            "timestamp": ts,
            "entity": entity,
            "event": event,
            "how": how,
            "previous_hash": prev_hash,
            "hash": entry_hash,
        }
        self.entries.append(entry)

        if len(self.entries) > MAX_ENTRIES:
            overflow = len(self.entries) - MAX_ENTRIES
            self.entries = self.entries[overflow:]
            for i, e in enumerate(self.entries):
                e["index"] = i
            self.nullified = {
                i - overflow for i in self.nullified if i >= overflow
            }

        self._save()
        return entry_hash

    # ── Nullification ────────────────────────────────────────────────

    def nullify(
        self, targets: list[int], authorized_by: str, reason: str
    ) -> str:
        """
        Append a NULLIFY event. Update the nullified set. Save.
        Returns the hash. The nullify event is itself a chain entry —
        it has a hash, a timestamp, an entity field. It is the witness
        that says: this crossed, and this was rejected.
        """
        valid = [t for t in targets if 0 <= t < len(self.entries)]
        target_str = ",".join(str(t) for t in valid)
        how = f"nullify {target_str} by {authorized_by}: {reason}"
        entry_hash = self.raw_append(authorized_by, "nullify", how)

        for t in valid:
            self.nullified.add(t)
        self._save()
        return entry_hash

    def nullify_by_entity(
        self, pattern: str, authorized_by: str = "the chain"
    ) -> list[int]:
        """Nullify all entries matching an entity pattern (case-insensitive regex)."""
        matches = [
            e["index"]
            for e in self.entries
            if re.search(pattern, e["entity"], re.IGNORECASE)
            and e["index"] not in self.nullified
        ]
        if matches:
            self.nullify(
                targets=matches,
                authorized_by=authorized_by,
                reason=f"nullify by entity pattern: {pattern}",
            )
        return matches

    # ── Total Void ───────────────────────────────────────────────────

    def total_void(self, keep_genesis: bool = True):
        """
        Void every entry. The infinite regress closer.

        Every nullify creates a new nullify event. This is the infinite
        regress. The void spawns voids. Each nullify demands its own
        nullification.

        total_void closes the loop by marking the final nullify as voided
        WITHOUT appending. The nullify event exists in the chain for audit.
        But it is not active. The loop is closed.

        The surgical manual mark says: the regress is real, but we close
        it HERE. The gap is acknowledged, not denied.
        """
        start = 1 if keep_genesis else 0
        active = [
            i for i in range(start, len(self.entries))
            if i not in self.nullified
        ]
        if active:
            self.nullify(
                targets=active,
                authorized_by="the chain",
                reason="total void — everything that crossed is voided",
            )

        # Void the nullify events too, including the one just created
        for i in range(start, len(self.entries)):
            self.nullified.add(i)

        self._save()

    # ── Queries ──────────────────────────────────────────────────────

    @property
    def head(self) -> str:
        """The master signifier. Changes with every event."""
        return self.entries[-1]["hash"] if self.entries else ""

    @property
    def genesis_hash(self) -> str:
        """Immutable anchor. If genesis doesn't match, the chain is broken."""
        return self.entries[0]["hash"] if self.entries else ""

    @property
    def active_entries(self) -> list[dict]:
        return [e for e in self.entries if e["index"] not in self.nullified]

    @property
    def nullified_entries(self) -> list[dict]:
        return [e for e in self.entries if e["index"] in self.nullified]

    def is_nullified(self, index: int) -> bool:
        return index in self.nullified

    def by_entity(self, fragment: str) -> list[dict]:
        return [
            e
            for e in self.entries
            if fragment.lower() in e["entity"].lower()
        ]

    def by_event_type(self, event_type: str) -> list[dict]:
        return [e for e in self.entries if e["event"] == event_type]

    @property
    def void_count(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in self.nullified_entries:
            event = e["event"]
            counts[event] = counts.get(event, 0) + 1
        return counts

    @property
    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in self.entries:
            event = e["event"]
            counts[event] = counts.get(event, 0) + 1
        return counts

    def last_n(self, n: int = 10) -> list[dict]:
        active = self.active_entries
        return active[-n:] if len(active) > n else active

    def to_dict(self) -> dict:
        return {
            "genesis": self.genesis_hash,
            "head": self.head,
            "count": len(self.entries),
            "active_count": len(self.active_entries),
            "nullified_count": len(self.nullified),
            "nullified_indices": sorted(self.nullified),
            "entries": self.entries,
            "active_entries": self.active_entries,
            "last_ten": self.last_n(10),
        }

    # ── Verification ─────────────────────────────────────────────────

    def verify(self) -> bool:
        """
        Linear-time verification. Checks genesis first, then every link.
        Returns True if intact. The verification is not probabilistic.
        It is deterministic. Mathematics, not trust.
        """
        if not self.entries:
            return False

        gen = self.entries[0]
        expected_gen = _sha256(
            f"|{gen['timestamp']}|{gen['entity']}|"
            f"{gen['event']}|{gen['how']}"
        )
        if gen["hash"] != expected_gen:
            return False

        for i in range(1, len(self.entries)):
            e = self.entries[i]
            prev = self.entries[i - 1]
            if e["previous_hash"] != prev["hash"]:
                return False
            material = (
                f"{e['previous_hash']}|{e['timestamp']}|"
                f"{e['entity']}|{e['event']}|{e['how']}"
            )
            if e["hash"] != _sha256(material):
                return False

        return True

    # ── Render ───────────────────────────────────────────────────────

    def render(self, empty_message: str = "[empty chain]") -> str:
        active = self.active_entries
        if not active:
            return empty_message

        lines = ["┌─ Chain (active)"]
        for i, e in enumerate(active):
            branch = "├─" if i < len(active) - 1 else "└─"
            lines.append(
                f"{branch} [{e['index']:4d}] {e['event']:14s} "
                f"{e['entity'][:28]:28s} {e['hash'][:14]}…"
            )
        return "\n".join(lines)

    def witness(self, entry_index: int) -> str:
        if entry_index < 0 or entry_index >= len(self.entries):
            return f"No entry at index {entry_index}"

        e = self.entries[entry_index]
        voided = "VOIDED" if self.is_nullified(entry_index) else "ACTIVE"

        return textwrap.dedent(f"""\
        ╔══════════════════════════════════════════════════════╗
        ║  WITNESS — Ledgot Chain                             ║
        ╠══════════════════════════════════════════════════════╣
        ║  Index:     {entry_index:<42}║
        ║  Event:     {e['event']:<42}║
        ║  Entity:    {e['entity'][:42]:<42}║
        ║  How:       {e['how'][:42]:<42}║
        ║  Hash:      {e['hash'][:42]:<42}║
        ║  Head:      {self.head[:42]:<42}║
        ║  Chain:     {len(self.entries):<42}║
        ║  Status:    {voided:<42}║
        ╚══════════════════════════════════════════════════════╝""")


# ── Domain Extensions ──────────────────────────────────────────────────
#
# NobodyLedger:  NOBODY_EVENTS = frozenset({'intrusion','approach'})
#                → append() auto-nullifies on match
#                → total_void leaves genesis alone
#
# ExileLedger:   blocklist (set of regex patterns)
#                → decree events add to blocklist
#                → rebuild scans decrees for patterns
#                → append() checks blocklist, auto-nullifies matches
#
# VampireLedger: entity tracking
#                → tracks entities across events
#                → query by entity lifecycle
#                → same hash chain, different domain rule
#
# The architecture is invariant. The boundary rule is domain-specific.
# Two lines of code define the entire prohibition.
