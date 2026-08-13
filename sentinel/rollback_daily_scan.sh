#!/usr/bin/env bash
# Reverses deploy_daily_scan_root.sh. Run as root.
#
#   sudo bash /home/nakamichi/projects/sentinel/rollback_daily_scan.sh
set -euo pipefail

DST="/usr/local/sbin/sentinel-daily-scan"
LOG_DIR="/var/log/sentinel"

[ "$(id -u)" -eq 0 ] || { echo "run as root"; exit 1; }

echo "Removing root crontab entry ..."
crontab -l 2>/dev/null | grep -vF "$DST" | crontab - 2>/dev/null || true

echo "Removing deployed script ..."
rm -f "$DST"

echo "Done. (rkhunter baseline is NOT reverted — re-run 'sudo rkhunter --propupd'"
echo "after system changes if you want to re-baseline. $LOG_DIR is left in place.)"
