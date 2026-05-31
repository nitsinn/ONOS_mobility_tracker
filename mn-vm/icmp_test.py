#!/usr/bin/env python
"""
Live ICMP Telemetry Dashboard for Mininet-WiFi.
One ping every 0.5s. Statistics start after a 5-second warmup.
Tracks drop transitions (normal->drop) and reports dropped packets per transition.
"""
import sys
import subprocess
import re
import time
from datetime import datetime


def run_live_dashboard(station_name, target_ip):

    cmd = ['ping', '-O', '-i', '0.5', target_ip]
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )

    # ── Counters ──────────────────────────────────────────────────────────────
    sent          = 0
    received      = 0
    latest_rtt    = "N/A"
    status        = "INITIALIZING..."

    # Transition tracking
    transitions   = []   # {"time": datetime, "drops": int, "closed": bool}
    in_drop       = False
    current_drops = 0

    # Warmup
    WARMUP_SECONDS = 5
    start_time     = time.monotonic()
    warmed_up      = False

    sys.stdout.write('\033[2J\033[H')
    sys.stdout.flush()

    def format_transitions():
        if not transitions:
            return "  (none yet)\n"
        lines  = f"  {'#':<4} {'Time':<22} {'Drops'}\n"
        lines += "  " + "-" * 35 + "\n"
        for i, t in enumerate(transitions, 1):
            ts   = t["time"].strftime("%H:%M:%S.%f")[:-3]
            drps = str(t["drops"]) + ("" if t["closed"] else "...")
            lines += f"  {i:<4} {ts:<22} {drps}\n"
        return lines

    try:
        for line in process.stdout:
            line    = line.strip()
            now     = time.monotonic()
            elapsed = now - start_time

            # ── Warmup gate ───────────────────────────────────────────────────
            if elapsed < WARMUP_SECONDS:
                remaining = WARMUP_SECONDS - elapsed
                sys.stdout.write(
                    f"\033[H\033[J\n"
                    f"  Warming up -- statistics start in {remaining:.1f}s ...\n"
                )
                sys.stdout.flush()
                continue

            if not warmed_up:
                warmed_up     = True
                sent          = 0
                received      = 0
                in_drop       = False
                current_drops = 0
                transitions   = []

            # ── Parse line ────────────────────────────────────────────────────
            is_drop = False

            if "bytes from" in line:
                sent     += 1
                received += 1
                status    = "CONNECTED  "
                rtt_match = re.search(r'time=([\d.]+)\s*ms', line)
                latest_rtt = (rtt_match.group(1) + " ms") if rtt_match else latest_rtt

                if in_drop:
                    transitions[-1]["closed"] = True
                    in_drop       = False
                    current_drops = 0

            elif "no answer yet" in line:
                sent      += 1
                status     = "LOSS       "
                latest_rtt = "DROPPED"
                is_drop    = True

            elif "unreachable" in line.lower() or "timeout" in line.lower():
                sent      += 1
                status     = "UNREACHABLE"
                latest_rtt = "FAIL"
                is_drop    = True

            else:
                # Header line or noise -- skip
                continue

            # ── Transition logic ──────────────────────────────────────────────
            if is_drop:
                if not in_drop:
                    in_drop       = True
                    current_drops = 1
                    transitions.append({
                        "time":   datetime.now(),
                        "drops":  1,
                        "closed": False
                    })
                else:
                    current_drops           += 1
                    transitions[-1]["drops"] = current_drops

            # ── Stats ─────────────────────────────────────────────────────────
            lost        = sent - received
            loss_pct    = (lost     / sent * 100) if sent > 0 else 0.0
            success_pct = (received / sent * 100) if sent > 0 else 0.0
            n_trans     = len(transitions)
            closed      = [t for t in transitions if t["closed"]]
            avg_closed  = (
                sum(t["drops"] for t in closed) / len(closed) if closed else 0.0
            )
            total_per_t = (lost / n_trans) if n_trans > 0 else 0.0
            timestamp   = datetime.now().strftime("%H:%M:%S.%f")[:-3]

            # ── Draw ──────────────────────────────────────────────────────────
            out = (
                f"\033[H\033[J"
                f"\n================================================\n"
                f"  ICMP TELEMETRY: {station_name.upper()} -> {target_ip}\n"
                f"================================================\n"
                f"  Time:        {timestamp}\n"
                f"  Status:      {status}\n"
                f"  Latest RTT:  {latest_rtt}\n"
                f"------------------------------------------------\n"
                f"  Sent:        {sent}\n"
                f"  Received:    {received}   ({success_pct:.1f}%)\n"
                f"  Lost:        {lost}   ({loss_pct:.1f}%)\n"
                f"------------------------------------------------\n"
                f"  Drop transitions:          {n_trans}\n"
            )

            if n_trans > 0:
                out += (
                    f"  Total lost / transitions:  {total_per_t:.2f} pkts\n"
                    f"  Avg drops / closed burst:  {avg_closed:.2f} pkts\n"
                    f"================================================\n"
                    f"  TRANSITION LOG\n"
                    f"================================================\n"
                    + format_transitions()
                )

            out += "================================================\n"

            sys.stdout.write(out)
            sys.stdout.flush()

    except KeyboardInterrupt:
        pass
    finally:
        process.terminate()
        _final_report(station_name, target_ip, sent, received, transitions, start_time)


def _final_report(station_name, target_ip, sent, received, transitions, start_time):
    lost        = sent - received
    success_pct = (received / sent * 100) if sent > 0 else 0.0
    loss_pct    = (lost     / sent * 100) if sent > 0 else 0.0
    n_trans     = len(transitions)
    closed      = [t for t in transitions if t["closed"]]
    elapsed     = time.monotonic() - start_time

    print("\n\n" + "=" * 50)
    print("  FINAL REPORT")
    print("=" * 50)
    print(f"  {station_name}  ->  {target_ip}")
    print(f"  Duration: {elapsed:.1f}s  (after 5s warmup)")
    print("-" * 50)
    print(f"  Sent:      {sent}")
    print(f"  Received:  {received}  ({success_pct:.1f}%)")
    print(f"  Lost:      {lost}  ({loss_pct:.1f}%)")
    print("-" * 50)
    print(f"  Drop transitions (normal->drop): {n_trans}")

    if n_trans > 0:
        print(f"  Total lost / transitions:        {lost / n_trans:.2f} pkts/transition")
    if closed:
        avg = sum(t["drops"] for t in closed) / len(closed)
        print(f"  Avg drops / closed burst:        {avg:.2f} pkts  ({len(closed)} closed)")

    if transitions:
        print(f"\n  {'#':<4} {'Time':<22} {'Drops':<8} {'Closed?'}")
        print("  " + "-" * 42)
        for i, t in enumerate(transitions, 1):
            ts = t["time"].strftime("%H:%M:%S.%f")[:-3]
            print(f"  {i:<4} {ts:<22} {t['drops']:<8} {'yes' if t['closed'] else 'ongoing'}")

    print("=" * 50 + "\n")


def main():
    if len(sys.argv) < 3:
        print("Usage: python icmp_test.py <station_name> <target_ip>")
        sys.exit(1)

    run_live_dashboard(sys.argv[1].lower(), sys.argv[2])


if __name__ == '__main__':
    main()