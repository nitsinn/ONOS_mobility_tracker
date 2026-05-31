# ONOS ID/Locator Host Tracking System

An ONOS application that implements ID/Locator separation for seamless wireless host mobility using MPLS label switching. When a station roams between access points, the controller detects the movement, tears down stale MPLS paths, and installs new ones.

---

## Repository Structure

```
ONOS_mobility_tracker-main/
├── docker-compose.yml                  # ONOS 2.7.0 controller (Docker)
├── onos_apps/
│   └── id-locator-tracker/
│       ├── pom.xml                     # Maven build (ONOS 2.7.0, Java 11)
│       └── src/main/java/org/student/idlocatortracker/
│           ├── AppComponent.java
│           ├── flowlogic/
│           │   ├── FlowManagerService.java
│           │   └── FlowInstallerService.java
│           └── hosttracking/
│               ├── HostLocationManager.java
│               └── HostLocationService.java
└── mn-vm/                              # Mininet-WiFi test scripts (run on separate VM/host)
    ├── icmp_test.py                    # Live ICMP telemetry dashboard
    ├── topo_6_8_replay_mobility.py     # 6 APs + 8 core switches, replay mobility
    ├── topo_6_4_replay_mobility.py     # 6 APs + 4 core switches, replay mobility
    ├── topo_6_12_replay_mobility.py    # 6 APs + 12 core switches, replay mobility
    ├── topo1_random_walk.py            # Random waypoint mobility
    └── replayingMobility/
        ├── node1.dat                   # Mobility trace for sta1
        └── node2.dat                   # Mobility trace for sta2
```

---

## Part 1 — ONOS Controller Setup

### Docker (recommended, no build required)

You need Docker and Docker Compose installed.

```bash
# From the repository root
docker compose up -d
```

Wait until ONOS is healthy (roughly 60–90 seconds):

```bash
docker compose ps
# "onos" should show status: healthy
```

Verify the GUI is up:

```
http://localhost:8181/onos/ui
# Default credentials: onos / rocks
```

> **Note:** The `docker-compose.yml` uses the pre-built `onosproject/onos:2.7.0` image for
> `linux/amd64`. On Apple Silicon (M1/M2/M3) the `platform: linux/amd64` line forces emulation
> via Rosetta — this works but is slower. If performance is a concern, build ONOS natively for
> ARM or run it on an x86 machine.


## Part 2 — Build the ONOS Application (.oar)

### Prerequisites

| Tool    | Required version |
|---------|-----------------|
| Java    | 11 (exact — set by `.java-version`) |
| Maven   | 3.6 or later |

On Ubuntu/Debian:

```bash
sudo apt update
sudo apt install -y openjdk-11-jdk maven
java -version   # must show openjdk 11
```

### Build

```bash
cd onos_apps/id-locator-tracker
mvn clean package -DskipTests
```

The `.oar` file is produced at:

```
onos_apps/id-locator-tracker/target/id-locator-tracker-1.0-SNAPSHOT.oar
```

---

## Part 3 — Deploy the App to ONOS

### 3.1 — Activate required default apps

SSH into the ONOS CLI (password: `karaf`):

```bash
ssh -p 8101 karaf@localhost
```

> If ONOS is running on a remote host, replace `localhost` with its IP.

Activate the full required stack:

```
onos> app activate org.onosproject.drivers
onos> app activate org.onosproject.openflow-base
onos> app activate org.onosproject.openflow
onos> app activate org.onosproject.lldpprovider
onos> app activate org.onosproject.hostprovider
onos> app activate org.onosproject.proxyarp
onos> app activate org.onosproject.gui2
```

### 3.2 — Deactivate the default forwarding app

The ID/Locator tracker **replaces** `fwd`. They must not run together:

```
onos> app deactivate org.onosproject.fwd
```

Confirm it is gone:

```
onos> apps -a -s
# org.onosproject.fwd must NOT appear in the list
```

### 3.3 — Install the .oar file

Use the ONOS REST API to upload the built archive. Replace `localhost` with your ONOS
host IP if needed:

```bash
curl -X POST \
  -u onos:rocks \
  -H "Content-Type: application/octet-stream" \
  --data-binary @onos_apps/id-locator-tracker/target/id-locator-tracker-1.0-SNAPSHOT.oar \
  "http://localhost:8181/onos/v1/applications?activate=false"
```

### 3.4 — Activate the ID/Locator tracker

```bash
curl -X POST \
  -u onos:rocks \
  "http://localhost:8181/onos/v1/applications/org.id-locator-tracker.app/active"
```

Or from the ONOS CLI:

```
onos> app activate org.id-locator-tracker.app
```

### 3.5 — Verify everything is running

```
onos> apps -a -s
```

Expected active apps (minimum):

```
org.onosproject.drivers
org.onosproject.openflow-base
org.onosproject.openflow
org.onosproject.lldpprovider
org.onosproject.hostprovider
org.onosproject.proxyarp
org.onosproject.gui2
org.id-locator-tracker.app       <-- the app
```

`org.onosproject.fwd` must **not** appear.

---

## Part 4 — Mininet-WiFi VM Setup

