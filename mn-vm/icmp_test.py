#!/usr/bin/env python
"""
Live ICMP Telemetry Dashboard for Mininet-WiFi with continuous ARP updates.
Refreshes the terminal screen in-place at 2 pings/sec and sends gratuitous ARP every 2 seconds.
"""
import sys
import subprocess
import re
import threading
import time
from datetime import datetime

def run_gratuitous_arp(gateway_ip, interval=2):
    """
    Send gratuitous ARP packets at regular intervals to ensure ONOS detects host location.
    This helps with WiFi roaming detection.
    """
    while True:
        try:
            # Send gratuitous ARP using arping
            subprocess.run(
                ['arping', '-c', '1', gateway_ip],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2
            )
            time.sleep(interval)
        except subprocess.TimeoutExpired:
            pass
        except Exception as e:
            # If arping fails, try arp command instead
            try:
                subprocess.run(
                    ['arp', '-s', gateway_ip, '00:00:00:00:00:00'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=2
                )
                time.sleep(interval)
            except Exception:
                time.sleep(interval)

def run_live_dashboard(station_name, target_ip, gateway_ip=None):
    """
    Run live ICMP telemetry dashboard with ARP updates.
    
    Args:
        station_name: Name of the station
        target_ip: IP address to ping
        gateway_ip: Gateway IP for ARP updates (defaults to target_ip if not provided)
    """
    if gateway_ip is None:
        gateway_ip = target_ip
    
    # Start ARP background thread
    arp_thread = threading.Thread(
        target=run_gratuitous_arp,
        args=(gateway_ip, 2),  # Send ARP every 2 seconds
        daemon=True
    )
    arp_thread.start()
    
    # -O: Reports outstanding (dropped) packets immediately
    # -i 0.5: 2 pings per second
    cmd = ['ping', '-O', '-i', '1', target_ip]
    
    # Use bufsize=1 for line-buffered output to process results instantly
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )
    
    sent = 0
    received = 0
    latest_rtt = "N/A"
    status = "INITIALIZING..."
    arp_status = "RUNNING"
    
    # Clear screen initially
    sys.stdout.write('\033[2J\033[H')
    
    try:
        for line in process.stdout:
            line = line.strip()
            # Track the highest sequence number to know exactly how many were sent
            seq_match = re.search(r'icmp_seq=(\d+)', line)
            if seq_match:
                seq = int(seq_match.group(1))
                sent = max(sent, seq)
            
            # Logic for a successful reply
            if "bytes from" in line:
                received += 1
                status = "CONNECTED "
                rtt_match = re.search(r'time=([\d.]+)\s*ms', line)
                if rtt_match:
                    latest_rtt = rtt_match.group(1) + " ms"
            
            # Logic for a dropped packet (triggered by the -O flag)
            elif "no answer yet" in line:
                status = "LOSS SPYKE "
                latest_rtt = "DROPPED "
            
            # Logic for routing failures
            elif "Unreachable" in line or "timeout" in line.lower():
                status = "UNREACHABLE"
                latest_rtt = "FAIL    "
            
            # Calculate live percentages
            lost = sent - received
            success_rate = (received / sent * 100) if sent > 0 else 0.0
            loss_rate = (lost / sent * 100) if sent > 0 else 0.0
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            
            # \033[H moves the cursor to the top-left corner without flickering the screen
            # \033[J clears everything below the cursor
            dashboard = f"""\033[H\033[J
====================================================
  LIVE ICMP TELEMETRY: {station_name.upper()} -> {target_ip}
====================================================
  Time:          {timestamp}
  Link Status:   {status}
  Latest RTT:    {latest_rtt}
  ARP Status:    {arp_status} (gateway: {gateway_ip})
----------------------------------------------------
  Packets Sent:     {sent}
  Packets Received: {received}
  Packets Lost:     {lost}
  Success Rate:     {success_rate:.1f}%
  Loss Rate:        {loss_rate:.1f}%
====================================================
"""
            sys.stdout.write(dashboard)
            sys.stdout.flush()
    
    except KeyboardInterrupt:
        sys.stdout.write("\nDashboard terminated by user.\n")
        process.terminate()

def main():
    if len(sys.argv) < 3:
        print("Usage: python icmp_test.py <station_name> <target_ip> [gateway_ip]")
        print()
        print("  station_name: Name of the station (e.g., sta1, sta2)")
        print("  target_ip:    IP address to ping (e.g., 10.0.0.2)")
        print("  gateway_ip:   Optional - IP for gratuitous ARP (defaults to target_ip)")
        sys.exit(1)
    
    station_name = sys.argv[1].lower()
    target_ip = sys.argv[2]
    gateway_ip = sys.argv[3] if len(sys.argv) > 3 else None
    
    run_live_dashboard(station_name, target_ip, gateway_ip)

if __name__ == '__main__':
    main()