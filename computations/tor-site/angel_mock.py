#!/usr/bin/env python3
"""
Angel Mock — The first living Angel in the Myosu network.
Returns canned but PGP-signed responses for the Router to compile.

This is Angel #1. Deploy more by changing the data and key.
"""

import json
import subprocess
import tempfile
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

ANGEL_PORT = int(os.getenv("ANGEL_PORT", "8083"))
ANGEL_KEY_ID = os.getenv("ANGEL_KEY_ID", None)

# ── Known responses by query tag ─────────────────────────────────────
KNOWLEDGE_BASE = {
    "oncology": {
        "result": {"survival_hr": 0.67, "ci_95": [0.52, 0.86], "p_value": 0.003},
        "source": "TRIAL-XX-2024 (N=1,247)",
        "methodology": "Cox proportional hazards, ITT population",
        "disclaimer": "This is a mock response for demonstration."
    },
    "cardiology": {
        "result": {"mace_reduction": "18%", "nnt": 34, "follow_up_months": 24},
        "source": "HEART-META-2025 (pooled analysis)",
        "methodology": "Meta-analysis of 12 RCTs",
        "disclaimer": "This is a mock response for demonstration."
    },
    "rwe": {
        "result": {"real_world_adherence": "72%", "discontinuation_rate": "14%"},
        "source": "CLAIMS-DB-2025-Q2",
        "methodology": "Retrospective claims analysis",
        "disclaimer": "This is a mock response for demonstration."
    },
    "general": {
        "result": {"message": "No specific data available for this query domain."},
        "source": "ANGEL-01-KB",
        "methodology": "Keyword matching",
        "disclaimer": "This is a mock response. Angel #1 is a demonstration endpoint."
    }
}


def sign_response(data: dict) -> str:
    """Sign the response with this Angel's PGP key."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f, sort_keys=True, separators=(",", ":"))
        tf = f.name
    try:
        cmd = ["gpg", "--clearsign", "--batch", "--yes"]
        if ANGEL_KEY_ID:
            cmd.extend(["--default-key", ANGEL_KEY_ID])
        cmd.append(tf)
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        signed_file = tf + ".asc"
        with open(signed_file) as sf:
            result = sf.read()
        os.unlink(signed_file)
        return result
    finally:
        os.unlink(tf)


def classify(text: str) -> list[str]:
    tags = []
    t = text.lower()
    for tag, keywords in [
        ("oncology", ["cancer", "tumor", "survival", "oncology"]),
        ("cardiology", ["heart", "cardiac", "stroke", "mace"]),
        ("rwe", ["real world", "observational", "claims", "registry"]),
    ]:
        if any(k in t for k in keywords):
            tags.append(tag)
    return tags if tags else ["general"]


class AngelHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in ("/v1/infer", "/api/infer"):
            self._send({"error": "not found"}, 404)
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode() if length else ""
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send({"error": "invalid JSON"}, 400)
            return

        signed_query = data.get("signed_query", "")
        if not signed_query:
            self._send({"error": "signed_query required"}, 400)
            return

        # Extract payload text (simple: grab between headers)
        import re
        m = re.search(
            r'-----BEGIN PGP SIGNED MESSAGE-----.*?\n\n(.*?)-----BEGIN PGP SIGNATURE-----',
            signed_query, re.DOTALL
        )
        query_text = m.group(1).strip() if m else signed_query

        # Classify and fetch response
        tags = classify(query_text)
        response_data = None
        for tag in tags:
            if tag in KNOWLEDGE_BASE:
                response_data = dict(KNOWLEDGE_BASE[tag])
                break
        if not response_data:
            response_data = dict(KNOWLEDGE_BASE["general"])

        response_data["angel_id"] = "angel-01"
        response_data["query_tags"] = tags
        response_data["timestamp"] = __import__('datetime').datetime.now().isoformat()

        # Sign
        try:
            signed = sign_response(response_data)
        except Exception:
            signed = json.dumps(response_data)

        self._send({
            "angel": "angel-01",
            "status": "ok",
            "signed_response": signed,
            "response_data": response_data
        })

    def do_GET(self):
        self._send({"angel": "angel-01", "status": "ready", "endpoint": "POST /v1/infer"})

    def _send(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    print(f"Angel #1 listening on 127.0.0.1:{ANGEL_PORT}")
    print("  POST /v1/infer  — submit signed query")
    print("  GET  /          — status")
    server = HTTPServer(("127.0.0.1", ANGEL_PORT), AngelHandler)
    server.serve_forever()
