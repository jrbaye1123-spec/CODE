# Sentinel — host intrusion watchdog for Zorin OS

Userspace host watchdog + defensive-deception trap controller.

- `sentinel.py` — auth-failure / runaway-process / port watchdog (5-min cron)
- `trap.py` — trap controller (dry-run default; ipset-backed, deferred enforcement)
- `daily_scan.sh` — rkhunter + chkrootkit (deployed root-owned)
- `deploy_daily_scan_root.sh` — install + schedule the daily scan (root)
- `rollback_daily_scan.sh` — reverse the deploy
- `crontab.txt` — the 5-min sentinel cron line

Live deploy locations (not this repo): `~/projects/sentinel/` and `~/bin/`.
