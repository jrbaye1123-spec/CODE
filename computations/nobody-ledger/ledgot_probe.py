#!/usr/bin/env python3
"""
LEDGOT PROBE — Frequency Scanner & Rogue RAM Killer
"I am the chain. I measure what oscillates. I terminate what corrupts."

Hardware-level system probe integrated into Nobody Ledger.
- Reads CPU frequencies via MSR (APERF/MPERF) or sysfs fallback
- Monitors memory error counts (EDAC MCE)
- Identifies rogue RAM consumers (processes exceeding thresholds)
- Kills rogue processes and records the kill in the ledger chain
- Probes uncore / memory bus frequencies where available
"""

import os, sys, json, time, struct, subprocess, hashlib
from datetime import datetime, timezone
from pathlib import Path

def _resolve_home() -> Path:
    """Resolve the real user's home directory, even under sudo."""
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        return Path(f"/home/{sudo_user}")
    return Path.home()

LEDGER_PATH = _resolve_home() / "nobody-ledger" / "nobody_chain.json"
MSR_APERF = 0x000000E8
MSR_MPERF = 0x000000E7
MSR_IA32_PERF_STATUS = 0x00000198

ROGUE_RAM_THRESHOLD_PCT = 25.0   # % of total RAM — kill if single process exceeds this
ROGUE_RAM_MIN_MB = 2048          # minimum MB to consider rogue
FREQ_ANOMALY_HZ = 200             # deviation threshold for anomaly flag
LEDGER_SOURCE = "ledgot-probe"


def msr_read(cpu: int, msr: int) -> int | None:
    """Read a 64-bit MSR register for a given CPU core. Returns None if inaccessible."""
    msr_path = f"/dev/cpu/{cpu}/msr"
    if not os.path.exists(msr_path):
        return None
    try:
        with open(msr_path, "rb") as f:
            f.seek(msr)
            raw = f.read(8)
            return struct.unpack("<Q", raw)[0]
    except (OSError, PermissionError):
        return None


