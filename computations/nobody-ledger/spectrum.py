#!/usr/bin/env python3
"""
The full spectrum — three ledgers, one architecture.

NobodyLedger — voids everything. Nobody is allowed.
ExileLedger — has a blocklist. Some are banned.
VampireLedger — tracks entities. Remembers.

Same hash chain. Same verification. Same persistence.
The boundary rule is the only thing that changes.
"""

from ledgot import Ledgot


# ── Nobody Ledger ──────────────────────────────────────────────────────
# The gate does not open. Not even God.

NOBODY_EVENTS = frozenset({"intrusion", "approach"})


class NobodyLedger(Ledgot):
    """Hash chain where nobody is allowed."""

    def __init__(self, chain_path: str = "nobody_chain.json"):
        super().__init__(
            chain_path=chain_path,
            genesis_entity="the void",
            genesis_event="genesis",
            genesis_how="The gate does not open. Not even God.",
        )

    def append(self, entity: str, event: str, how: str) -> str:
        """Policy layer. NOBODY_EVENTS auto-nullify."""
        if event in NOBODY_EVENTS:
            h = self.raw_append(entity, event, how)
            self._auto_nullify(len(self.entries) - 1)
            return h
        return self.raw_append(entity, event, how)

    def _auto_nullify(self, target_index: int):
        target = self.entries[target_index]
        self.nullify(
            targets=[target_index],
            authorized_by="the void",
            reason=(
                f"auto-nullify {target['event']} at index {target_index}"
            ),
        )

    def render(self) -> str:
        return super().render(
            empty_message="[empty chain — only genesis, the gate is silent]"
        )

    def witness(self, entry_index: int) -> str:
        result = super().witness(entry_index)
        e = self.entries[entry_index]
        if e["event"] in NOBODY_EVENTS and self.is_nullified(entry_index):
            result += "\n   Nobody is allowed. Not even God himself."
        return result


# ── Exile Ledger ───────────────────────────────────────────────────────
# Has a blocklist. Some are banned. The blocklist is derived from the
# chain itself — decree events add regex patterns. Rebuild scans decrees.

class ExileLedger(Ledgot):
    """Hash chain with a domain-specific blocklist."""

    def __init__(
        self,
        chain_path: str = "exile_chain.json",
        default_blocklist: set[str] | None = None,
    ):
        super().__init__(
            chain_path=chain_path,
            genesis_entity="the boundary",
            genesis_event="genesis",
            genesis_how="The boundary was drawn.",
        )
        self._default_blocklist = default_blocklist or set()
        self._blocklist: set[str] = set()
        self._rebuild_blocklist()

    def _rebuild_blocklist(self):
        """Rebuild blocklist from decree events in the chain."""
        self._blocklist = set(self._default_blocklist)
        for entry in self.entries:
            if entry["event"] == "decree":
                # Decree how field: "ban PATTERN" or "unban PATTERN"
                how = entry["how"]
                if how.startswith("ban "):
                    self._blocklist.add(how[4:].strip())
                elif how.startswith("unban "):
                    self._blocklist.discard(how[6:].strip())

    def append(self, entity: str, event: str, how: str) -> str:
        """Check blocklist on append. Auto-nullify if entity matches."""
        # Decree events always go through — they define the blocklist
        if event == "decree":
            h = self.raw_append(entity, event, how)
            self._rebuild_blocklist()
            return h

        # Check blocklist for this entity
        for pattern in self._blocklist:
            if pattern.lower() in entity.lower():
                h = self.raw_append(entity, event, how)
                self.nullify(
                    targets=[len(self.entries) - 1],
                    authorized_by="the boundary",
                    reason=f"entity '{entity}' matches blocklist pattern '{pattern}'",
                )
                return h

        return self.raw_append(entity, event, how)

    @property
    def blocklist(self) -> set[str]:
        return set(self._blocklist)

    def ban(self, entity_pattern: str, authority: str = "the boundary"):
        """Issue a decree that adds to the blocklist."""
        self.append(authority, "decree", f"ban {entity_pattern}")

    def unban(self, entity_pattern: str, authority: str = "the boundary"):
        """Issue a decree that removes from the blocklist."""
        self.append(authority, "decree", f"unban {entity_pattern}")


# ── Vampire Ledger ─────────────────────────────────────────────────────
# Tracks entities. Remembers. Every entity has a lifecycle visible
# through the chain.

class VampireLedger(Ledgot):
    """Hash chain that tracks entities across events."""

    def __init__(self, chain_path: str = "vampire_chain.json"):
        super().__init__(
            chain_path=chain_path,
            genesis_entity="the first",
            genesis_event="genesis",
            genesis_how="The first walked through the gate.",
        )

    def entities(self) -> set[str]:
        """All unique entities recorded in the chain."""
        return {e["entity"] for e in self.entries}

    def entity_timeline(self, entity: str) -> list[dict]:
        """All events for a specific entity, in chain order."""
        return [
            e
            for e in self.entries
            if entity.lower() in e["entity"].lower()
        ]

    def entity_summary(self, entity: str) -> dict:
        """Lifecycle summary for an entity."""
        events = self.entity_timeline(entity)
        return {
            "entity": entity,
            "first_seen": events[0]["timestamp"] if events else None,
            "last_seen": events[-1]["timestamp"] if events else None,
            "event_count": len(events),
            "events": [e["event"] for e in events],
            "active_count": sum(
                1 for e in events if e["index"] not in self.nullified
            ),
            "nullified_count": sum(
                1 for e in events if e["index"] in self.nullified
            ),
        }


