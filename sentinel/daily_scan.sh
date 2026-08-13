#!/usr/bin/env bash
# Sentinel daily rootkit scan — runs as root via cron.
#
# Deployed root-owned to /usr/local/sbin/sentinel-daily-scan by
# deploy_daily_scan_root.sh; logs to /var/log/sentinel/daily_scan.log.
# Root cron MUST run a root-owned copy, never a user-writable script
# (a user-writable script in root cron is a local privilege-escalation path).
#
# Deliberately does NOT run `rkhunter --propupd` automatically: that would
# re-baseline rkhunter to the CURRENT machine state every day and bless any
# future compromise as "clean". Run `sudo rkhunter --propupd` manually, only
# after reviewing a scan and only after legitimate system updates.
set -u

LOG_DIR="/var/log/sentinel"
LOG_FILE="$LOG_DIR/daily_scan.log"

if [ "$(id -u)" -ne 0 ]; then
    echo "sentinel-daily-scan must run as root (rkhunter/chkrootkit need it)." >&2
    exit 1
fi

mkdir -p "$LOG_DIR"

{
    echo "=== DAILY SCAN: $(date '+%Y-%m-%d %H:%M:%S') ==="
    echo "--- rkhunter ---"
    rkhunter --check --skip-keypress --nocolors
    echo "--- chkrootkit ---"
    chkrootkit
    echo "=== SCAN COMPLETE ==="
} >> "$LOG_FILE" 2>&1
