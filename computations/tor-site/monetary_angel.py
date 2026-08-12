#!/usr/bin/env python3
"""
Monetary Angel #3 — Polyvalent treasury management.
Accepts signed transactions, stores in ledger, answers queries.
Uses our existing BaseHTTPRequestHandler pattern. No Flask needed.
"""

import json
import os
import hashlib
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

LEDGER_PATH = os.path.expanduser("~/tor-site/monetary_ledger.json")
BUDGETS_PATH = os.path.expanduser("~/tor-site/proposal_budgets.json")
ANGEL_PORT = int(os.getenv("MONETARY_PORT", "8085"))
GPG_KEY_ID = os.getenv("MONETARY_GPG_KEY_ID", None)

def load_json(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def sign_message(message: str) -> str:
    if not GPG_KEY_ID:
        return f"-----BEGIN PGP SIGNED MESSAGE-----\n\n{message}\n-----BEGIN PGP SIGNATURE-----\nUNSIGNED\n-----END PGP SIGNATURE-----"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(message)
        tf = f.name
    try:
        subprocess.run(["gpg", "--clearsign", "--batch", "--yes", "--default-key", GPG_KEY_ID, tf],
                       check=True, capture_output=True, timeout=10)
        with open(tf + ".asc") as sf:
            content = sf.read()
        os.unlink(tf + ".asc")
        return content
    finally:
        os.unlink(tf)


class MonetaryHandler(BaseHTTPRequestHandler):

    def _send(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _read(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            self._send({"status": "ready", "angel": "monetary-03", "ledger": LEDGER_PATH})
        elif path == "/v1/balance":
            ledger = load_json(LEDGER_PATH, {"balances": {}})
            self._send({"balances": ledger.get("balances", {})})
        else:
            self._send({"error": "not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        data = self._read()

        if path == "/v1/incoming":
            amount = data.get("amount")
            currency = data.get("currency", "USD")
            source = data.get("source", "unknown")

            if not amount or not source:
                self._send({"error": "amount and source required"}, 400)
                return

            ledger = load_json(LEDGER_PATH, {"transactions": [], "balances": {}})
            ts = datetime.now(timezone.utc).isoformat()
            tx_id = hashlib.sha256(f"{source}{amount}{ts}".encode()).hexdigest()[:16]

            tx = {
                "id": tx_id, "type": "incoming", "amount": float(amount),
                "currency": currency, "source": source,
                "timestamp": ts, "proposal_id": data.get("proposal_id")
            }
            ledger["transactions"].append(tx)

            key = f"{source}_{currency}"
            ledger["balances"][key] = ledger["balances"].get(key, 0) + float(amount)
            save_json(LEDGER_PATH, ledger)

            receipt = sign_message(
                f"RECEIPT\nTX: {tx_id}\nAmount: {amount} {currency}\nSource: {source}\nTime: {ts}"
            )
            self._send({
                "status": "recorded", "tx_id": tx_id, "receipt": receipt,
                "new_balance": ledger["balances"][key]
            }, 201)

        elif path == "/v1/proposal_fund":
            pid = data.get("proposal_id")
            allocated = data.get("allocated")
            if not pid or not allocated:
                self._send({"error": "proposal_id and allocated required"}, 400)
                return

            budgets = load_json(BUDGETS_PATH, {})
            budgets[pid] = {
                "allocated": float(allocated),
                "currency": data.get("currency", "USD"),
                "spent": budgets.get(pid, {}).get("spent", 0),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            save_json(BUDGETS_PATH, budgets)
            self._send({"status": "funded", "proposal_id": pid, "allocated": allocated})

        elif path == "/v1/query":
            ledger = load_json(LEDGER_PATH, {"transactions": [], "balances": {}})
            txs = ledger.get("transactions", [])
            total_in = sum(t["amount"] for t in txs if t["type"] == "incoming")
            total_out = sum(t["amount"] for t in txs if t["type"] == "outgoing")
            self._send({
                "variant_causal": {"total_in": total_in, "total_out": total_out},
                "variant_temporal": {"latest": txs[-1] if txs else None, "count": len(txs)},
                "variant_evidential": {"transactions": txs[-10:]},
                "variant_provenance": {"sources": list(set(t["source"] for t in txs))}
            })

        else:
            self._send({"error": "not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    print(f"Monetary Angel #3 on 127.0.0.1:{ANGEL_PORT}")
    print("  POST /v1/incoming       — record payment")
    print("  POST /v1/proposal_fund  — allocate budget")
    print("  GET  /v1/balance        — current balances")
    print("  POST /v1/query          — polyvalent ledger query")
    server = HTTPServer(("127.0.0.1", ANGEL_PORT), MonetaryHandler)
    server.serve_forever()
