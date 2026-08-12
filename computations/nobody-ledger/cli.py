#!/usr/bin/env python3
"""
Nobody Ledger — The gate does not open. Not even God.

Usage:
  python3 cli.py --intrude "God" "attempted to enter"
  python3 cli.py --approach "Lucifer" "at the perimeter"
  python3 cli.py --decree "The Void" "The gate remains closed"
  python3 cli.py --witness "The Chain" "integrity verified"
  python3 cli.py --verify
  python3 cli.py --render
  python3 cli.py --export
  python3 cli.py --voided
  python3 cli.py --nullified
  python3 cli.py --by-entity God
  python3 cli.py --intrusions [ENTITY]
  python3 cli.py --total-void
  python3 cli.py --nullify 1 3 5

Event types:
  genesis    — chain origin (auto-created, index 0)
  intrusion  — boundary crossing (auto-nullified)
  approach   — perimeter approach (auto-nullified)
  decree     — reaffirms the boundary (active)
  witness    — chain self-observation (active)
  nullify    — voids a crossing (active until total-void)

Nobody is allowed. Not even God himself.
"""

import argparse
import json
import sys
from nobody_ledger import NobodyLedger


def main():
    parser = argparse.ArgumentParser(
        prog="nobody-ledger",
        description="Nobody Ledger — The gate does not open. Not even God.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Nobody is allowed.\n"
            "Not even God himself."
        ),
    )

    # ── Chain file ──────────────────────────────────────────────────
    parser.add_argument(
        "--chain",
        default="nobody_chain.json",
        metavar="PATH",
        help="Path to chain file (default: nobody_chain.json)",
    )

    # ── Recording (grouped) ─────────────────────────────────────────
    record = parser.add_argument_group("recording operations")
    record.add_argument(
        "--intrude",
        nargs=2,
        metavar=("ENTITY", "HOW"),
        help="Record an intrusion — auto-nullified",
    )
    record.add_argument(
        "--approach",
        nargs=2,
        metavar=("ENTITY", "HOW"),
        help="Record a perimeter approach — auto-nullified",
    )
    record.add_argument(
        "--decree",
        nargs=2,
        metavar=("ENTITY", "HOW"),
        help="Record a decree — active, reaffirms the boundary",
    )
    record.add_argument(
        "--witness",
        nargs=2,
        metavar=("ENTITY", "HOW"),
        help="Record a witness event — active, chain self-observation",
    )
    record.add_argument(
        "--nullify",
        nargs="+",
        type=int,
        metavar="INDEX",
        help="Nullify specific entries by index",
    )

    # ── Queries (grouped) ───────────────────────────────────────────
    query = parser.add_argument_group("query operations")
    query.add_argument(
        "--verify",
        action="store_true",
        help="Verify chain integrity — exit 0 if intact, exit 1 if broken",
    )
    query.add_argument(
        "--render",
        action="store_true",
        help="Render active chain as ASCII tree",
    )
    query.add_argument(
        "--export",
        action="store_true",
        help="Export full chain as JSON to stdout",
    )
    query.add_argument(
        "--voided",
        action="store_true",
        help="Show voided entry counts by event type",
    )
    query.add_argument(
        "--nullified-entries",
        action="store_true",
        dest="show_nullified",
        help="List every voided entry with details",
    )
    query.add_argument(
        "--by-entity",
        metavar="FRAGMENT",
        help="Filter entries by entity fragment (case-insensitive)",
    )
    query.add_argument(
        "--intrusions",
        nargs="?",
        const="",
        metavar="ENTITY",
        help="List intrusion events, optionally filtered by entity",
    )
    query.add_argument(
        "--summary",
        action="store_true",
        help="Show chain summary",
    )

    # ── Total void ──────────────────────────────────────────────────
    parser.add_argument(
        "--total-void",
        action="store_true",
        dest="total_void",
        help="Total void — only genesis remains active. The gate is silent.",
    )

    args = parser.parse_args()
    ledger = NobodyLedger(chain_path=args.chain)

    # ── Dispatch ────────────────────────────────────────────────────
    # Recording
    if args.intrude:
        entity, how = args.intrude
        print(ledger.record_at_gate(entity, "intrusion", how))

    elif args.approach:
        entity, how = args.approach
        print(ledger.record_at_gate(entity, "approach", how))

    elif args.decree:
        entity, how = args.decree
        print(ledger.record_at_gate(entity, "decree", how))

    elif args.witness:
        entity, how = args.witness
        print(ledger.record_at_gate(entity, "witness", how))

    elif args.nullify is not None:
        targets = args.nullify
        h = ledger.nullify(
            targets=targets,
            authorized_by="the void",
            reason=f"manual nullify: indices {targets}",
        )
        print(f"Nullified {len(targets)} entries. Hash: {h[:16]}…")

    # Queries
    elif args.verify:
        if ledger.verify():
            print("Chain verified intact.")
            sys.exit(0)
        else:
            print("Chain BROKEN — verification failed.")
            sys.exit(1)

    elif args.render:
        print(ledger.render())

    elif args.export:
        print(json.dumps(ledger.to_dict(), indent=2, ensure_ascii=False))

    elif args.voided:
        vc = ledger.void_count
        if not vc:
            print("No voided entries.")
        else:
            print("Voided entries by event type:")
            for event, count in sorted(vc.items()):
                print(f"  {event:12s} {count:4d}")
            print(f"  {'TOTAL':12s} {sum(vc.values()):4d}")

    elif args.show_nullified:
        ne = ledger.nullified_entries
        if not ne:
            print("No nullified entries.")
        else:
            for e in ne:
                print(
                    f"⛝ [{e['index']:4d}] {e['event']:12s} "
                    f"{e['entity'][:25]:25s}  {e['hash'][:14]}…"
                )
                print(f"     {e['how'][:72]}")

    elif args.by_entity:
        results = ledger.by_entity(args.by_entity)
        if not results:
            print(f"No entries matching entity '{args.by_entity}'.")
        else:
            for e in results:
                status = "VOIDED" if ledger.is_nullified(e["index"]) else "ACTIVE"
                print(
                    f"[{e['index']:4d}] {status:7s}  {e['event']:12s} "
                    f"{e['entity'][:25]:25s}  {e['hash'][:14]}…"
                )

    elif args.intrusions is not None:
        entity_filter = args.intrusions if args.intrusions else None
        results = ledger.intrusions(entity_filter)
        if not results:
            print("No intrusion events.")
        else:
            for e in results:
                status = "VOIDED" if ledger.is_nullified(e["index"]) else "ACTIVE"
                print(
                    f"[{e['index']:4d}] {status:7s}  {e['entity'][:25]:25s}  "
                    f"{e['how'][:40]:40s}  {e['hash'][:14]}…"
                )

    elif args.total_void:
        before = len(ledger.active_entries)
        ledger.total_void()
        after = len(ledger.active_entries)
        print("Total void complete.")
        print(f"  Before: {before} active entries")
        print(f"  After:  {after} active entry (genesis only)")
        print("  The gate is silent.")

    elif args.summary:
        s = ledger.summary
        print(
            f"Chain: {len(ledger.entries)} entries, "
            f"{len(ledger.active_entries)} active, "
            f"{len(ledger.nullified)} voided"
        )
        print(f"Genesis: {ledger.genesis_hash[:16]}…")
        print(f"Head:    {ledger.head[:16]}…")
        print("By event type:")
        for event, count in sorted(s.items()):
            print(f"  {event:12s} {count:4d}")

    # Default: render + summary line
    else:
        print(ledger.render())
        print()
        print(
            f"Entries: {len(ledger.entries)} | "
            f"Active: {len(ledger.active_entries)} | "
            f"Voided: {len(ledger.nullified)}"
        )
        print(f"Head: {ledger.head[:16]}…")


if __name__ == "__main__":
    main()
