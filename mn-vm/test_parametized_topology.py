#!/usr/bin/env python
"""
Parametized Test Framework for Mininet-WiFi
Tests 3 levels of core switches x 3 levels of edge switches x 3 levels of hosts
Measures ICMP transition times and packet loss during mobility
"""

import os
import sys
import csv
import time
import subprocess
import re
from datetime import datetime
from threading import Thread
import tempfile


class TopologyConfig:
    """Configuration for a test scenario"""
    def __init__(self, core_level, edge_level, host_level):
        self.core_level = core_level
        self.edge_level = edge_level
        self.host_level = host_level
        
        # Core switch configuration (L0: sparse, L1: medium, L2: dense)
        self.core_configs = {
            0: {'count': 2, 'name': 'sparse'},
            1: {'count': 4, 'name': 'medium'},
            2: {'count': 6, 'name': 'dense'}
        }
        
        # Edge switch configuration (L0: 4, L1: 6, L2: 10)
        self.edge_counts = {
            0: 4,
            1: 6,
            2: 10
        }
        
        # Host configuration (L0: 2 hosts, L1: 4 hosts, L2: 6 hosts)
        self.host_counts = {
            0: 2,
            1: 4,
            2: 6
        }
    
    @property
    def num_core_switches(self):
        return self.core_configs[self.core_level]['count']
    
    @property
    def num_edge_switches(self):
        return self.edge_counts[self.edge_level]
    
    @property
    def num_hosts(self):
        return self.host_counts[self.host_level]
    
    def __str__(self):
        return f"C{self.core_level}E{self.edge_level}H{self.host_level}"


