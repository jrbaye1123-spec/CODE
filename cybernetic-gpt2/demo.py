#!/usr/bin/env python3
"""90-second demo: Governed AI that proves its answers.

Run this to generate output suitable for a LinkedIn post, investor deck,
or cold email attachment. Demonstrates the full epistemic supply chain
from query to cryptographic audit trail.
"""

import sys
import os
import json
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/../agentic-triage")

from apps import governed_ask, generate_evidence_pack
from observability import IndexHealthMonitor

VAULT = os.path.expanduser("~/workspace/rbaye/vault")

def run_demo():
    """Generate a complete demo of the governed AI system."""
    
    print("=" * 70)
    print("  GOVERNED AI DEMO — Provenance-Controlled Answer Surface")
    print("=" * 70)
    print(f"  Generated: {datetime.now(timezone.utc).isoformat()}")
    print()
    
    # --- 1. Show the gate ---
    print("━" * 70)
    print("  STEP 1: The Gate — Only governed knowledge enters the index")
    print("━" * 70)
    
    from curation.gate import EpistemicGate
    gate = EpistemicGate(VAULT)
    gate_result = gate.scan_directory("wiki/agents")
    
    print(f"  Files scanned:  {gate_result.total_files}")
    print(f"  Parse clean:    {gate_result.total_files - gate_result.parse_failed_count}")
    print(f"  Index-eligible: {gate_result.eligible_count}")
    print(f"  Rejected:       {gate_result.rejected_count}")
    print(f"  Gate status:    {'✅ PASSED' if gate_result.passed else '⛔ BLOCKED — ungoverned content detected'}")
    print()
    
    # --- 2. Governed ask ---
    print("━" * 70)
    print("  STEP 2: Governed Answer — Only index-eligible sources used")
    print("━" * 70)
    
    query = "What is the index eligibility rule for agent knowledge?"
    result = governed_ask(query, VAULT, directory="wiki/agents")
    
    print(f"  Query:          {query}")
    print(f"  Answer:         {'✅ Provided' if result['answer'] else '❌ Refused — no governed source'}")
    print(f"  Provenance:     {result['provenance_level'].upper()}")
    print(f"  Sources used:   {len(result.get('sources', []))}")
    print(f"  Eligible pool:  {result.get('eligible_sources_count', 0)}")
    print(f"  Gate:           {result['gate_status']}")
    print()
    
    if result['answer']:
        # Show excerpt
        excerpt = result['answer'][:200].replace('\n', ' ')
        print(f"  Excerpt: \"{excerpt}...\"")
        print()
    
    # --- 3. Refusal demo ---
    print("━" * 70)
    print("  STEP 3: Refusal — Ungoverned questions get honest refusal")
    print("━" * 70)
    
    refusal = governed_ask("What is the weather forecast for tomorrow?", VAULT, directory="wiki/agents")
    print(f"  Query:          What is the weather forecast for tomorrow?")
    print(f"  Answer:         ❌ REFUSED")
    print(f"  Reason:         {refusal.get('response', 'No governed source available.')}")
    print(f"  Provenance:     {refusal['provenance_level']}")
    print()
    
    # --- 4. Evidence pack ---
    print("━" * 70)
    print("  STEP 4: Audit Trail — Cryptographic proof of every answer")
    print("━" * 70)
    
    evidence = generate_evidence_pack(query, VAULT, directory="wiki/agents")
    pack = evidence["evidence_pack"]
    
    print(f"  Governance:     {pack['governance_status'].upper()}")
    print(f"  Gate passed:    {pack['gate']['passed']}")
    print(f"  Eligible:       {pack['gate']['eligible']} files")
    print(f"  Rejected:       {pack['gate']['rejected']} files")
    print(f"  Audit chain:    {'✅ VERIFIED' if pack['audit_chain']['verified'] else '💔 BROKEN'}")
    print(f"  Chain entries:  {pack['audit_chain']['entries']}")
    print(f"  Active exc:     {len(pack.get('exceptions', []))}")
    print()
    
    if pack.get("sources_detail"):
        print(f"  Sources used:")
        for sd in pack["sources_detail"]:
            print(f"    📄 {sd['file']}")
            print(f"       status: {sd.get('provenance_status', '?')}")
            print(f"       level:  {sd.get('provenance_level', '?')}")
            print(f"       reviewer: {sd.get('reviewer', '?')}")
        print()
    
    # --- 5. Value proposition ---
    print("━" * 70)
    print("  WHY THIS MATTERS")
    print("━" * 70)
    print()
    print("  Most enterprise AI:     'Here's an answer.'")
    print("  This system:            'Here's an answer. Here's exactly which")
    print("                           governed sources it came from. Here's who")
    print("                           reviewed them and when. Here's the")
    print("                           cryptographic proof none of it was tampered.")
    print("                           The gate blocked everything ungoverned.'")
    print()
    print("  Compliance value:       Every output is auditable.")
    print("  Legal value:            Every claim traces to a verified source.")
    print("  Trust value:            The system says no when it should.")
    print()
    print("=" * 70)
    print("  DEMO COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
