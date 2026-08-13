#!/usr/bin/env bash
# Sentinel — deploy daily rootkit scan (run ONCE as root).
#
#   sudo bash /home/nakamichi/projects/sentinel/deploy_daily_scan_root.sh
#
# Step 1: install daily_scan.sh as a ROOT-OWNED script. Root cron must never
#         run a user-writable script (that is a local privilege-escalation path).
# Step 2: schedule it in ROOT's crontab under flock, logging to /var/log/sentinel/.
# Step 3: baseline rkhunter (--propupd) — only after you have reviewed state.
#
# Idempotent: safe to re-run. The trap (ipset/iptables) infrastructure is NOT
# deployed here — that is a later, separately-reviewed phase behind its own
# root-owned /usr/local/sbin/sentinel-trap helper.
set -euo pipefail

SRC="/home/nakamichi/projects/sentinel/daily_scan.sh"
DST="/usr/local/sbin/sentinel-daily-scan"
LOG_DIR="/var/log/sentinel"
LOCK="/run/lock/sentinel-daily-scan.lock"
CRON_LINE="0 2 * * * /usr/bin/flock -n $LOCK $DST >> $LOG_DIR/daily_scan.log 2>&1"

log() { echo "[$(date '+%F %T')] $*"; }
die() { echo "FATAL: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "must run as root: sudo bash $0"

# --- log dir (root-owned, mode 700) ---
mkdir -p "$LOG_DIR"
chown root:root "$LOG_DIR"
chmod 700 "$LOG_DIR"
log "log dir ready: $LOG_DIR"

# --- install root-owned copy ---
install -o root -g root -m 0755 "$SRC" "$DST"
log "installed root-owned script: $DST"

# --- schedule under flock (idempotent) ---
if crontab -l 2>/dev/null | grep -Fq "$DST"; then
    log "root crontab: daily scan already scheduled"
else
    ( crontab -l 2>/dev/null; echo "$CRON_LINE" ) | crontab -
    log "root crontab: scheduled daily scan (flock + /var/log/sentinel)"
fi

# --- rkhunter baseline ---
if command -v rkhunter >/dev/null 2>&1; then
    log "setting rkhunter baseline (--propupd) ..."
    rkhunter --propupd && log "rkhunter baseline set" \
        || log "WARN: rkhunter --propupd failed"
else
    log "WARN: rkhunter not installed (run: apt-get install -y rkhunter chkrootkit)"
fi

log "=== deploy complete ==="
log "verify: sudo crontab -l"
log "        sudo $DST"
log "        sudo tail $LOG_DIR/daily_scan.log"
