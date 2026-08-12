#!/usr/bin/env python3
"""
Åverd-Åverdön Exchange Backend — PGP-Verified Listing Server

Receives PGP-signed offers and requests, verifies them against the
submitter's public key, stores verified listings, and serves them.

No accounts. No passwords. Your PGP public key IS your identity.
"""

import json
import os
import time
import hashlib
import subprocess
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

LISTINGS_DIR = os.path.expanduser("~/tor-site/listings")
KEYRING_DIR = os.path.expanduser("~/tor-site/keyring")
ATTEST_DIR = os.path.expanduser("~/tor-site/attestations")
os.makedirs(LISTINGS_DIR, exist_ok=True)
os.makedirs(KEYRING_DIR, exist_ok=True)
os.makedirs(ATTEST_DIR, exist_ok=True)

# ── PGP Operations ───────────────────────────────────────────────────

def extract_fingerprint(pubkey_armor: str) -> str | None:
    """Extract the fingerprint from an armored PGP public key."""
    if isinstance(pubkey_armor, bytes):
        pubkey_input = pubkey_armor
    else:
        pubkey_input = pubkey_armor.encode()
    # Use --show-keys which works on stdin
    proc = subprocess.run(
        ["gpg", "--show-keys", "--with-colons"],
        input=pubkey_input,
        capture_output=True, timeout=10
    )
    for line in proc.stdout.decode().splitlines():
        if line.startswith("fpr:"):
            return line.split(":")[9]
    return None


def import_key(pubkey_armor: str, fingerprint: str) -> bool:
    """Import a public key into our temporary keyring."""
    keyring_path = os.path.join(KEYRING_DIR, f"{fingerprint}.gpg")
    if os.path.exists(keyring_path):
        return True
    pk_input = pubkey_armor if isinstance(pubkey_armor, bytes) else pubkey_armor.encode()
    proc = subprocess.run(
        ["gpg", "--no-default-keyring", "--keyring", keyring_path,
         "--import"],
        input=pk_input,
        capture_output=True, timeout=15
    )
    return proc.returncode == 0


def verify_signature(signed_content: str, fingerprint: str) -> bool:
    """Verify a clearsigned message against an imported public key."""
    keyring_path = os.path.join(KEYRING_DIR, f"{fingerprint}.gpg")
    sig_input = signed_content if isinstance(signed_content, bytes) else signed_content.encode()
    proc = subprocess.run(
        ["gpg", "--no-default-keyring", "--keyring", keyring_path,
         "--verify"],
        input=sig_input,
        capture_output=True, timeout=15
    )
    return proc.returncode == 0


def extract_signed_payload(signed_content: str) -> str | None:
    """Extract the message body from a clearsigned PGP message."""
    match = re.search(
        r'-----BEGIN PGP SIGNED MESSAGE-----.*?\n\n(.*?)-----BEGIN PGP SIGNATURE-----',
        signed_content, re.DOTALL
    )
    return match.group(1).strip() if match else None


# ── Listing Storage ──────────────────────────────────────────────────

