#!/usr/bin/env python3
"""
Exchange Attestation Writer — Creates immutable, cryptographically signed
pre-execution contracts before any Router dispatches a query.

Every query becomes a verifiable legal event:
  user_fingerprint + selected_angels + policy_decisions + query_hash
  — all signed by the Router's PGP key and anchored to the Exchange API.
"""

import json
import logging
import hashlib
import subprocess
import tempfile
import os
from datetime import datetime, timezone
from typing import Dict, List, Any
from dataclasses import dataclass, asdict
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ── Configuration ────────────────────────────────────────────────────
EXCHANGE_API_BASE = os.getenv("EXCHANGE_API_URL", "http://127.0.0.1:8081/api")
ATTESTATIONS_ENDPOINT = f"{EXCHANGE_API_BASE}/attest"
ROUTER_PGP_KEY_ID = os.getenv("ROUTER_PGP_KEY_ID", None)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("attestation_writer")

# ── Data Models ──────────────────────────────────────────────────────

@dataclass
class AttestationRecord:
    query_hash: str
    user_fingerprint: str
    selected_angels: List[str]
    rejected_angels: List[str]
    policy_decisions: Dict[str, Any]
    routing_timestamp: str
    query_classification: List[str]
    router_fingerprint: str
    attestation_signature: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)

    def compute_payload_hash(self) -> str:
        data = self.to_dict()
        data.pop("attestation_signature", None)
        return hashlib.sha256(
            json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

# ── GPG Signer ───────────────────────────────────────────────────────

class GPGSigner:
    @staticmethod
    def clearsign_message(message: str, key_id: str = None) -> str:
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
                f.write(message)
                temp_file = f.name

            cmd = ["gpg", "--clearsign", "--batch", "--yes"]
            if key_id:
                cmd.extend(["--default-key", key_id])
            cmd.append(temp_file)

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            os.unlink(temp_file)

            if result.returncode != 0:
                raise RuntimeError(f"GPG clearsign failed: {result.stderr.strip()}")

            signed_file = temp_file + ".asc"
            with open(signed_file) as sf:
                signed_content = sf.read()
            os.unlink(signed_file)
            return signed_content

        except subprocess.TimeoutExpired:
            raise RuntimeError("GPG clearsign timed out")

    @staticmethod
    def get_fingerprint(key_id: str = None) -> str:
        cmd = ["gpg", "--fingerprint", "--with-colons", "--batch"]
        if key_id:
            cmd.append(key_id)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            raise RuntimeError(f"Fingerprint failed: {result.stderr}")
        for line in result.stdout.splitlines():
            if line.startswith("fpr:"):
                parts = line.split(":")
                if len(parts) >= 10:
                    return parts[9].upper()
        raise RuntimeError("Fingerprint not found")

# ── The Writer ───────────────────────────────────────────────────────

class AttestationWriter:
    def __init__(self):
        self._session = requests.Session()
        retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
        self._session.mount("http://", HTTPAdapter(max_retries=retries))
        self._router_key_id = ROUTER_PGP_KEY_ID or None
        try:
            self._router_fingerprint = GPGSigner.get_fingerprint(ROUTER_PGP_KEY_ID)
        except Exception:
            self._router_fingerprint = ""
        logger.info(f"AttestationWriter ready. Router FP: {self._router_fingerprint}")

    def create_attestation(
        self,
        user_fingerprint: str,
        query_hash: str,
        selected_angels: List[str],
        rejected_angels: List[str],
        policy_decisions: Dict[str, Any],
        query_classification: List[str]
    ) -> AttestationRecord:
        record = AttestationRecord(
            query_hash=query_hash,
            user_fingerprint=user_fingerprint.replace(" ", "").upper(),
            selected_angels=selected_angels,
            rejected_angels=rejected_angels,
            policy_decisions=policy_decisions,
            routing_timestamp=datetime.now(timezone.utc).isoformat(),
            query_classification=query_classification,
            router_fingerprint=self._router_fingerprint,
            attestation_signature=""
        )

        data_for_signing = record.to_dict()
        data_for_signing.pop("attestation_signature", None)
        json_to_sign = json.dumps(data_for_signing, sort_keys=True, separators=(",", ":"))

        clearsigned = GPGSigner.clearsign_message(json_to_sign, self._router_key_id)
        record.attestation_signature = clearsigned

        self._post_to_exchange(record)
        return record

    def _post_to_exchange(self, record: AttestationRecord):
        payload = record.to_dict()
        resp = self._session.post(
            ATTESTATIONS_ENDPOINT,
            json=payload,
            timeout=10,
            headers={"Content-Type": "application/json"}
        )
        resp.raise_for_status()
        result = resp.json()
        aid = result.get("attestation_id") if isinstance(result, dict) else None
        if aid:
            logger.info(f"Attestation recorded: {aid}")
        return result

attestation_writer = AttestationWriter()

def write_pre_execution_attestation(
    user_fingerprint: str,
    signed_request_text: str,
    selected_angel_ids: List[str],
    rejected_angel_list: List[str],
    policy_eval_result: Dict[str, Any],
    query_tags: List[str]
) -> AttestationRecord:
    query_hash = hashlib.sha256(signed_request_text.encode()).hexdigest()
    record = attestation_writer.create_attestation(
        user_fingerprint=user_fingerprint,
        query_hash=query_hash,
        selected_angels=selected_angel_ids,
        rejected_angels=rejected_angel_list,
        policy_decisions=policy_eval_result,
        query_classification=query_tags
    )
    return record

if __name__ == "__main__":
    record = write_pre_execution_attestation(
        user_fingerprint="3B6A7F8E9D0C1A2B3C4D5E6F7A8B9C0D1E2F3A4B",
        signed_request_text="-----BEGIN PGP SIGNED MESSAGE-----\n...\n",
        selected_angel_ids=["lst_abc123"],
        rejected_angel_list=["lst_old789"],
        policy_eval_result={"allow": True},
        query_tags=["oncology", "survival"]
    )
    print(json.dumps(record.to_dict(), indent=2, default=str))