class TestRunner:
    """Executes parametized tests and collects metrics"""
    
    def __init__(self):
        self.results = []
        self.mobility_data_dir = os.path.dirname(os.path.abspath(__file__)) + '/replayingMobility/'
    
    def generate_topology_code(self, config):
        """Generate Python code for a specific topology configuration"""
        num_hosts = config.num_hosts
        num_edge_switches = config.num_edge_switches
        num_core_switches = config.num_core_switches
        core_level = config.core_level
        edge_level = config.edge_level
        host_level = config.host_level
        
        code = f'''#!/usr/bin/env python3
"""Parametized Topology: Core={core_level}, Edge={edge_level}, Hosts={host_level}"""

import os
import sys
import time
import subprocess
import json
import re
from mininet.log import setLogLevel, info
from mininet.node import RemoteController, OVSKernelSwitch
from mn_wifi.net import Mininet_wifi
from mn_wifi.node import OVSKernelAP
from mn_wifi.link import wmediumd
from mn_wifi.wmediumdConnector import interference
from mn_wifi.replaying import ReplayingMobility


def get_trace(sta, file_):
    """Load mobility trace from file"""
    try:
        with open(file_, 'r') as f:
            raw_data = f.readlines()
    except IOError:
        print(f"Warning: Could not load trace file {{file_}}")
        return
    
    sta.p = []
    pos = (-1000, 0, 0)
    sta.position = pos
    
    for data in raw_data:
        line = data.split()
        if len(line) < 2:
            continue
        try:
            x = float(line[0])
            y = float(line[1])
            pos = (x, y, 0.0)
            sta.p.append(pos)
        except (ValueError, IndexError):
            continue


def collect_metrics(stations, duration=30):
    """Run pings between stations and collect ICMP metrics"""
    metrics = {{'stations': {{}}}}
    
    for i, sta in enumerate(stations):
        target_ip = '10.0.0.' + str(((i + 1) % len(stations)) + 1)
        
        info(f"*** {{sta.name}} pinging {{target_ip}} for {{duration}}s\\n")
        
        # Run ping
        cmd = f'ping -c {{duration}} {{target_ip}}'
        try:
            output = sta.cmd(cmd)
            
            # Parse loss percentage
            loss_match = re.search(r'(\\d+(?:\\.\\d+)?)% packet loss', output)
            loss_pct = float(loss_match.group(1)) if loss_match else 0.0
            
            # Parse RTT stats: min/avg/max/stddev
            rtt_match = re.search(r'min = ([\\d.]+), avg = ([\\d.]+), max = ([\\d.]+), stddev = ([\\d.]+)', output)
            if rtt_match:
                metrics['stations'][sta.name] = {{
                    'loss_pct': loss_pct,
                    'min_rtt': float(rtt_match.group(1)),
                    'avg_rtt': float(rtt_match.group(2)),
                    'max_rtt': float(rtt_match.group(3)),
                    'stddev_rtt': float(rtt_match.group(4))
                }}
            else:
                metrics['stations'][sta.name] = {{'loss_pct': loss_pct}}
            
            info(f"  {{sta.name}}: {{loss_pct}}% loss\\n")
        except Exception as e:
            info(f"Error on {{sta.name}}: {{e}}\\n")
            metrics['stations'][sta.name] = {{'error': str(e)}}
    
    return metrics


def run_continuous_ping(sta, target_ip, duration=30, interval=1):
    """Run continuous ping and log results in real-time"""
    import time
    start = time.time()
    results = {{'packets_sent': 0, 'packets_received': 0, 'min_rtt': float('inf'), 
                'max_rtt': 0, 'total_rtt': 0, 'losses': []}}
    
    while time.time() - start < duration:
        try:
            output = sta.cmd(f'ping -c 1 {{target_ip}}')
            results['packets_sent'] += 1
            
            # Check if packet was received
            if '1 received' in output:
                results['packets_received'] += 1
                rtt_match = re.search(r'time=([\\d.]+) ms', output)
                if rtt_match:
                    rtt = float(rtt_match.group(1))
                    results['min_rtt'] = min(results['min_rtt'], rtt)
                    results['max_rtt'] = max(results['max_rtt'], rtt)
                    results['total_rtt'] += rtt
            else:
                results['losses'].append(time.time() - start)
            
            time.sleep(interval)
        except Exception as e:
            info(f"Ping error: {{e}}\\n")
            break
    
    return results


def run_gratuitous_arp(sta, interval=2, duration=30):
    """Send gratuitous ARP to advertise station location"""
    import time
    import subprocess
    start = time.time()
    
    while time.time() - start < duration:
        try:
            sta.cmd('arping -c 1 {{sta.IP().split("/")[0]}}')
            time.sleep(interval)
        except:
            pass


def topology(args):
    """Create a {num_core_switches}-core, {num_edge_switches}-edge, {num_hosts}-host topology"""
    
    net = Mininet_wifi(topo=None, build=False, link=wmediumd,
                       wmediumd_mode=interference, ipBase='10.0.0.0/8')
    
    info("*** Creating {{{{num_hosts}}}} wireless stations\\n")
    stations = []
    for i in range({num_hosts}):
        sta = net.addStation(f'sta{{i+1}}', mac=f'00:00:00:00:00:{{i+2:02x}}',
                            ip=f'10.0.0.{{i+1}}/8', speed=4)
        stations.append(sta)
    
    info("*** Creating {{{{num_edge_switches}}}} edge access points\\n")
    edge_aps = []
    for i in range({num_edge_switches}):
        x_pos = 20 + (i % 3) * 80
        y_pos = 60 + (i // 3) * 80
        ap = net.addAccessPoint(f'ap{{i+1}}', cls=OVSKernelAP, 
                               ssid='ssid-edge', mode='g',
                               position=f'{{x_pos}},{{y_pos}},0',
                               protocols='OpenFlow13', range=40)
        edge_aps.append(ap)
    
    info("*** Creating {{{{num_core_switches}}}} core switches\\n")
    core_switches = []
    for i in range({num_core_switches}):
        sw = net.addSwitch(f'core{{i+1}}', cls=OVSKernelSwitch, 
                          stp=True, protocols='OpenFlow13')
        core_switches.append(sw)
    
    info("*** Connecting core switches (chain topology)\\n")
    for i in range(len(core_switches) - 1):
        net.addLink(core_switches[i], core_switches[i+1])
    
    info("*** Connecting edge APs to core (round-robin)\\n")
    for i, ap in enumerate(edge_aps):
        core_idx = i % len(core_switches)
        net.addLink(ap, core_switches[core_idx])
    
    c1 = net.addController('c1', controller=RemoteController, 
                          ip='192.168.64.1', port=6653)
    
    net.setPropagationModel(model="logDistance", exp=3)
    net.configureNodes()
    
    info("*** Loading mobility traces\\n")
    mobility_dir = os.path.dirname(os.path.abspath(__file__)) + '/replayingMobility/'
    net.isReplaying = True
    available_traces = ['node1.dat', 'node2.dat']
    for i, sta in enumerate(stations):
        trace_file = available_traces[i % len(available_traces)]
        get_trace(sta, mobility_dir + trace_file)
    
    if '-p' not in args:
        net.plotGraph(max_x=400, max_y=400)
    
    info("*** Starting network\\n")
    net.build()
    c1.start()
    for sw in core_switches:
        sw.start([c1])
    for ap in edge_aps:
        ap.start([c1])
    
    info("*** Waiting for network stabilization (5s)\\n")
    time.sleep(5)
    
    info("*** Starting mobility replay (30s)\\n")
    ReplayingMobility(net)
    
    info("*** Starting continuous ping + ARP during mobility (30s)\\n")
    from threading import Thread
    
    # Start ARP broadcasts and pings for each station
    ping_threads = []
    arp_threads = []
    all_metrics = {{}}
    
    for i, sta in enumerate(stations):
        target_ip = '10.0.0.' + str(((i + 1) % len(stations)) + 1)
        
        # Ping thread
        ping_thread = Thread(target=lambda s=sta, t=target_ip: 
                            all_metrics.update({{s.name: run_continuous_ping(s, t, 30, 1)}}))
        ping_thread.daemon = True
        ping_thread.start()
        ping_threads.append(ping_thread)
        
        # ARP thread
        arp_thread = Thread(target=run_gratuitous_arp, args=(sta, 2, 30))
        arp_thread.daemon = True
        arp_thread.start()
        arp_threads.append(arp_thread)
        
        info(f"*** {{sta.name}} -> {{target_ip}}: ping + ARP started\\n")
    
    # Wait for all pings to complete
    for t in ping_threads:
        t.join(timeout=35)
    for t in arp_threads:
        t.join(timeout=35)
    
    info("*** Collecting final metrics\\n")
    metrics = {{'stations': all_metrics}}
    
    # Print live results
    print("\\n" + "="*70)
    print("ICMP METRICS (Live Results)")
    print("="*70)
    for sta_name, data in all_metrics.items():
        if isinstance(data, dict) and 'packets_sent' in data:
            sent = data['packets_sent']
            recv = data['packets_received']
            loss_pct = ((sent - recv) / sent * 100) if sent > 0 else 0.0
            avg_rtt = (data['total_rtt'] / recv) if recv > 0 else 0.0
            max_rtt = data['max_rtt'] if data['max_rtt'] != 0 else 0.0
            print(f"  {{sta_name}}: {{recv}}/{{sent}} packets, {{loss_pct:.1f}}% loss, avg RTT {{avg_rtt:.1f}}ms, max {{max_rtt:.1f}}ms")
    print("="*70 + "\\n")
    
    info("*** Writing results to file\\n")
    with open('/tmp/icmp_metrics.json', 'w') as f:
        json.dump(metrics, f, indent=2)
    
    info("*** Stopping network\\n")
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    topology(sys.argv)
'''
        return code

    def run_single_test(self, config, timeout=120):
        """Execute a single topology test configuration with mobility and ICMP monitoring"""
        print(f"\n{'='*70}")
        print(f"Test: {config} | {config.num_core_switches} core, {config.num_edge_switches} edge, {config.num_hosts} hosts")
        print(f"{'='*70}")
        
        start_time = time.time()
        
        # Generate topology script
        topology_code = self.generate_topology_code(config)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, dir='/tmp') as f:
            f.write(topology_code)
            temp_script = f.name
        
        try:
            # Run test directly with sudo like the original test files
            # Do NOT capture output so we can see what's happening
            result = subprocess.run(
                ['sudo', sys.executable, temp_script, '-p'],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                timeout=timeout
            )
            
            elapsed_time = time.time() - start_time
            
            # Clean up mininet processes
            print("  Cleaning up mininet...")
            subprocess.run(['sudo', 'mn', '-c'], timeout=10)
            time.sleep(2)  # Wait for cleanup to finish
            
            # Try to read metrics from JSON file written by the topology script
            metrics_file = '/tmp/icmp_metrics.json'
            avg_drop_pct = 0.0
            max_rtt = 0.0
            rtt_variance = 0.0
            
            if os.path.exists(metrics_file):
                try:
                    import json
                    with open(metrics_file, 'r') as f:
                        metrics = json.load(f)
                    
                    # Aggregate metrics across all stations
                    if 'stations' in metrics and metrics['stations']:
                        drops = [s.get('loss_pct', 0) for s in metrics['stations'].values()]
                        rtts = [s.get('max_rtt', 0) for s in metrics['stations'].values()]
                        
                        avg_drop_pct = sum(drops) / len(drops) if drops else 0.0
                        max_rtt = max(rtts) if rtts else 0.0
                        
                        # Compute RTT variance as indicator of transitions
                        if rtts:
                            mean_rtt = sum(rtts) / len(rtts)
                            variance = sum((x - mean_rtt) ** 2 for x in rtts) / len(rtts)
                            rtt_variance = variance ** 0.5
                    
                    os.remove(metrics_file)  # Clean up
                except Exception as e:
                    print(f"  Warning: Could not parse metrics: {e}")
            else:
                print(f"  Warning: Metrics file not found (network may have failed to start)")
            
            test_result = {
                'timestamp': datetime.now().isoformat(),
                'config': str(config),
                'core_level': config.core_level,
                'edge_level': config.edge_level,
                'host_level': config.host_level,
                'num_core_switches': config.num_core_switches,
                'num_edge_switches': config.num_edge_switches,
                'num_hosts': config.num_hosts,
                'elapsed_time': elapsed_time,
                'icmp_drop_percentage': avg_drop_pct,
                'max_rtt_ms': max_rtt,
                'rtt_variance_ms': rtt_variance,
                'ap_transitions': 0,
                'status': 'completed' if result.returncode == 0 else 'failed',
                'return_code': result.returncode
            }
            
            self.results.append(test_result)
            
            print(f"  ✓ Elapsed: {elapsed_time:.1f}s | Drop: {avg_drop_pct:.1f}% | RTT var: {rtt_variance:.1f}ms")
            
            return test_result
        
        except subprocess.TimeoutExpired:
            print(f"  ✗ TIMEOUT (>{timeout}s)")
            # Still try to clean up on timeout
            try:
                subprocess.run(['sudo', 'mn', '-c'], timeout=10)
            except:
                pass
            
            elapsed_time = time.time() - start_time
            test_result = {
                'timestamp': datetime.now().isoformat(),
                'config': str(config),
                'core_level': config.core_level,
                'edge_level': config.edge_level,
                'host_level': config.host_level,
                'num_core_switches': config.num_core_switches,
                'num_edge_switches': config.num_edge_switches,
                'num_hosts': config.num_hosts,
                'elapsed_time': elapsed_time,
                'icmp_drop_percentage': -1.0,
                'max_rtt_ms': -1.0,
                'rtt_variance_ms': -1.0,
                'ap_transitions': -1,
                'status': 'timeout',
                'error': f'Test exceeded {timeout}s'
            }
            self.results.append(test_result)
            return test_result
        
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            # Still try to clean up on error
            try:
                subprocess.run(['sudo', 'mn', '-c'], timeout=10)
            except:
                pass
            
            test_result = {
                'timestamp': datetime.now().isoformat(),
                'config': str(config),
                'core_level': config.core_level,
                'edge_level': config.edge_level,
                'host_level': config.host_level,
                'num_core_switches': config.num_core_switches,
                'num_edge_switches': config.num_edge_switches,
                'num_hosts': config.num_hosts,
                'elapsed_time': time.time() - start_time,
                'icmp_drop_percentage': -1.0,
                'max_rtt_ms': -1.0,
                'rtt_variance_ms': -1.0,
                'ap_transitions': -1,
                'status': 'error',
                'error': str(e)
            }
            self.results.append(test_result)
            return test_result
        
        finally:
            try:
                os.unlink(temp_script)
            except:
                pass
    
    def run_all_tests(self):
        """Execute all 27 test combinations (3x3x3)"""
        print("\\n" + "="*70)
        print("PARAMETIZED TOPOLOGY TEST SUITE (3x3x3)")
        print("="*70)
        print(f"Start time: {datetime.now().isoformat()}")
        
        test_count = 0
        for core_level in range(3):
            for edge_level in range(3):
                for host_level in range(3):
                    config = TopologyConfig(core_level, edge_level, host_level)
                    test_count += 1
                    self.run_single_test(config)
        
        print(f"\\nCompleted {test_count} tests at {datetime.now().isoformat()}")
        return self.results
    
    def save_results_csv(self, output_file='test_results.csv'):
        """Save test results to CSV file"""
        if not self.results:
            print("No results to save")
            return
        
        keys = self.results[0].keys()
        
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(self.results)
        
        print(f"\\nResults saved to: {output_file}")
        return output_file
    
    def print_summary(self):
        """Print summary statistics"""
        if not self.results:
            print("No results available")
            return
        
        completed = sum(1 for r in self.results if r.get('status') == 'completed')
        valid_drops = [r.get('icmp_drop_percentage', 0) for r in self.results 
                      if r.get('icmp_drop_percentage', -1) >= 0]
        valid_rtts = [r.get('rtt_variance_ms', 0) for r in self.results 
                     if r.get('rtt_variance_ms', -1) >= 0]
        
        avg_drop = sum(valid_drops) / len(valid_drops) if valid_drops else 0.0
        avg_rtt_var = sum(valid_rtts) / len(valid_rtts) if valid_rtts else 0.0
        avg_time = sum(r.get('elapsed_time', 0) for r in self.results) / len(self.results)
        
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        print(f"Total tests: {len(self.results)}")
        print(f"Completed: {completed}")
        print(f"Failed: {len(self.results) - completed}")
        print(f"Average ICMP drop rate: {avg_drop:.2f}%")
        print(f"Average RTT variance (transition indicator): {avg_rtt_var:.2f}ms")
        print(f"Average elapsed time: {avg_time:.2f}s")
        print("="*70)


def main():
    """Main entry point"""
    runner = TestRunner()
    
    # Run all 27 test combinations
    results = runner.run_all_tests()
    
    # Print summary
    runner.print_summary()
    
    # Save results to CSV
    output_dir = os.path.dirname(os.path.abspath(__file__))
    csv_file = os.path.join(output_dir, f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    runner.save_results_csv(csv_file)


if __name__ == '__main__':
    main()