The test scripts in `mn-vm/` must run on a **Linux machine or VM** — not inside
the ONOS Docker container. This could be for example a dedicated Ubuntu VM.

### 4.1 — OS requirement

> ⚠️ **Mininet-WiFi does not work on the latest Ubuntu releases (22.04+).**  
> Use **Ubuntu 20.04 LTS**

### 4.2 — Install Mininet-WiFi

Follow the official instructions at:  
**https://github.com/intrig-unicamp/mininet-wifi**

The short version:

```bash
git clone https://github.com/intrig-unicamp/mininet-wifi
cd mininet-wifi
sudo util/install.sh -Wlnfv
```

> The `-W` flag installs wireless extensions, `-l` installs wmediumd (the wireless medium
> emulator), `-n` installs Mininet, `-f` installs OpenFlow tools, and `-v` installs OVS.
> This takes 10–20 minutes on a clean system.

### 4.3 — Enable OVS and wireless kernel modules

After installation, enable Open vSwitch and load the virtual WiFi kernel module:

```bash
# Start and enable OVS
sudo systemctl start openvswitch-switch
sudo systemctl enable openvswitch-switch

# Load the mac80211_hwsim module (virtual WiFi interfaces for mininet-wifi)
sudo modprobe mac80211_hwsim

# Verify OVS is running
sudo ovs-vsctl show
```

### 4.4 — Copy the mn-vm directory to the VM

```bash
scp -r mn-vm/ user@<mininet-vm-ip>:~/
```

Or clone the whole repository on the VM and work from the `mn-vm/` folder.

---

## Part 5 — Configure the Controller IP

All topology scripts have the ONOS controller IP **hardcoded** to `192.168.64.1`.  
You must change this to match your actual ONOS host IP before running any test.

Find and replace in every topology file:

```bash
cd mn-vm/

# Check what is currently set
grep -n "192.168.64.1" *.py

# Replace with your controller IP (example: 10.0.1.5)
sed -i 's/192\.168\.64\.1/<YOUR_ONOS_IP>/g' \
    topo_6_8_replay_mobility.py \
    topo_6_4_replay_mobility.py \
    topo_6_12_replay_mobility.py \
    topo1_random_walk.py \
    test_parametized_topology.py
```

Verify the change:

```bash
grep "ip=" topo_6_8_replay_mobility.py
# Should show your IP, e.g.: ip='10.0.1.5', port=6653
```

> **How to find your ONOS IP:**  
> - If ONOS runs in Docker on the same machine, use the Docker host IP (e.g. `172.17.0.1` or  
>   the host's LAN IP — not `127.0.0.1`, as mininet runs in its own network namespace).  
> - Run `ip addr` on the ONOS host and use the IP of the interface reachable from the Mininet VM.  
> - Confirm connectivity: `ping <ONOS_IP>` and `nc -zv <ONOS_IP> 6653` from the Mininet VM.

---

## Part 6 — Run the Tests

All topology scripts must be run with `sudo` because they create kernel-level network
namespaces and virtual wireless interfaces.

```bash
cd mn-vm/
```

### Replay mobility — 6 APs, 8 core switches (main test)

```bash
sudo python topo_6_8_replay_mobility.py
```

Stations follow pre-recorded mobility traces from `replayingMobility/`. Two xterm windows
open automatically showing live ICMP telemetry for `sta1` and `sta2`.

### Other fixed topologies

```bash
sudo python topo_6_4_replay_mobility.py    # 6 APs, 4 core switches
sudo python topo_6_12_replay_mobility.py   # 6 APs, 12 core switches
sudo python topo1_random_walk.py           # Random waypoint mobility
```

### ICMP telemetry dashboard (standalone)

If you want to run the dashboard manually against any target (when using miniedit for example):

```bash
python icmp_test.py <station_name> <target_ip>
# Example:
python icmp_test.py sta1 10.0.0.2
```

### Clean up between runs

If a previous run crashed or was interrupted, clean up stale Mininet state before
starting again:

```bash
sudo mn -c
```

---

## Troubleshooting

**OVS bridges not connecting to ONOS (`is_connected` missing from `ovs-vsctl show`)**  
→ Confirm ONOS is listening: `nc -zv <ONOS_IP> 6653`  
→ Confirm the `openflow` app is active in ONOS: `apps -a -s`  
→ Confirm `fwd` is deactivated  

**`HOST_MOVED` events not firing / stations not detected after handoff**  
→ Ensure `hostprovider` and `proxyarp` are active  
→ ARP traffic is required alongside ICMP — the topology scripts handle this automatically  

**`mac80211_hwsim: No such file or directory`**  
→ Run `sudo modprobe mac80211_hwsim`  

**Mininet install fails on Ubuntu 22.04+**  
→ Use Ubuntu 20.04. This is a kernel/wireless driver compatibility issue with newer kernels.  

**`flow rules stuck in PENDING_ADD`**  
→ Run `sudo ovs-vsctl show` — check that every bridge shows `is_connected: true`  
→ If not, check for stale OVS state: `sudo mn -c` then restart the topology  

**Duplicate rule installation warnings in ONOS log**  
→ This is a known race condition when multiple Packet-In events arrive before FlowMod
   installation completes. It is idempotent and does not affect correctness.