def save_listing(listing_type: str, payload: dict, fingerprint: str):
    """Save a verified listing to disk."""
    ts = int(time.time())
    listing_id = hashlib.sha256(
        f"{fingerprint}:{ts}:{json.dumps(payload, sort_keys=True)}".encode()
    ).hexdigest()[:12]

    data = {
        "listing_id": listing_id,
        "type": listing_type,
        "category": payload.get("category", ""),
        "title": payload.get("title", ""),
        "body": payload.get("body", ""),
        "consent_terms": payload.get("consent_terms", []),
        "no_ask": payload.get("no_ask", []),
        "fingerprint": fingerprint,
        "created_at": ts,
        "expires_at": ts + int(payload.get("expires_days", 14)) * 86400,
        "status": "active"
    }

    path = os.path.join(LISTINGS_DIR, f"{listing_id}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    return listing_id


def get_active_listings() -> list:
    """Return all active, non-expired listings."""
    now = int(time.time())
    listings = []
    for fn in os.listdir(LISTINGS_DIR):
        if not fn.endswith(".json"):
            continue
        path = os.path.join(LISTINGS_DIR, fn)
        try:
            with open(path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            continue
        if data.get("status") != "active":
            continue
        if data.get("expires_at", 0) < now:
            data["status"] = "expired"
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            continue
        listings.append(data)
    listings.sort(key=lambda x: x["created_at"], reverse=True)
    return listings


def revoke_listing(listing_id: str, fingerprint: str, signed_revocation: str) -> bool:
    """Revoke a listing if signed by the original fingerprint."""
    path = os.path.join(LISTINGS_DIR, f"{listing_id}.json")
    if not os.path.exists(path):
        return False

    with open(path) as f:
        data = json.load(f)

    if data["fingerprint"] != fingerprint:
        return False

    if not verify_signature(signed_revocation, fingerprint):
        return False

    data["status"] = "revoked"
    data["revoked_at"] = int(time.time())
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return True


# ── HTTP Server ──────────────────────────────────────────────────────

class ExchangeHandler(BaseHTTPRequestHandler):

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

        if path == "/api/listings":
            listings = get_active_listings()
            self._send_json({"listings": listings})
            return

        if path.startswith("/api/listing/"):
            listing_id = path.split("/")[-1]
            lpath = os.path.join(LISTINGS_DIR, f"{listing_id}.json")
            if os.path.exists(lpath):
                with open(lpath) as f:
                    self._send_json(json.load(f))
            else:
                self._send_json({"error": "not found"}, 404)
            return

        if path.startswith("/api/attest/"):
            attest_id = path.split("/")[-1]
            apath = os.path.join(ATTEST_DIR, f"{attest_id}.json")
            if os.path.exists(apath):
                with open(apath) as f:
                    self._send_json(json.load(f))
            else:
                self._send_json({"error": "not found"}, 404)
            return

        if path == "/api/fingerprint":
            pubkey = self.headers.get("X-PGP-Public-Key", "")
            if not pubkey:
                self._send_json({"error": "no pubkey provided"}, 400)
                return
            fp = extract_fingerprint(pubkey)
            if fp:
                self._send_json({"fingerprint": fp})
            else:
                self._send_json({"error": "invalid key"}, 400)
            return

        self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._read_body()

        if path == "/api/submit":
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self._send_json({"error": "invalid JSON"}, 400)
                return

            pubkey = data.get("pubkey", "")
            signed = data.get("signed_content", "")
            listing_type = data.get("type", "offer")

            # Extract fingerprint and import key
            fp = extract_fingerprint(pubkey)
            if not fp:
                self._send_json({"error": "invalid public key"}, 400)
                return

            if not import_key(pubkey, fp):
                self._send_json({"error": "failed to import key"}, 500)
                return

            # Verify signature
            if not verify_signature(signed, fp):
                self._send_json({"error": "signature verification failed"}, 403)
                return

            # Extract payload
            payload_text = extract_signed_payload(signed)
            if not payload_text:
                self._send_json({"error": "could not extract signed payload"}, 400)
                return

            try:
                payload = json.loads(payload_text)
            except json.JSONDecodeError:
                self._send_json({"error": "signed payload is not valid JSON"}, 400)
                return

            # Validate required fields
            if not payload.get("title") or not payload.get("body"):
                self._send_json({"error": "title and body are required"}, 400)
                return

            # Save
            listing_id = save_listing(listing_type, payload, fp)
            self._send_json({
                "status": "submitted",
                "listing_id": listing_id,
                "fingerprint": fp,
                "expires_at": int(time.time()) + int(payload.get("expires_days", 14)) * 86400
            }, 201)
            return

        if path == "/api/revoke":
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self._send_json({"error": "invalid JSON"}, 400)
                return

            listing_id = data.get("listing_id", "")
            pubkey = data.get("pubkey", "")
            signed = data.get("signed_revocation", "")

            fp = extract_fingerprint(pubkey)
            if not fp:
                self._send_json({"error": "invalid public key"}, 400)
                return

            if revoke_listing(listing_id, fp, signed):
                self._send_json({"status": "revoked", "listing_id": listing_id})
            else:
                self._send_json({"error": "revocation failed"}, 403)
            return

        if path == "/api/attest":
            # Store a pre-execution attestation record
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self._send_json({"error": "invalid JSON"}, 400)
                return

            qhash = data.get("query_hash", "")
            if not qhash:
                self._send_json({"error": "query_hash required"}, 400)
                return

            attest_id = hashlib.sha256(
                f"{qhash}:{int(time.time())}".encode()
            ).hexdigest()[:12]

            data["attestation_id"] = attest_id
            data["received_at"] = int(time.time())

            path = os.path.join(ATTEST_DIR, f"{attest_id}.json")
            with open(path, "w") as f:
                json.dump(data, f, indent=2)

            self._send_json({"attestation_id": attest_id, "status": "recorded"}, 201)
            return

        self._send_json({"error": "not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-PGP-Public-Key")
        self.end_headers()

    def log_message(self, format, *args):
        pass  # silent — no IP logging


if __name__ == "__main__":
    port = 8081
    server = HTTPServer(("127.0.0.1", port), ExchangeHandler)
    print(f"Exchange backend listening on 127.0.0.1:{port}")
    print("Endpoints:")
    print("  POST /api/submit       — submit signed listing")
    print("  GET  /api/listings      — get active listings")
    print("  GET  /api/listing/:id   — get single listing")
    print("  POST /api/revoke        — revoke listing")
    print("  GET  /api/fingerprint   — extract fingerprint from key")
    print("  POST /api/attest        — store attestation record")
    print("  GET  /api/attest/:id    — get attestation record")
    server.serve_forever()
