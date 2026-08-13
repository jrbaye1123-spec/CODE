#!/usr/bin/env python3
"""Sentinel trap — defensive-deception quarantine controller for repeat offenders.

Decision side only (no retaliation, no active harm):

  repeat offender detected
    -> validate the IP is globally routable and not exempt
    -> add it to an ipset (sentinel_trap / sentinel_trap6) with a TTL
    -> the firewall's `nat PREROUTING` chain (deployed separately, later)
       redirects trapped IPs to a decoy; the TTL expires automatically.

Two modes:
  --dry-run (default)  validate, log a proposed trap to JSONL, change nothing
  --enforce            actually run `sudo ipset add` (deferred — requires a
                       separate root-owned /usr/local/sbin/sentinel-trap helper)

Trappability uses ipaddress.is_global, which excludes loopback, RFC1918,
link-local, multicast, reserved, documentation ranges (203.0.113.0/24,
198.51.100.0/24, 2001:db8::/32), and CGNAT shared space (100.64.0.0/10).

Usage:
  trap.py --dry-run --add-offender 8.8.8.8 --ttl 3600 --reason repeat_offender
  trap.py --enforce  --add-offender 8.8.8.8 --ttl 3600 --reason repeat_offender
  trap.py --remove-offender 8.8.8.8
  trap.py --list-offenders
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from ipaddress import ip_address
from pathlib import Path

TRAP_SET4: str = "sentinel_trap"
TRAP_SET6: str = "sentinel_trap6"
TRAP_TTL_SECONDS: int = 3600

# Explicit exemptions for anything is_global still considers routable but
# which you never want trapped (your VPN exit IP, jump host, monitoring agent).
ADMIN_EXCEPTIONS: frozenset[str] = frozenset()

EVENT_LOG: Path = Path.home() / ".local" / "state" / "sentinel" / "trap-events.jsonl"


def is_trappable(ip: str) -> bool:
    """True only for globally routable, non-exempt addresses."""
    if ip in ADMIN_EXCEPTIONS:
        return False
    try:
        return ip_address(ip).is_global
    except ValueError:
        return False


def _set_for(ip: str) -> str:
    return TRAP_SET6 if ":" in ip else TRAP_SET4


def _log_event(mode: str, action: str, ip: str, ttl_seconds: int, reason: str) -> None:
    EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": mode,
        "action": action,
        "ip": ip,
        "ttl_seconds": ttl_seconds,
        "reason": reason,
    }
    with EVENT_LOG.open("a") as fh:
        fh.write(json.dumps(event) + "\n")


def add_offender(ip: str, ttl_seconds: int, reason: str, enforce: bool) -> int:
    if not is_trappable(ip):
        print(f"REFUSING to trap non-trappable IP: {ip}")
        return 1

    set_name = _set_for(ip)
    cmd = ["sudo", "ipset", "add", set_name, ip,
           "timeout", str(ttl_seconds), "-exist"]
    mode = "enforce" if enforce else "dry-run"

    _log_event(mode, "add_offender", ip, ttl_seconds, reason)

    if enforce:
        try:
            subprocess.run(cmd, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"TRAP FAILED for {ip}: {e}")
            return 1
        print(f"TRAPPED {ip} for {ttl_seconds}s in {set_name}")
    else:
        print("TRAP DRY-RUN")
        print(f"ip={ip}")
        print(f"ttl={ttl_seconds}")
        print(f"reason={reason}")
        print(f"proposed: {' '.join(cmd)}")
    return 0


def remove_offender(ip: str, enforce: bool) -> int:
    set_name = _set_for(ip)
    cmd = ["sudo", "ipset", "del", set_name, ip]
    _log_event("enforce" if enforce else "dry-run", "remove_offender", ip, 0, "manual")
    if enforce:
        subprocess.run(cmd, check=False)
        print(f"REMOVED {ip} from {set_name}")
    else:
        print(f"DRY-RUN: {' '.join(cmd)}")
    return 0


def list_offenders() -> int:
    for set_name in (TRAP_SET4, TRAP_SET6):
        try:
            subprocess.run(["sudo", "ipset", "list", set_name], check=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"ipset list {set_name} failed: {e}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Sentinel trap controller")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true",
                      help="validate + log only (default)")
    mode.add_argument("--enforce", action="store_true",
                      help="actually run `sudo ipset`")

    action = ap.add_mutually_exclusive_group(required=True)
    action.add_argument("--add-offender", metavar="IP")
    action.add_argument("--remove-offender", metavar="IP")
    action.add_argument("--list-offenders", action="store_true")

    ap.add_argument("--ttl", type=int, default=TRAP_TTL_SECONDS,
                    help="trap TTL seconds (default 3600)")
    ap.add_argument("--reason", default="repeat_offender", help="audit reason")
    args = ap.parse_args(argv)

    enforce = bool(args.enforce)  # dry-run is the default when neither flag set

    if args.add_offender:
        return add_offender(args.add_offender, args.ttl, args.reason, enforce)
    if args.remove_offender:
        return remove_offender(args.remove_offender, enforce)
    return list_offenders()


if __name__ == "__main__":
    sys.exit(main())