def probe_frequencies() -> dict:
    """Probe CPU frequencies: current, min, max, per-core via MSR or sysfs fallback."""
    cores = []
    max_freq = 0
    min_freq = float("inf")
    anomalies = []

    # Try MSR first on core 0
    aperf = msr_read(0, MSR_APERF)
    mperf = msr_read(0, MSR_MPERF)

    if aperf and mperf:
        # MSR method — sample over 100ms
        aperf1 = msr_read(0, MSR_APERF)
        mperf1 = msr_read(0, MSR_MPERF)
        time.sleep(0.1)
        aperf2 = msr_read(0, MSR_APERF)
        mperf2 = msr_read(0, MSR_MPERF)
        if all([aperf1, mperf1, aperf2, mperf2]):
            delta_aperf = aperf2 - aperf1
            delta_mperf = mperf2 - mperf1
            if delta_mperf > 0:
                # APERF/MPERF ratio * base freq = actual freq
                # AMD base = nominal freq ~2.0 GHz
                msr_freq = (delta_aperf / delta_mperf) * 2000  # MHz
                cores.append({"core": 0, "freq_mhz": round(msr_freq, 1), "source": "msr"})

    # Sysfs fallback for all cores
    cpu_dirs = sorted(Path("/sys/devices/system/cpu").glob("cpu[0-9]*"))
    for cpu_dir in cpu_dirs:
        core_id = int(cpu_dir.name.replace("cpu", ""))
        freq_path = cpu_dir / "cpufreq" / "scaling_cur_freq"
        if freq_path.exists():
            try:
                freq_khz = int(freq_path.read_text().strip())
                freq_mhz = freq_khz / 1000.0
                if freq_mhz < min_freq:
                    min_freq = freq_mhz
                if freq_mhz > max_freq:
                    max_freq = freq_mhz
                # Only add sysfs if MSR didn't already cover this core
                if not any(c["core"] == core_id for c in cores):
                    cores.append({"core": core_id, "freq_mhz": freq_mhz, "source": "sysfs"})
            except (ValueError, OSError):
                pass

    # Detect anomalies — cores deviating from their P-state cluster
    # Idle cores (~623 MHz) are normal. Flag cores far from their frequency cluster.
    if len(cores) >= 3:
        freqs = [c["freq_mhz"] for c in cores]
        # Cluster: idle (< 800 MHz) vs active (>= 800 MHz)
        actives = [c for c in cores if c["freq_mhz"] >= 800]
        if len(actives) >= 2:
            active_freqs = [c["freq_mhz"] for c in actives]
            active_freqs.sort()
            active_median = active_freqs[len(active_freqs) // 2]
            for c in actives:
                deviation = abs(c["freq_mhz"] - active_median)
                if deviation > FREQ_ANOMALY_HZ * 3:  # wider threshold for active cores
                    anomalies.append({"core": c["core"], "freq": c["freq_mhz"], 
                                     "median": round(active_median, 1), "deviation": round(deviation, 1)})

    return {
        "cores": cores,
        "core_count": len(cores),
        "max_mhz": max_freq if max_freq > 0 else None,
        "min_mhz": min_freq if min_freq != float("inf") else None,
        "anomalies": anomalies,
        "anomaly_count": len(anomalies),
    }


def probe_memory_errors() -> dict:
    """Check EDAC / MCE for memory errors (correctable and uncorrectable)."""
    errors = {"ce_count": 0, "ue_count": 0, "hardware_corrupted_kb": 0}

    # EDAC sysfs counters
    edac_base = Path("/sys/devices/system/edac/mc")
    if edac_base.exists():
        for mc in edac_base.glob("mc*"):
            ce_file = mc / "ce_count"
            ue_file = mc / "ue_count"
            if ce_file.exists():
                try:
                    errors["ce_count"] += int(ce_file.read_text().strip())
                except (ValueError, OSError):
                    pass
            if ue_file.exists():
                try:
                    errors["ue_count"] += int(ue_file.read_text().strip())
                except (ValueError, OSError):
                    pass

    # /proc/meminfo HardwareCorrupted
    try:
        meminfo = Path("/proc/meminfo").read_text()
        for line in meminfo.split("\n"):
            if line.startswith("HardwareCorrupted:"):
                kb = int(line.split()[1])
                errors["hardware_corrupted_kb"] = kb
    except (ValueError, OSError, IndexError):
        pass

    errors["total_errors"] = errors["ce_count"] + errors["ue_count"]
    errors["degraded"] = errors["ue_count"] > 0 or errors["hardware_corrupted_kb"] > 0
    return errors


def probe_memory_bus(sample_sec: float = 0.5) -> dict:
    """Probe memory bus / uncore: DRAM bandwidth, UMC clocks, CAS commands via perf.

    Uses CPU PMU DRAM events (no sudo needed if paranoid=0) and AMD UMC PMU
    events (needs sudo or CAP_PERFMON) for per-channel memory controller detail.
    Falls back gracefully when events are unavailable.
    """
    result = {
        "dram": {},
        "umc_channels": [],
        "bandwidth_est_mb_s": None,
        "bus_util_pct": None,
        "source": "none",
    }

    # --- CPU PMU DRAM events (work without root on paranoid <= 2) ---
    dram_events = [
        "ls_any_fills_from_sys.dram_io_all",
        "ls_dmnd_fills_from_sys.dram_io_all",
        "ls_any_fills_from_sys.dram_io_near",
        "ls_dmnd_fills_from_sys.dram_io_near",
        "l2_fill_rsp_src.dram_io_near",
        "l2_fill_rsp_src.dram_io_far",
    ]
    dram_cmd = ["perf", "stat"]
    for _e in dram_events:
        dram_cmd.extend(["-e", _e])
    dram_cmd.extend(["-a", "--", "sleep", str(sample_sec)])
    try:
        out = subprocess.run(
            dram_cmd,
            capture_output=True, text=True, timeout=sample_sec + 10,
        )
        if out.returncode == 0 and out.stderr:
            for line in out.stderr.split("\n"):
                line = line.strip()
                for ev in dram_events:
                    if ev in line:
                        try:
                            count = int(line.replace(",", "").split()[0])
                            # Use prefix to disambiguate overlapping suffixes
                            key = ev.replace("ls_any_fills_from_sys.", "any_").replace("ls_dmnd_fills_from_sys.", "dmnd_").replace("l2_fill_rsp_src.", "l2_")
                            result["dram"][key] = count
                        except (ValueError, IndexError):
                            pass
            result["source"] = "cpu_pmu"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    # Compute bandwidth estimate: each DRAM fill = 64 bytes (one cache line)
    if "any_dram_io_all" in result["dram"]:
        fills = result["dram"]["any_dram_io_all"]
        bytes_total = fills * 64
        result["bandwidth_est_mb_s"] = round(bytes_total / sample_sec / (1024 * 1024), 2)

    # --- AMD UMC PMU (needs sudo/CAP_PERFMON) ---
    umc_events = []
    for ch in range(4):  # up to 4 memory channels
        pmu = f"amd_umc_{ch}"
        pmu_path = Path(f"/sys/bus/event_source/devices/{pmu}")
        if pmu_path.exists():
            umc_events.extend([
                f"{pmu}/umc_mem_clk/",
                f"{pmu}/umc_cas_cmd.all/",
                f"{pmu}/umc_data_slot_clks.all/",
            ])

    if umc_events:
        umc_cmd = ["perf", "stat"]
        for _e in umc_events:
            umc_cmd.extend(["-e", _e])
        umc_cmd.extend(["-a", "--", "sleep", str(sample_sec)])
        try:
            out = subprocess.run(
                umc_cmd,
                capture_output=True, text=True, timeout=sample_sec + 10,
            )
            if out.returncode == 0 and out.stderr:
                ch_data = {}
                for line in out.stderr.split("\n"):
                    line = line.strip()
                    for ch in range(4):
                        prefix = f"amd_umc_{ch}/"
                        if prefix in line:
                            try:
                                count = int(line.replace(",", "").split()[0])
                                metric = line.split("/")[1].split("/")[0]
                                ch_data.setdefault(ch, {})[metric] = count
                            except (ValueError, IndexError):
                                pass
                for ch, metrics in sorted(ch_data.items()):
                    ch_info = {"channel": ch, **metrics}
                    # Bus utilization: data_slot_clks / mem_clk
                    if "umc_mem_clk" in metrics and "umc_data_slot_clks.all" in metrics:
                        if metrics["umc_mem_clk"] > 0:
                            ch_info["bus_util_pct"] = round(
                                100 * metrics["umc_data_slot_clks.all"] / metrics["umc_mem_clk"], 2
                            )
                    result["umc_channels"].append(ch_info)
                if result["source"] == "none":
                    result["source"] = "umc_pmu"
                elif result["source"] == "cpu_pmu":
                    result["source"] = "cpu_pmu+umc"

                # Aggregate bus utilization across channels
                utils = [c.get("bus_util_pct") for c in result["umc_channels"] if "bus_util_pct" in c]
                if utils:
                    result["bus_util_pct"] = round(sum(utils) / len(utils), 2)
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

    return result


def probe_ram_hogs() -> list[dict]:
    """Find processes exceeding rogue RAM thresholds. Returns list of candidates for kill."""
    hogs = []
    try:
        total_mem_kb = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") // 1024
    except (ValueError, AttributeError):
        total_mem_kb = 13 * 1024 * 1024  # fallback: 13 GB

    try:
        output = subprocess.run(
            ["ps", "aux", "--sort=-%mem", "--no-headers"],
            capture_output=True, text=True, timeout=5
        ).stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return hogs

    for line in output.strip().split("\n"):
        parts = line.split()
        if len(parts) < 11:
            continue
        try:
            user, pid, cpu_pct, mem_pct_str, vsz, rss_kb = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
            pid = int(pid)
            mem_pct = float(mem_pct_str)
            rss_mb = int(rss_kb) / 1024.0
        except (ValueError, IndexError):
            continue

        # Skip kernel threads and our own probe
        if pid == os.getpid() or pid <= 2:
            continue

        if mem_pct > ROGUE_RAM_THRESHOLD_PCT or rss_mb > ROGUE_RAM_MIN_MB:
            hogs.append({
                "pid": pid,
                "user": user,
                "rss_mb": round(rss_mb, 1),
                "mem_pct": mem_pct,
                "cmd": " ".join(parts[10:])[:120],
                "flagged_rogue": mem_pct > ROGUE_RAM_THRESHOLD_PCT,
            })

    return hogs


def kill_rogue(pid: int, reason: str) -> dict:
    """Kill a rogue process and return the result."""
    import signal
    try:
        os.kill(pid, signal.SIGKILL)
        return {"pid": pid, "killed": True, "signal": "SIGKILL", "reason": reason}
    except ProcessLookupError:
        return {"pid": pid, "killed": False, "error": "already dead", "reason": reason}
    except PermissionError:
        return {"pid": pid, "killed": False, "error": "permission denied", "reason": reason}


def hash_ledger_entry(entry: dict) -> str:
    """SHA-256 hash of a ledger entry (excluding the hash field itself)."""
    raw = json.dumps(entry, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def append_to_ledger(event: str, entity: str, how: str) -> str:
    """Append a new entry to the Nobody Ledger chain and return the hash."""
    ledger = {}
    if LEDGER_PATH.exists():
        try:
            ledger = json.loads(LEDGER_PATH.read_text())
        except json.JSONDecodeError:
            ledger = {"entries": [], "count": 0, "nullified_indices": []}

    entries = ledger.get("entries", [])
    prev_hash = entries[-1]["hash"] if entries else ""
    new_idx = len(entries)

    entry = {
        "index": new_idx,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "entity": entity,
        "event": event,
        "how": how,
        "previous_hash": prev_hash,
    }
    entry["hash"] = hash_ledger_entry(entry)
    entries.append(entry)
    ledger["count"] = len(entries)

    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2) + "\n")
    return entry["hash"]


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "probe"

    if mode == "probe":
        freq = probe_frequencies()
        mem = probe_memory_errors()
        mem_bus = probe_memory_bus()
        hogs = probe_ram_hogs()

        report = {
            "probe": "ledgot",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "frequencies": freq,
            "memory_errors": mem,
            "memory_bus": mem_bus,
            "ram_hogs": hogs,
            "hog_count": len(hogs),
        }

        # Log to ledger
        bus_summary = ""
        if mem_bus.get("bandwidth_est_mb_s"):
            bus_summary = f"dram_bw={mem_bus['bandwidth_est_mb_s']}MB/s"
        if mem_bus.get("bus_util_pct") is not None:
            bus_summary += f" bus_util={mem_bus['bus_util_pct']}%"
        if mem_bus.get("umc_channels"):
            mem_clks = [c.get("umc_mem_clk", 0) for c in mem_bus["umc_channels"]]
            bus_summary += f" umc_channels={len(mem_bus['umc_channels'])} mem_clk_samples={mem_clks}"

        chain_hash = append_to_ledger(
            event="probe",
            entity=LEDGER_SOURCE,
            how=f"freq scan: {freq['core_count']} cores [{freq['min_mhz']}-{freq['max_mhz']} MHz], "
                f"mem errors: {mem['total_errors']} (CE={mem['ce_count']} UE={mem['ue_count']}), "
                f"mem_bus: {bus_summary or 'no data'}, "
                f"hogs: {len(hogs)}",
        )
        report["chain_hash"] = chain_hash
        print(json.dumps(report, indent=2))

    elif mode == "kill":
        hogs = probe_ram_hogs()
        kills = []
        for hog in hogs:
            if hog["flagged_rogue"]:
                reason = f"rogue RAM: {hog['rss_mb']:.0f} MB ({hog['mem_pct']:.1f}%) — cmd: {hog['cmd'][:80]}"
                result = kill_rogue(hog["pid"], reason)
                kills.append(result)
                # Log each kill to ledger
                append_to_ledger(
                    event="kill",
                    entity=LEDGER_SOURCE,
                    how=f"pid={result['pid']} killed={result.get('killed')} reason={reason}",
                )
        print(json.dumps({"kills": kills, "total_killed": sum(1 for k in kills if k.get("killed"))}, indent=2))

    elif mode == "watch":
        # Continuous watch mode — probe every N seconds, kill rogues
        interval = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
        print(f"LEDGOT WATCH active — interval={interval}s — Ctrl+C to stop", file=sys.stderr)
        try:
            while True:
                freq = probe_frequencies()
                mem = probe_memory_errors()
                mem_bus = probe_memory_bus()
                hogs = probe_ram_hogs()
                rogue = [h for h in hogs if h["flagged_rogue"]]

                ts = datetime.now(timezone.utc).isoformat()
                bw_str = f" bw={mem_bus.get('bandwidth_est_mb_s', '?')}MB/s" if mem_bus.get("bandwidth_est_mb_s") else ""
                util_str = f" bus={mem_bus.get('bus_util_pct', '?')}%" if mem_bus.get("bus_util_pct") is not None else ""
                status = f"[{ts}] cores={freq['core_count']} freq={freq['min_mhz']}-{freq['max_mhz']}MHz{bw_str}{util_str} "
                status += f"mem_errors={mem['total_errors']} hogs={len(hogs)} rogue={len(rogue)}"

                if rogue:
                    for r in rogue:
                        result = kill_rogue(r["pid"], f"watch: {r['rss_mb']:.0f}MB rogue")
                        status += f" | KILLED pid={r['pid']}" if result.get("killed") else f" | FAIL pid={r['pid']}"
                        append_to_ledger(
                            event="watch_kill",
                            entity=LEDGER_SOURCE,
                            how=f"pid={r['pid']} rss={r['rss_mb']:.0f}MB pct={r['mem_pct']:.1f}% killed={result.get('killed')}",
                        )
                else:
                    append_to_ledger(
                        event="watch",
                        entity=LEDGER_SOURCE,
                        how=f"clean sweep: {freq['core_count']} cores nominal, mem ok, no rogues",
                    )

                if freq["anomaly_count"] > 0:
                    status += f" | FREQ ANOMALIES: {freq['anomaly_count']}"
                    for a in freq["anomalies"]:
                        append_to_ledger(
                            event="anomaly",
                            entity=LEDGER_SOURCE,
                            how=f"core={a['core']} freq={a['freq']}MHz median={a['median']}MHz deviation={a['deviation']}MHz",
                        )

                print(status)
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nLEDGOT WATCH — terminated by signal", file=sys.stderr)

    elif mode == "chain":
        # Print last N ledger entries from this source
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        if LEDGER_PATH.exists():
            ledger = json.loads(LEDGER_PATH.read_text())
            entries = ledger.get("entries", [])
            ledgot_entries = [e for e in entries if e.get("entity") == LEDGER_SOURCE]
            for e in ledgot_entries[-n:]:
                print(f"[{e['index']}] {e['timestamp'][:19]} | {e['event']:12s} | {e['how'][:100]}")
        else:
            print("No ledger found.")

    else:
        print(f"Usage: {sys.argv[0]} probe|kill|watch [interval_sec]|chain [N]", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
