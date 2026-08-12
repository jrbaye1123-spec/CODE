#!/usr/bin/env python3
"""
Nobody Ledger — Hash-chain security apparatus.
The gate does not open. Not even God.

Built on the ledgot architecture. Three boundary rules:
    NOBODY_EVENTS = frozenset({'intrusion', 'approach'})
    ANCHOR_ADDRESSES — the three authorized bitcoin addresses
    TRIBUTE_LOOP — any other bc1 address pays tribute on entry

Zero dependencies. Standard library only.
"""

import re
from ledgot import Ledgot

NOBODY_EVENTS = frozenset({"intrusion", "approach"})

ANCHOR_ADDRESSES = frozenset({
    "bc1qh0htmhc2nxqc3wwrk4aspc7x4flatavhmp329f",
    "bc1q9azpdpzcvvxjygqs49qusnw5hmgkdaepmpuc3s",
    "bc1q3m3tp83f5xwzaynaw9tekxpcp945e9lqk5e87x",
})

BC1_PATTERN = re.compile(r"^bc1[a-z0-9]{38,90}$", re.IGNORECASE)


class NobodyLedger(Ledgot):
    """Hash chain where nobody is allowed — and unknown addresses pay tribute."""

    def __init__(self, chain_path: str = "nobody_chain.json"):
        super().__init__(
            chain_path=chain_path,
            genesis_entity="the void",
            genesis_event="genesis",
            genesis_how="The gate does not open. Not even God.",
        )

    def append(self, entity: str, event: str, how: str) -> str:
        """
        Policy layer. Three checks, in order:

        1. NOBODY_EVENTS (intrusion, approach) → auto-nullify always
        2. Unknown bc1 address → tribute loop (recorded then nullified)
        3. Anchor address or non-bc1 entity → recorded active
        """
        # Rule 1: intrusion/approach always nullified
        if event in NOBODY_EVENTS:
            h = self.raw_append(entity, event, how)
            self._auto_nullify(len(self.entries) - 1)
            return h

        # Rule 2: unknown bc1 address pays tribute
        if self._is_unknown_address(entity):
            h = self.raw_append(entity, event, how)
            self._tribute_nullify(len(self.entries) - 1)
            return h

        # Rule 3: anchor or non-address → active
        return self.raw_append(entity, event, how)

    def _is_unknown_address(self, entity: str) -> bool:
        """True if entity is a bc1 address not in the anchor set."""
        return bool(
            BC1_PATTERN.match(entity)
            and entity not in ANCHOR_ADDRESSES
        )

    def _auto_nullify(self, target_index: int):
        """After a NOBODY_EVENT, create the witness that voids it."""
        target = self.entries[target_index]
        self.nullify(
            targets=[target_index],
            authorized_by="the void",
            reason=(
                f"auto-nullify {target['event']} at index {target_index}"
            ),
        )

    def _tribute_nullify(self, target_index: int):
        """
        Unknown address tried to enter. Tribute extracted.
        The nullify IS the tribute — recorded, voided, gate remains closed.
        The loop: enter → nullify → the nullify itself is the toll paid.
        """
        target = self.entries[target_index]
        self.nullify(
            targets=[target_index],
            authorized_by="the void",
            reason=(
                f"TRIBUTE EXTRACTED — {target['entity']} attempted "
                f"'{target['event']}' — tribute paid at index {target_index} — "
                f"gate remains closed"
            ),
        )

    def intrusions(self, entity: str | None = None) -> list[dict]:
        """All intrusion events, optionally filtered by entity."""
        entries = self.by_event_type("intrusion")
        if entity:
            entries = [
                e
                for e in entries
                if entity.lower() in e["entity"].lower()
            ]
        return entries

    def tributes(self) -> list[dict]:
        """All tribute nullifications — unknown addresses that paid the toll."""
        return [
            e for e in self.entries
            if e["event"] == "nullify" and "TRIBUTE EXTRACTED" in e["how"]
        ]

    def render(self) -> str:
        active = self.active_entries
        if len(active) == 1 and active[0]["event"] == "genesis":
            return "[empty chain — only genesis, the gate is silent]"
        return super().render()

    def witness(self, entry_index: int) -> str:
        result = super().witness(entry_index)
        e = self.entries[entry_index]

        if e["event"] in NOBODY_EVENTS and self.is_nullified(entry_index):
            result += "\n   Nobody is allowed. Not even God himself."
        elif self.is_nullified(entry_index) and self._is_unknown_address(
            e["entity"]
        ):
            result += (
                "\n   ⛓ TRIBUTE LOOP — toll extracted — "
                "gate remains closed."
            )

        return result

    def record_at_gate(self, entity: str, event: str, how: str) -> str:
        """Record an event and return the witness statement."""
        idx_before = len(self.entries)
        self.append(entity, event, how)
        return self.witness(idx_before)
