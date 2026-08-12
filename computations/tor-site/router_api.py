#!/usr/bin/env python3
"""
Router API — The cryptographic switchboard.
Listens on port 8082. Verifies signed queries, routes to verified Angels,
writes pre-execution attestations, compiles responses, and returns a
PGP-signed final answer envelope.

The Router does not store. It listens, routes, witnesses, and returns.
It is a pure function, not a database.
"""

import json
import subprocess
import tempfile
import os
import time
import hashlib
import threading
import concurrent.futures
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# ── Import our middleware ────────────────────────────────────────────
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from angel_registry import registry as angel_registry
from attestation_writer import write_pre_execution_attestation

# ── Configuration ────────────────────────────────────────────────────
ROUTER_PORT = int(os.getenv("ROUTER_PORT", "8082"))
ROUTER_KEY_ID = os.getenv("ROUTER_KEY_ID", None)
ANGEL_TIMEOUT = int(os.getenv("ANGEL_TIMEOUT", "15"))
ANGEL_RETRIES = int(os.getenv("ANGEL_RETRIES", "1"))

# ── GPG Utilities ────────────────────────────────────────────────────

def extract_fingerprint_from_signed(signed_text: str) -> str | None:
    """Extract the signer's fingerprint from a clearsigned message."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".asc", delete=False) as f:
        f.write(signed_text)
        tf = f.name
    try:
        proc = subprocess.run(
            ["gpg", "--verify", "--status-fd", "1", tf],
            capture_output=True, text=True, timeout=10
        )
        for line in proc.stdout.splitlines():
            if line.startswith("[GNUPG:] VALIDSIG"):
                parts = line.split()
                if len(parts) >= 2:
                    return parts[2].upper()
        return None
    finally:
        os.unlink(tf)


def verify_request_signature(signed_text: str) -> tuple[bool, str | None, str]:
    """Verify a signed request. Returns (valid, fingerprint, error)."""
    fp = extract_fingerprint_from_signed(signed_text)
    if not fp:
        return False, None, "Could not extract fingerprint"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".asc", delete=False) as f:
        f.write(signed_text)
        tf = f.name
    try:
        proc = subprocess.run(
            ["gpg", "--verify", tf],
            capture_output=True, text=True, timeout=10
        )
        if proc.returncode == 0:
            return True, fp, ""
        return False, fp, f"Signature invalid: {proc.stderr.strip()[:200]}"
    finally:
        os.unlink(tf)


def extract_payload(signed_text: str) -> str:
    """Extract the message body from a clearsigned PGP message."""
    import re
    m = re.search(
        r'-----BEGIN PGP SIGNED MESSAGE-----.*?\n\n(.*?)-----BEGIN PGP SIGNATURE-----',
        signed_text, re.DOTALL
    )
    return m.group(1).strip() if m else ""


def sign_envelope(data: dict) -> str:
    """Sign the final answer with the Router's PGP key."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f, sort_keys=True, separators=(",", ":"))
        tf = f.name
    try:
        cmd = ["gpg", "--clearsign", "--batch", "--yes"]
        if ROUTER_KEY_ID:
            cmd.extend(["--default-key", ROUTER_KEY_ID])
        cmd.append(tf)
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        signed_file = tf + ".asc"
        with open(signed_file) as sf:
            result = sf.read()
        os.unlink(signed_file)
        return result
    finally:
        os.unlink(tf)


# ── Query Classifier (lightweight) ───────────────────────────────────

def classify_query(text: str) -> list[str]:
    """Extract keywords/tags from the query text."""
    tags = []
    text_lower = text.lower()
    keywords = {
        "oncology": ["cancer", "tumor", "survival", "oncology", "malignancy"],
        "cardiology": ["heart", "cardiac", "cardiovascular", "stroke"],
        "neurology": ["brain", "neuro", "alzheimer", "dementia", "cognitive"],
        "rwe": ["real world", "observational", "rwe", "registry"],
        "clinical_trial": ["trial", "rct", "randomized", "phase"],
        "epidemiology": ["incidence", "prevalence", "epidemiology", "outbreak"],
    }
    for tag, terms in keywords.items():
        if any(t in text_lower for t in terms):
            tags.append(tag)
    return tags if tags else ["general"]


# ── OPA-Style Policy Engine ──────────────────────────────────────────

def policy_allows(angel, query_tags: list[str], jurisdiction: str = "GLOBAL") -> bool:
    """Simple policy filter. Extensible to full OPA."""
    cap = angel.capability
    # Domain match
    if not any(t in cap.domains for t in query_tags):
        return False
    # Jurisdiction check (placeholder)
    if jurisdiction == "EU" and cap.jurisdiction not in ("EU", "GLOBAL"):
        return False
    return True


# ── Angel Dispatcher ─────────────────────────────────────────────────

