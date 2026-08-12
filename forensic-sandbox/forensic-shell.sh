#!/bin/bash
# Forensic sandbox wrapper — locks down the RECOVERY drive for safe analysis.
# Usage: forensic-shell.sh [command...]
#   No args: drops into an interactive shell inside the sandbox.
#   With args: runs that command inside the sandbox and exits.

set -euo pipefail

FORENSIC_HOME="/home/nakamichi/forensic-sandbox"
EVIDENCE="/media/nakamichi/RECOVERY"
WORKDIR="${FORENSIC_HOME}/workspace"

mkdir -p "$WORKDIR"

exec bwrap \
    --ro-bind / / \
    --ro-bind "$EVIDENCE" "$EVIDENCE" \
    --bind "$WORKDIR" "$WORKDIR" \
    --bind "$FORENSIC_HOME" "$FORENSIC_HOME" \
    --dev /dev \
    --proc /proc \
    --tmpfs /tmp \
    --unshare-all \
    --unshare-net \
    --unshare-pid \
    --unshare-ipc \
    --unshare-uts \
    --hostname forensic-box \
    --die-with-parent \
    --clearenv \
    --setenv HOME "$FORENSIC_HOME" \
    --setenv PATH "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    --setenv TERM "${TERM:-xterm-256color}" \
    --setenv LANG "${LANG:-en_US.UTF-8}" \
    --setenv SHELL /bin/bash \
    --setenv FORENSIC_MODE 1 \
    --chdir "$FORENSIC_HOME" \
    /bin/bash "${@:--l}"
