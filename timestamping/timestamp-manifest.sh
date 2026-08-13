#!/usr/bin/env bash
# Timestamp a manifest of SHA-256 hashes covering the "seeds" corpus.
#
# One RFC 3161 timestamp on a single manifest proves every file listed in it
# (by exact content hash) existed at that moment — scalable prior-art proof
# without timestamping each file individually. Only the manifest's hash leaves
# the machine; file names and contents never do.
#
# Usage:
#   timestamp-manifest.sh                          # default out dir + seeds
#   timestamp-manifest.sh /some/out/dir            # custom output dir
#   timestamp-manifest.sh /some/out/dir path1 ...  # custom seed paths
#
# Outputs <out>/seeds-<UTC>.manifest and its .manifest.tsr timestamp token.
set -euo pipefail

TSA="http://timestamp.digicert.com"
CAFILE="/etc/ssl/certs/ca-certificates.crt"

OUT_DIR="${1:-$HOME/Documents/timestamps}"
shift || true
if [ "$#" -gt 0 ]; then
    SEEDS=("$@")
else
    SEEDS=("$HOME/Documents" "$HOME/projects")
fi

mkdir -p "$OUT_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
MANIFEST="$OUT_DIR/seeds-$STAMP.manifest"
SORTED="$(mktemp /tmp/manifest.XXXXXX)"
TMPQ="$(mktemp /tmp/tsq.XXXXXX)"
trap 'rm -f "$SORTED" "$TMPQ"' EXIT

# Build sorted manifest: absolute path -> sha256. Exclude prior artifacts and
# build junk so the manifest reflects work product, not caches/venvs.
find "${SEEDS[@]}" -type f \
    -not -path "$OUT_DIR/*" \
    -not -path '*/.git/*' \
    -not -path '*/__pycache__/*' \
    -not -path '*/node_modules/*' \
    -not -path '*/.venv/*' -not -path '*/venv/*' \
    -not -path '*/.mypy_cache/*' -not -path '*/.ruff_cache/*' \
    -not -name '*.tsr' -not -name '*.tsq' \
    -not -name '*.manifest' -not -name '*.sha256' -not -name '*.pyc' \
    -exec sha256sum {} + 2>/dev/null | sort -k2 > "$SORTED"

count=$(wc -l < "$SORTED")
[ "$count" -gt 0 ] || { echo "FAIL: no files found under SEEDS" >&2; exit 1; }

{
    echo "# Sentinel seeds manifest"
    echo "# generated: $STAMP UTC"
    echo "# files: $count"
    echo "# verify: verify-timestamp.sh $MANIFEST $MANIFEST.tsr"
    echo
    cat "$SORTED"
} > "$MANIFEST"

echo "Manifest: $MANIFEST ($count files)"

openssl ts -query -data "$MANIFEST" -no_nonce -sha256 -cert -out "$TMPQ"
http_code=$(curl -sS --max-time 30 -o "$MANIFEST.tsr" -w '%{http_code}' \
    -X POST -H "Content-Type: application/timestamp-query" \
    --data-binary @"$TMPQ" "$TSA")

if [ "$http_code" != "200" ]; then
    echo "FAIL: TSA returned HTTP $http_code" >&2
    rm -f "$MANIFEST.tsr"; exit 1
fi
[ -s "$MANIFEST.tsr" ] || { echo "FAIL: empty token" >&2; rm -f "$MANIFEST.tsr"; exit 1; }

if openssl ts -verify -data "$MANIFEST" -in "$MANIFEST.tsr" -CAfile "$CAFILE" >/dev/null 2>&1; then
    echo "OK: manifest timestamped + verified"
    openssl ts -reply -in "$MANIFEST.tsr" -text 2>/dev/null | grep -E "Time stamp|Serial number"
else
    echo "FAIL: manifest token verification failed" >&2
    rm -f "$MANIFEST.tsr"; exit 1
fi
