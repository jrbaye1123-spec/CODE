#!/usr/bin/env bash
# Timestamp a single file via DigiCert RFC 3161 (proof of existence).
#
# Usage: timestamp-file.sh <file>
# Produces <file>.tsr (the timestamp token) next to the file, then verifies it.
# Only the file's SHA-256 imprint leaves the machine — never the file itself.
set -euo pipefail

TSA="http://timestamp.digicert.com"
CAFILE="/etc/ssl/certs/ca-certificates.crt"

FILE="$1"
if [ -z "$FILE" ] || [ ! -f "$FILE" ]; then
    echo "Usage: $0 <file>" >&2
    exit 1
fi

TSR="$FILE.tsr"
TMPQ="$(mktemp /tmp/tsq.XXXXXX)"
trap 'rm -f "$TMPQ"' EXIT

echo "Timestamping: $FILE"

# 1. Build the timestamp query (hash computed locally).
openssl ts -query -data "$FILE" -no_nonce -sha256 -cert -out "$TMPQ"

# 2. Request the token; fail loudly on any transport error.
http_code=$(curl -sS --max-time 30 -o "$TSR" -w '%{http_code}' \
    -X POST -H "Content-Type: application/timestamp-query" \
    --data-binary @"$TMPQ" "$TSA")

if [ "$http_code" != "200" ]; then
    echo "FAIL: TSA returned HTTP $http_code" >&2
    rm -f "$TSR"; exit 1
fi
[ -s "$TSR" ] || { echo "FAIL: empty token" >&2; rm -f "$TSR"; exit 1; }

# 3. Confirm the token was actually granted.
if ! openssl ts -reply -in "$TSR" -text 2>/dev/null | grep -q "Status: Granted"; then
    echo "FAIL: timestamp not granted" >&2
    rm -f "$TSR"; exit 1
fi

# 4. Cryptographically verify the token against the file + TSA cert chain.
if openssl ts -verify -data "$FILE" -in "$TSR" -CAfile "$CAFILE" >/dev/null 2>&1; then
    echo "OK: token granted and verified -> $TSR"
    openssl ts -reply -in "$TSR" -text 2>/dev/null | grep -E "Time stamp|Serial number"
else
    echo "FAIL: token failed cryptographic verification" >&2
    rm -f "$TSR"; exit 1
fi
