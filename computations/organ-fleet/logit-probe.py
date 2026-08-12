#!/usr/bin/env python3
"""Logit Probe — TCP honeypot on 127.0.0.1:8910. Logs every knock."""
import socket
import json
import sys
import os
from datetime import datetime, timezone

HOST = '127.0.0.1'
PORT = 8910
LOG_PATH = os.path.join(os.path.expanduser("~"), "logit-probe.jsonl")
METTA_LEDGER = os.path.join(os.path.expanduser("~"), "metta-ledger.jsonl")

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind((HOST, PORT))
sock.listen(1)

event = {
    'event': 'probe_start',
    'probe': 'logit',
    'port': PORT,
    'host': HOST,
    'timestamp_utc': datetime.now(timezone.utc).isoformat()
}
with open(LOG_PATH, 'a') as f:
    f.write(json.dumps(event) + '\n')
print(f'Logit probe listening on {HOST}:{PORT}', file=sys.stderr, flush=True)

while True:
    try:
        conn, addr = sock.accept()
        event = {
            'event': 'knock',
            'probe': 'logit',
            'port': PORT,
            'src_addr': addr[0],
            'src_port': addr[1],
            'timestamp_utc': datetime.now(timezone.utc).isoformat()
        }
        with open(LOG_PATH, 'a') as f:
            f.write(json.dumps(event) + '\n')
        # Wire into Organ Fleet metta-ledger
        metta_event = {
            'event_type': 'probe_knock',
            'probe': 'logit',
            'port': PORT,
            'src_addr': addr[0],
            'src_port': addr[1],
            'timestamp_utc': event['timestamp_utc']
        }
        with open(METTA_LEDGER, 'a') as f:
            f.write(json.dumps(metta_event) + '\n')
        print(f'KNOCK: {addr[0]}:{addr[1]}', file=sys.stderr, flush=True)
        # Honeypot: accept but send nothing, then close — wastes attacker's time
        conn.close()
    except KeyboardInterrupt:
        break
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr, flush=True)

sock.close()
