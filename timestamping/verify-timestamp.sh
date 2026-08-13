#!/usr/bin/env bash
# Verify a file against an existing RFC 3161 timestamp token.
#
# Usage: verify-timestamp.sh <file> <file.tsr>
set -euo pipefail

CAFILE="/etc/ssl/certs/ca-certificates.crt"

FILE="$1"
TSR="$2"

if [ -z "$FILE" ] || [ -z "$TSR" ] || [ ! -f "$FILE" ] || [ ! -f "$TSR" ]; then
    echo "Usage: $0 <file> <file.tsr>" >&2
    exit 1
fi

if openssl ts -verify -data "$FILE" -in "$TSR" -CAfile "$CAFILE"; then
    echo "PASSED: file matches token"
else
    echo "FAILED: file does not match token (or token invalid)" >&2
    exit 1
fi
