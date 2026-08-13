#!/usr/bin/env python3
"""
Sentinel — lightweight host watchdog for Zorin OS (userspace, no root needed).

Requirements: user in 'adm' group (for /var/log/auth.log), notify-send
(libnotify-bin), python3. Uses only the standard library.

Checks:
  1. Failed SSH / password authentication attempts in /var/log/auth.log
  2. Processes exceeding CPU or memory thresholds
  3. Listening TCP/UDP ports vs. an allow-list

Alerts via desktop notification (notify-send) and appends to a log file.
Tracks per-IP auth-failure counts in a state file so the same incident is
not re-notified on every cron run — only new IPs or rising counts alert.

Usage:
  sentinel.py --once      # run all checks once (for cron)
  sentinel.py --test      # dry run: print findings to stdout, no notify
  sentinel.py --help
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, cast

# --- Configuration -----------------------------------------------------------
AUTH_LOG = "/var/log/auth.log"
STATE_FILE = Path.home() / ".local" / "state" / "sentinel-state.json"
LOG_FILE = Path.home() / "projects" / "sentinel" / "sentinel.log"
TRAP_SCRIPT = Path.home() / "projects" / "sentinel" / "trap.py"
TRAP_THRESHOLD_COUNT = 5  # failures before a repeat-offender trap is proposed
TRAP_TTL_SECONDS = 3600

CPU_THRESHOLD = 80.0  # percent
MEM_THRESHOLD = 50.0  # percent

# Ports we consider normal/expected on a desktop. Anything else listening on
# a wildcard address triggers an alert.
ALLOWED_PORTS = {
    22,  # ssh
    53,  # dns
    80,  # http
    443,  # https
    631,  # cups (printing)
    5353,  # avahi/mdns
    6463,  # discord rpc / some apps
    1716,  # kde connect
    9050,  # tor (if used)
}

# Regexes for auth failures. Captures the source IPv4 address.
AUTH_FAIL_PATTERNS = [
    re.compile(r"Failed password for .* from (\d{1,3}(?:\.\d{1,3}){3})"),
    re.compile(r"authentication failure.*rhost=(\d{1,3}(?:\.\d{1,3}){3})"),
    re.compile(r"Invalid user .* from (\d{1,3}(?:\.\d{1,3}){3})"),
    re.compile(r"Connection closed by .*?(\d{1,3}(?:\.\d{1,3}){3})"),
]


# --- Helpers -----------------------------------------------------------------
def load_state() -> dict[str, Any]:
    if STATE_FILE.exists():
        try:
            return cast(dict[str, Any], json.loads(STATE_FILE.read_text()))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_state(state: dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with LOG_FILE.open("a") as fh:
        fh.write(f"[{stamp}] {msg}\n")


def notify(title: str, body: str, urgency: str = "normal") -> bool:
    """Send a desktop notification. Returns True if one was sent."""
    if not os.environ.get("DISPLAY"):
        return False
    try:
        subprocess.run(
            ["notify-send", "-u", urgency, "-a", "Sentinel", title, body],
            check=False,
            timeout=5,
        )
        return True
    except (FileNotFoundError, subprocess.SubprocessError):
        return False


def emit(title: str, body: str, urgency: str, dry_run: bool) -> None:
    """Notify (or print in dry-run) and log."""
    log(f"{title}: {body}")
    if dry_run:
        print(f"[ALERT] {title}: {body}")
    else:
        notify(title, body, urgency)


def invoke_trap_dry_run(ip: str) -> None:
    """Propose a trap for a repeat offender (dry-run only; never enforces)."""
    subprocess.run(
        [
            sys.executable,
            str(TRAP_SCRIPT),
            "--dry-run",
            "--add-offender",
            ip,
            "--ttl",
            str(TRAP_TTL_SECONDS),
            "--reason",
            "repeat_offender",
        ],
        check=False,
    )


# --- Check 1: auth failures --------------------------------------------------
def check_auth_failures(
    state: dict[str, Any], dry_run: bool
) -> list[tuple[str, int, int]]:
    alerts: list[tuple[str, int, int]] = []
    if not os.access(AUTH_LOG, os.R_OK):
        return alerts

    counts: dict[str, int] = {}
    try:
        with open(AUTH_LOG, "r", errors="ignore") as fh:
            for line in fh:
                for pat in AUTH_FAIL_PATTERNS:
                    m = pat.search(line)
                    if m:
                        ip = m.group(1)
                        counts[ip] = counts.get(ip, 0) + 1
                        break
    except OSError as e:
        emit("auth-fail", f"could not read {AUTH_LOG}: {e}", "normal", dry_run)
        return alerts

    prev: dict[str, int] = state.get("auth_failures", {})

    for ip, count in counts.items():
        old = prev.get(ip, 0)
        if count > old:
            delta = count - old
            alerts.append((ip, count, delta))

    state["auth_failures"] = counts
    return alerts


# --- Check 2: processes ------------------------------------------------------
def check_processes(dry_run: bool) -> list[tuple[str, str, str, float, float]]:
    alerts: list[tuple[str, str, str, float, float]] = []
    try:
        proc = subprocess.run(
            ["ps", "-eo", "pid,user:20,comm:40,%cpu,%mem", "--sort=-%cpu"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError):
        return alerts

    for line in (proc.stdout or "").splitlines()[1:]:
        parts = line.split(None, 4)
        if len(parts) < 5:
            continue
        pid, user, comm, cpu_s, mem_s = parts
        try:
            cpu = float(cpu_s)
            mem = float(mem_s)
        except ValueError:
            continue
        if cpu > CPU_THRESHOLD or mem > MEM_THRESHOLD:
            alerts.append((pid, user, comm, cpu, mem))
    return alerts


# --- Check 3: listening ports ------------------------------------------------
def check_ports(dry_run: bool) -> list[tuple[str, int, str]]:
    alerts: list[tuple[str, int, str]] = []
    try:
        proc = subprocess.run(
            ["ss", "-tuln"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError):
        return alerts

    seen: set[tuple[str, int]] = set()
    for line in (proc.stdout or "").splitlines()[1:]:
        parts = line.split()
        if len(parts) < 5:
            continue
        local = parts[4]  # e.g. "0.0.0.0:8080" or "[::]:443"
        addr = local.rsplit(":", 1)[0]
        port_str = local.rsplit(":", 1)[1]
        if not port_str.isdigit():
            continue
        port_num = int(port_str)
        if addr not in ("0.0.0.0", "[::]", "*", "[::1]", "127.0.0.1"):
            continue
        if port_num in ALLOWED_PORTS or (addr, port_num) in seen:
            continue
        seen.add((addr, port_num))
        alerts.append((addr, port_num, parts[0]))
    return alerts


# --- Main --------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description="Sentinel host watchdog")
    ap.add_argument("--once", action="store_true", help="run checks once")
    ap.add_argument(
        "--test", action="store_true", help="dry run: print findings, do not notify"
    )
    args = ap.parse_args()

    dry_run: bool = args.test or not args.once
    state = load_state()

    # Auth failures
    for ip, count, delta in check_auth_failures(state, dry_run):
        emit(
            "SSH auth failures",
            f"{delta} new failure(s) from {ip} (total {count})",
            "critical" if delta >= 5 else "normal",
            dry_run,
        )
        if count >= TRAP_THRESHOLD_COUNT:
            invoke_trap_dry_run(ip)
            emit(
                "TRAP PROPOSED",
                f"{ip} crossed threshold ({count} failures) — dry-run trap logged",
                "critical",
                dry_run,
            )

    # Processes
    for pid, user, comm, cpu, mem in check_processes(dry_run):
        emit(
            "High resource process",
            f"{comm} (pid {pid}, user {user}) CPU {cpu:.0f}% MEM {mem:.0f}%",
            "normal",
            dry_run,
        )

    # Ports (deduped: alert once per newly-seen listener)
    seen_ports: set[str] = set(state.get("seen_ports", []))
    for addr, port, proto in check_ports(dry_run):
        key = f"{proto}:{addr}:{port}"
        if key in seen_ports:
            continue
        seen_ports.add(key)
        emit(
            "Unexpected listening port",
            f"{proto} {addr}:{port} not in allow-list",
            "critical",
            dry_run,
        )
    state["seen_ports"] = sorted(seen_ports)

    save_state(state)

    if args.test or args.once:
        print("Sentinel check complete.")


if __name__ == "__main__":
    main()
