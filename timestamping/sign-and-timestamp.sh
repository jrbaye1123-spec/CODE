#!/usr/bin/env bash
# Sign a file (authorship) then timestamp the signature (existence-before-time).
# Completes: integrity (sha256) -> signature (gpg) -> trust -> timestamp (RFC 3161).
#
# Usage: sign-and-timestamp.sh <file>
# Produces <file>.asc (detached signature) and <file>.asc.tsr (timestamp token).
#
# Env: GPG_KEY (default jrbaye1123@gmail.com); GPG_PASSPHRASE if your key has one.
set -euo pipefail

FILE="$1"
[ -n "$FILE" ] && [ -f "$FILE" ] || { echo "Usage: $0 <file>" >&2; exit 1; }

KEY="${GPG_KEY:-jrbaye1123@gmail.com}"

# 1. Detached, armored signature (proves authorship).
gpg --batch --yes --pinentry-mode loopback --local-user "$KEY" \
    --detach-sign --armor "$FILE"
echo "signed -> $FILE.asc"

# 2. Timestamp the signature (proves it existed before a given time).
"$(dirname "$0")/timestamp-file.sh" "$FILE.asc"