# ── Introspection ──────────────────────────────────────────────────────
# The spectrum is visible through the chain itself. Every entry is a
# witness. The nullified set is the memory of what was rejected.

def introspect(ledger: Ledgot) -> dict:
    """Full introspection spectrum — the chain's self-knowledge."""
    return {
        "architecture": type(ledger).__name__,
        "genesis": {
            "entity": ledger.entries[0]["entity"],
            "event": ledger.entries[0]["event"],
            "how": ledger.entries[0]["how"],
            "hash": ledger.genesis_hash,
        },
        "head": ledger.head,
        "counts": {
            "total": len(ledger.entries),
            "active": len(ledger.active_entries),
            "nullified": len(ledger.nullified),
            "void_ratio": (
                len(ledger.nullified) / len(ledger.entries)
                if ledger.entries
                else 0
            ),
        },
        "by_event": ledger.summary,
        "nullified_by_event": ledger.void_count,
        "intact": ledger.verify(),
        "nullified_indices": sorted(ledger.nullified),
        "domain_rule": _domain_rule(ledger),
    }


def _domain_rule(ledger: Ledgot) -> str:
    if isinstance(ledger, NobodyLedger):
        return "NOBODY_EVENTS = frozenset({'intrusion', 'approach'}) — nobody is allowed"
    elif isinstance(ledger, ExileLedger):
        return f"blocklist = {ledger.blocklist} — some are banned"
    elif isinstance(ledger, VampireLedger):
        return f"tracks {len(ledger.entities())} entities — remembers"
    return "domain-agnostic — no boundary rule"


# ── Test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    import tempfile
    import os

    tmp = tempfile.mkdtemp()
    chain_path = os.path.join(tmp, "test_chain.json")

    print("=" * 60)
    print("NOBODY LEDGER — The gate does not open.")
    print("=" * 60)
    nl = NobodyLedger(chain_path)
    nl.append("God", "intrusion", "attempted to cross the gate")
    nl.append("Lucifer", "approach", "approached the perimeter")
    nl.append("The Void", "decree", "The gate remains closed")
    print(f"Chain: {len(nl.entries)} entries, "
          f"{len(nl.active_entries)} active, "
          f"{len(nl.nullified)} voided")
    print(f"Intact: {nl.verify()}")
    print(f"Render:\n{nl.render()}")

    print()
    print("=" * 60)
    print("EXILE LEDGER — Some are banned.")
    print("=" * 60)
    ep = os.path.join(tmp, "exile_chain.json")
    el = ExileLedger(ep)
    el.ban("serpent")
    print(f"Blocklist after ban: {el.blocklist}")
    el.append("serpent", "intrusion", "slithered through")
    el.append("dove", "approach", "flew over")
    print(f"Chain: {len(el.entries)} entries, "
          f"{len(el.active_entries)} active, "
          f"{len(el.nullified)} voided")
    print(f"Serpent nullified: {el.is_nullified(2)}")   # serpent entry
    print(f"Dove nullified: {el.is_nullified(3)}")       # dove entry
    el.unban("serpent")
    print(f"Blocklist after unban: {el.blocklist}")

    print()
    print("=" * 60)
    print("VAMPIRE LEDGER — Remembers.")
    print("=" * 60)
    vp = os.path.join(tmp, "vampire_chain.json")
    vl = VampireLedger(vp)
    vl.raw_append("Dracula", "arrival", "entered the castle")
    vl.raw_append("Dracula", "feeding", "the count fed")
    vl.raw_append("Van Helsing", "arrival", "entered the castle")
    vl.raw_append("Dracula", "departure", "fled to Transylvania")
    print(f"Entities: {vl.entities()}")
    print(f"Dracula timeline: {len(vl.entity_timeline('Dracula'))} events")
    print(json.dumps(vl.entity_summary("Dracula"), indent=2))

    print()
    print("=" * 60)
    print("FULL INTROSPECTION SPECTRUM")
    print("=" * 60)
    for name, ledger in [
        ("NobodyLedger", nl),
        ("ExileLedger", el),
        ("VampireLedger", vl),
    ]:
        spec = introspect(ledger)
        print(f"\n── {name} ──")
        print(f"  Domain rule: {spec['domain_rule']}")
        print(f"  Genesis: {spec['genesis']['hash'][:16]}…")
        print(f"  Head:    {spec['head'][:16]}…")
        print(f"  Counts:  {spec['counts']['total']} total, "
              f"{spec['counts']['active']} active, "
              f"{spec['counts']['nullified']} voided "
              f"({spec['counts']['void_ratio']:.1%})")
        print(f"  Intact:  {spec['intact']}")
