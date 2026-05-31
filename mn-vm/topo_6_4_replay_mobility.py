#!/usr/bin/env python
'2 Stations, 6 APs with seamless mobility connected to core network via ONOS'
import os
import sys
from time import sleep                          # FIX 5: correct import
from mininet.log import setLogLevel, info
from mn_wifi.cli import CLI
from mn_wifi.net import Mininet_wifi
from mn_wifi.node import OVSKernelAP
from mn_wifi.link import wmediumd
from mn_wifi.replaying import ReplayingMobility
from mn_wifi.wmediumdConnector import interference
from mininet.node import RemoteController, OVSKernelSwitch


def topology(args):
    "Create a network."
    net = Mininet_wifi(topo=None,
                       build=False,
                       link=wmediumd,
                       wmediumd_mode=interference,
                       ipBase='10.0.0.0/8')

    info("*** Creating wireless nodes\n")
    sta1 = net.addStation('sta1', speed=3, range=1)
    sta2 = net.addStation('sta2', speed=3, range=1)

    info("*** Creating access points\n")
    # FIX 1: failMode='secure' forces OVS to connect to the controller
    # FIX 3: protocols='OpenFlow13' is now enforced because failMode is set
    ap1 = net.addAccessPoint('ap1', cls=OVSKernelAP, ssid='ssid-ap1', mode='g',
                             position='25,60,0', protocols='OpenFlow13',
                             range=38, failMode='secure')
    ap2 = net.addAccessPoint('ap2', cls=OVSKernelAP, ssid='ssid-ap1', mode='g',
                             position='100,60,0', protocols='OpenFlow13',
                             range=38, failMode='secure')
    ap3 = net.addAccessPoint('ap3', cls=OVSKernelAP, ssid='ssid-ap1', mode='g',
                             position='175,60,0', protocols='OpenFlow13',
                             range=38, failMode='secure')
    ap4 = net.addAccessPoint('ap4', cls=OVSKernelAP, ssid='ssid-ap1', mode='g',
                             position='25,150,0', protocols='OpenFlow13',
                             range=38, failMode='secure')
    ap5 = net.addAccessPoint('ap5', cls=OVSKernelAP, ssid='ssid-ap1', mode='g',
                             position='175,150,0', protocols='OpenFlow13',
                             range=38, failMode='secure')
    ap6 = net.addAccessPoint('ap6', cls=OVSKernelAP, ssid='ssid-ap1', mode='g',
                             position='100,150,0', protocols='OpenFlow13',
                             range=38, failMode='secure')

    info("*** Creating core network (4 switches)\n")
    # FIX 6: removed stp=True — let ONOS manage topology, not OVS STP
    core1 = net.addSwitch('core1', cls=OVSKernelSwitch, protocols='OpenFlow13', failMode='secure')
    core2 = net.addSwitch('core2', cls=OVSKernelSwitch, protocols='OpenFlow13', failMode='secure')
    core3 = net.addSwitch('core3', cls=OVSKernelSwitch, protocols='OpenFlow13', failMode='secure')
    core4 = net.addSwitch('core4', cls=OVSKernelSwitch, protocols='OpenFlow13', failMode='secure')

    core_switches = [core1, core2, core3, core4]

    info("*** Creating core switch links\n")
    net.addLink(core1, core2)
    net.addLink(core2, core3)
    net.addLink(core3, core4)

    c1 = net.addController('c1', controller=RemoteController,
                           ip='192.168.64.1', port=6653)

    info("*** Configuring propagation model\n")
    net.setPropagationModel(model="logDistance", exp=3)

    info("*** Configuring nodes\n")
    net.configureNodes()

    info("*** Adding links\n")
    net.addLink(ap1, core1)
    net.addLink(ap2, core2)
    net.addLink(ap3, core3)
    net.addLink(ap4, core4)


    net.isReplaying = True
    path = os.path.dirname(os.path.abspath(__file__)) + '/replayingMobility/'
    get_trace(sta1, '{}node1.dat'.format(path))
    get_trace(sta2, '{}node2.dat'.format(path))

    if '-p' not in args:
        net.plotGraph(max_x=200, max_y=200, min_y=25)

    info("*** Starting network\n")
    net.build()
    c1.start()
    for sw in core_switches:
        sw.start([c1])
    for ap in [ap1, ap2, ap3, ap4, ap5, ap6]:
        ap.start([c1])

    info("*** Waiting for ONOS to install flows (15s)...\n")
    sleep(15)

    info("*** Launching Live ICMP Dashboards...\n")
    sta1.cmd('xterm -T "STA1 Live Telemetry" -geometry 55x20+0+0 -e "python icmp_test.py sta1 10.0.0.2" &')
    sta2.cmd('xterm -T "STA2 Live Telemetry" -geometry 55x20+600+0 -e "python icmp_test.py sta2 10.0.0.1" &')

    ReplayingMobility(net)

    CLI(net)

    info("*** Stopping network\n")
    net.stop()


def get_trace(sta, file_):
    file_ = open(file_, 'r')
    raw_data = file_.readlines()
    file_.close()

    sta.p = []
    pos = (-1000, 0, 0)
    sta.position = pos

    for data in raw_data:
        line = data.split()
        x = line[0]
        y = line[1]
        pos = float(x), float(y), 0.0
        sta.p.append(pos)


if __name__ == '__main__':
    setLogLevel('info')
    topology(sys.argv)