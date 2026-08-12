#!/usr/bin/env python3
"""LogDet Probe — TCP honeypot on 127.0.0.1:8911. Logs every knock."""
import socket
import json
import sys
import os
from datetime import datetime, timezone

HOST = '127.0.0.1'
PORT = 8911
LOG_PATH = os.path.join(os.path.expanduser("~"), "logdet-probe.jsonl")
METTA_LEDGER = os.path.join(os.path.expanduser("~"), "metta-ledger.jsonl")

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind((HOST, PORT))
sock.listen(1)

event = {
    'event': 'probe_start',
    'probe': 'logdet',
    'port': PORT,
    'host': HOST,
    'timestamp_utc': datetime.now(timezone.utc).isoformat()
}
with open(LOG_PATH, 'a') as f:
    f.write(json.dumps(event) + '\n')
print(f'LogDet probe listening on {HOST}:{PORT}', file=sys.stderr, flush=True)

while True:
    try:
        conn, addr = sock.accept()
        event = {
            'event': 'knock',
            'probe': 'logdet',
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
            'probe': 'logdet',
            'port': PORT,
            'src_addr': addr[0],
            'src_port': addr[1],
            'timestamp_utc': event['timestamp_utc']
        }
        with open(METTA_LEDGER, 'a') as f:
            f.write(json.dumps(metta_event) + '\n')
        print(f'KNOCK: {addr[0]}:{addr[1]}', file=sys.stderr, flush=True)
        conn.close()
    except KeyboardInterrupt:
        break
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr, flush=True)

sock.close()