def dispatch_to_angel(angel, signed_query: str) -> dict | None:
    """Call an angel endpoint with the signed query. Returns response or None."""
    import requests
    for attempt in range(ANGEL_RETRIES + 1):
        try:
            resp = requests.post(
                angel.capability.endpoint,
                json={"signed_query": signed_query},
                timeout=ANGEL_TIMEOUT,
                headers={"Content-Type": "application/json"}
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            if attempt == ANGEL_RETRIES:
                return None
            time.sleep(1)
    return None


# ── Compiler ─────────────────────────────────────────────────────────

def compile_responses(responses: list[dict], query_tags: list[str]) -> dict:
    """Stitch angel responses into a final answer with contradiction disclosure."""
    fragments = []
    contradictions = []
    sources = set()

    for resp in responses:
        if not resp:
            continue
        fragments.append(resp.get("result", resp))
        src = resp.get("source", "unknown")
        sources.add(src)

    # Detect contradictions (simple: check for conflicting values)
    if len(responses) > 1:
        values = []
        for resp in responses:
            result = resp.get("result", {})
            if isinstance(result, dict):
                for k, v in result.items():
                    values.append((k, v))
        seen = {}
        for k, v in values:
            if k in seen and seen[k] != v:
                contradictions.append({
                    "field": k,
                    "values": [seen[k], v],
                    "resolution": "reported, not adjudicated"
                })
            seen[k] = v

    return {
        "compiled_result": {
            "fragments": fragments,
            "source_count": len(sources),
            "sources": sorted(list(sources))
        },
        "contradiction_disclosure": contradictions if contradictions else "none detected",
        "query_classification": query_tags,
        "angels_queried": len(responses),
        "angels_responded": len([r for r in responses if r])
    }


# ── HTTP Handler ─────────────────────────────────────────────────────

class RouterHandler(BaseHTTPRequestHandler):

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length).decode() if length else ""

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/route":
            self._send_json({
                "status": "ready",
                "endpoint": "POST /api/route",
                "usage": "Send a clearsigned PGP query in {'signed_query': '...'}",
                "angels_cached": angel_registry.get_stats().get("total_verified", 0)
            })
            return
        if path == "/api/stats":
            self._send_json(angel_registry.get_stats())
            return
        self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/api/route":
            self._send_json({"error": "not found"}, 404)
            return

        body = self._read_body()
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_json({"error": "invalid JSON"}, 400)
            return

        signed_query = data.get("signed_query", "")
        if not signed_query:
            self._send_json({"error": "signed_query required"}, 400)
            return

        # 1. Verify user signature
        valid, user_fp, err = verify_request_signature(signed_query)
        if not valid:
            self._send_json({"error": f"Signature verification failed: {err}"}, 403)
            return

        # 2. Extract query payload
        query_text = extract_payload(signed_query)

        # 3. Classify query
        tags = classify_query(query_text)

        # 4. Get verified angels from registry
        all_angels = angel_registry.get_all_angels()
        selected = []
        rejected = []

        for angel in all_angels:
            if policy_allows(angel, tags):
                selected.append(angel)
            else:
                rejected.append(angel.listing_id)

        if not selected:
            self._send_json({
                "error": "no matching angels available",
                "query_tags": tags,
                "angels_available": len(all_angels),
                "angels_rejected": len(rejected)
            }, 503)
            return

        # 5. Write pre-execution attestation
        try:
            attestation = write_pre_execution_attestation(
                user_fingerprint=user_fp,
                signed_request_text=signed_query,
                selected_angel_ids=[a.listing_id for a in selected],
                rejected_angel_list=rejected,
                policy_eval_result={
                    "allow": True,
                    "query_tags": tags,
                    "angels_total": len(all_angels),
                    "angels_selected": len(selected)
                },
                query_tags=tags
            )
        except Exception as e:
            self._send_json({"error": f"Attestation failed: {e}"}, 500)
            return

        # 6. Dispatch to selected angels in parallel
        responses = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(selected)) as executor:
            futures = {
                executor.submit(dispatch_to_angel, angel, signed_query): angel
                for angel in selected
            }
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result(timeout=ANGEL_TIMEOUT + 2)
                    responses.append(result)
                except Exception:
                    responses.append(None)

        # 7. Compile
        compiled = compile_responses([r for r in responses if r], tags)

        # 8. Build and sign final envelope
        envelope = {
            "router_response": compiled,
            "metadata": {
                "user_fingerprint": user_fp,
                "query_hash": hashlib.sha256(signed_query.encode()).hexdigest(),
                "attestation_id": attestation.attestation_id if hasattr(attestation, "attestation_id") else None,
                "angels_selected": [a.listing_id for a in selected],
                "angels_rejected": rejected,
                "angels_responded": len([r for r in responses if r]),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "router": "averdaverdon-router/v0.6"
            }
        }

        try:
            signed_envelope = sign_envelope(envelope)
        except Exception as e:
            # Return unsigned if signing fails
            signed_envelope = json.dumps(envelope)

        self._send_json({
            "status": "complete",
            "signed_envelope": signed_envelope,
            "attestation_id": attestation.attestation_id if hasattr(attestation, "attestation_id") else None,
            "angels_queried": len(selected),
            "angels_responded": len([r for r in responses if r]),
            "summary": compiled["compiled_result"]["fragments"][:3] if compiled["compiled_result"]["fragments"] else []
        })

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        pass  # silent


if __name__ == "__main__":
    # Give registry time to populate
    print(f"Router API starting on 127.0.0.1:{ROUTER_PORT}")
    print("Waiting for angel registry to populate...")
    time.sleep(3)
    stats = angel_registry.get_stats()
    print(f"Angels cached: {stats['total_verified']}")
    print(f"Endpoints: POST /api/route, GET /api/stats")

    server = HTTPServer(("127.0.0.1", ROUTER_PORT), RouterHandler)
    server.serve_forever()
