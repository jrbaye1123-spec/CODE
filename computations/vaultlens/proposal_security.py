"""Proposal security: integrity verification and cryptographic trust for VaultLens.

Provides:
- Proposal hashing for tamper detection
- Simple HMAC signing (no external deps needed)
- Integrity verification of approved_edges.jsonl
"""

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class SignedProposal:
    """A proposal with integrity hash for tamper detection."""
    proposal_id: str
    source_title: str
    target_title: str
    relation: str
    variant: str
    confidence: float
    evidence_span: str
    hash: str
    signature: str = ""


def compute_proposal_hash(proposal: dict) -> str:
    """Compute a deterministic hash of proposal content (excluding mutable fields)."""
    canonical = json.dumps({
        "source_title": proposal.get("source_title", ""),
        "target_title": proposal.get("target_title", proposal.get("target", "")),
        "relation": proposal.get("relation", ""),
        "variant": proposal.get("variant", ""),
        "evidence_span": proposal.get("evidence_span", ""),
        "proposal_id": proposal.get("proposal_id", ""),
    }, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def sign_proposal(proposal: dict, secret: str) -> str:
    """Sign a proposal with HMAC-SHA256 using a shared secret.

    The secret can be:
    - A passphrase stored in environment variable VAULTLENS_SECRET
    - A hardware key derived value
    - A YubiKey challenge-response
    """
    content_hash = compute_proposal_hash(proposal)
    sig = hmac.new(secret.encode(), content_hash.encode(), hashlib.sha256).hexdigest()[:16]
    return sig


def verify_proposal(proposal: dict, secret: str, expected_signature: str) -> bool:
    """Verify a proposal's signature matches."""
    computed = sign_proposal(proposal, secret)
    return hmac.compare_digest(computed, expected_signature)


def verify_jsonl_integrity(jsonl_path: str, secret: Optional[str] = None) -> dict:
    """Verify the integrity of an approved_edges.jsonl file.

    Returns:
        Dict with 'valid' (bool), 'total_edges' (int), 'tampered' (list of line numbers),
        'unsigned' (list of line numbers), 'errors' (list of error messages)
    """
    result = {
        "valid": True,
        "total_edges": 0,
        "tampered": [],
        "unsigned": [],
        "errors": [],
    }

    if not os.path.exists(jsonl_path):
        result["valid"] = False
        result["errors"].append(f"File not found: {jsonl_path}")
        return result

    with open(jsonl_path) as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            try:
                edge = json.loads(line)
            except json.JSONDecodeError as e:
                result["valid"] = False
                result["errors"].append(f"Line {i}: invalid JSON ({e})")
                continue

            result["total_edges"] += 1

            # Check required fields
            required = ["source_title", "target", "relation", "variant"]
            missing = [f for f in required if f not in edge]
            if missing:
                result["valid"] = False
                result["errors"].append(f"Line {i}: missing fields {missing}")

            # If signed, verify signature
            stored_sig = edge.get("signature", "")
            if stored_sig and secret:
                if not verify_proposal(edge, secret, stored_sig):
                    result["tampered"].append(i)
                    result["valid"] = False
            elif not stored_sig:
                result["unsigned"].append(i)

    return result


def get_secret() -> Optional[str]:
    """Get the signing secret from environment or config."""
    return os.environ.get("VAULTLENS_SECRET") or os.environ.get("VAULTLENS_SIGNING_KEY")
