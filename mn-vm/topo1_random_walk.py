#!/usr/bin/env python
'2 Stations, 3 APs with seamless mobility (bgscan + IEEE 802.11r) connected to core network'
import sys
import random
from mininet.log import setLogLevel, info
from mn_wifi.cli import CLI
from mn_wifi.net import Mininet_wifi
from mn_wifi.node import OVSKernelAP
from mn_wifi.link import wmediumd
from mn_wifi.wmediumdConnector import interference
from mininet.node import RemoteController, OVSKernelSwitch


def topology(args):
    "Create a network."
    net = Mininet_wifi(topo=None,
                       build=False,
                       link=wmediumd,
                       wmediumd_mode=interference,
                       ipBase='10.0.0.0/8')
    
    net.setMobilityModel(time=0, model='RandomWayPoint', seed=20, ac_method='ssf')
    
    info("*** Creating wireless nodes\n")
    sta1 = net.addStation('sta1', range=40, maxy=160, min_v=1, max_v=1, min_wt=10, max_wt=10, constantDistance=100)
    sta2 = net.addStation('sta2', range=40, max_x=160, maxy=160, min_v=1, max_v=1, min_wt=10, max_wt=10, constantDistance=100)
    
    info("*** Creating access points\n")
    ap1 = net.addAccessPoint('ap1', cls=OVSKernelAP, ssid='ssid-ap1', mode='g',
                             position='30,60,0', protocols='OpenFlow13', range=40)
    ap2 = net.addAccessPoint('ap2', cls=OVSKernelAP, ssid='ssid-ap1', mode='g',
                             position='100,60,0', protocols='OpenFlow13', range=40)
    ap3 = net.addAccessPoint('ap3', cls=OVSKernelAP, ssid='ssid-ap1', mode='g',
                             position='170,60,0', protocols='OpenFlow13', range=40)
    ap4 = net.addAccessPoint('ap4', cls=OVSKernelAP, ssid='ssid-ap1', mode='g',
                             position='30,150,0', protocols='OpenFlow13', range=40)
    ap5 = net.addAccessPoint('ap5', cls=OVSKernelAP, ssid='ssid-ap1', mode='g',
                             position='170,150,0', protocols='OpenFlow13', range=40)
    ap6 = net.addAccessPoint('ap6', cls=OVSKernelAP, ssid='ssid-ap1', mode='g',
                             position='100,150,0', protocols='OpenFlow13', range=40)
    
    info("*** Creating core network (5 switches)\n")
    # Create core network of 5 switches
    core1 = net.addSwitch('core1', cls=OVSKernelSwitch, stp=True, protocols='OpenFlow13')
    core2 = net.addSwitch('core2', cls=OVSKernelSwitch, stp=True, protocols='OpenFlow13')
    core3 = net.addSwitch('core3', cls=OVSKernelSwitch, stp=True, protocols='OpenFlow13')
    core4 = net.addSwitch('core4', cls=OVSKernelSwitch, stp=True, protocols='OpenFlow13')
    core5 = net.addSwitch('core5', cls=OVSKernelSwitch, stp=True, protocols='OpenFlow13')
    core6 = net.addSwitch('core6', cls=OVSKernelSwitch, stp=True, protocols='OpenFlow13')
    core7 = net.addSwitch('core7', cls=OVSKernelSwitch, stp=True, protocols='OpenFlow13')
    core8 = net.addSwitch('core8', cls=OVSKernelSwitch, stp=True, protocols='OpenFlow13')
    
    
    # Create random connections between core switches
    info("*** Creating partially random connections between core switches\n")
    core_switches = [core1, core2, core3, core4, core5, core6, core7, core8]
    
    # Ensure connectivity by creating a minimum spanning tree first
    net.addLink(core1, core2)
    net.addLink(core1, core3)
    net.addLink(core2, core4)
    net.addLink(core3, core5)
    net.addLink(core5, core6)
    net.addLink(core6, core7)
    net.addLink(core7, core8)

    # Add some random additional links for redundancy
    # net.addLink(core4, core5)
    # net.addLink(core2, core8) 
    
    c1 = net.addController('c1', controller=RemoteController, ip='192.168.64.1', port=6653)
    
    info("*** Setting OpenFlow version to 1.3\n")
    net.openFlowVersion = '1.3'
    
    info("*** Configuring propagation model\n")
    net.setPropagationModel(model="logDistance", exp=3)
    
    info("*** Configuring nodes\n")
    net.configureNodes()
    
    info("*** Associating and Creating links\n")
    # Connect APs to core network (randomly select which core switch)
    net.addLink(ap1, core1)
    net.addLink(ap2, core2)
    net.addLink(ap3, core3)
    net.addLink(ap4, core4)
    net.addLink(ap5, core5)
    net.addLink(ap6, core6)

    if '-p' not in args:
        net.plotGraph(max_x=200, max_y=200, min_y=25)
    
    info("*** Starting network\n")
    net.build()
    c1.start()
    for _ in range(len(core_switches)):
        core_switches[_].start([c1])
    ap1.start([c1])
    ap2.start([c1])
    ap3.start([c1])
    ap4.start([c1])
    ap5.start([c1])
    ap6.start([c1])
    
    info("*** Launching Live ICMP Dashboards...\n")
    # Launch xterm windows natively assigned to the stations' virtual interfaces.
    # The -e flag tells xterm to execute our custom dashboard immediately upon opening.
    # The -geometry flag ensures the windows spawn neatly side-by-side.
    
    # With automatic gateway detection (uses target IP)
    sta1.cmd('xterm -T "STA1 Live Telemetry" -geometry 55x20+0+0 -e "python icmp_test.py sta1 10.0.0.2" &')
    sta2.cmd('xterm -T "STA2 Live Telemetry" -geometry 55x20+600+0 -e "python icmp_test.py sta2 10.0.0.1" &')

    
    CLI(net)
    
    info("*** Stopping network\n")
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    topology(sys.argv)