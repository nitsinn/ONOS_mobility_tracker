package org.student.idlocatortracker.flowlogic;

import org.onlab.packet.Ethernet;
import org.onlab.packet.MacAddress;
import org.onlab.packet.MplsLabel;
import org.onosproject.core.ApplicationId;
import org.onosproject.core.CoreService;
import org.onosproject.net.DeviceId;
import org.onosproject.net.HostId;
import org.onosproject.net.Link;
import org.onosproject.net.Path;
import org.onosproject.net.PortNumber;
import org.onosproject.net.device.DeviceService;
import org.onosproject.net.flow.DefaultTrafficSelector;
import org.onosproject.net.flow.FlowRuleService;
import org.onosproject.net.flow.TrafficSelector;
import org.onosproject.net.flow.criteria.Criterion;
import org.onosproject.net.flow.criteria.EthCriterion;
import org.onosproject.net.packet.PacketContext;
import org.onosproject.net.packet.PacketPriority;
import org.onosproject.net.packet.PacketProcessor;
import org.onosproject.net.packet.PacketService;
import org.onosproject.net.topology.PathService;
import org.onosproject.net.topology.TopologyService;
import org.osgi.service.component.annotations.Activate;
import org.osgi.service.component.annotations.Component;
import org.osgi.service.component.annotations.Deactivate;
import org.osgi.service.component.annotations.Reference;
import org.osgi.service.component.annotations.ReferenceCardinality;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.student.idlocatortracker.hosttracking.HostLocationManager;
import org.student.idlocatortracker.hosttracking.HostLocationService;

import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.atomic.AtomicInteger;



@Component(immediate = true, service = FlowManagerService.class)
public class FlowManagerService {

    private final Logger log = LoggerFactory.getLogger(getClass());

    @Reference(cardinality = ReferenceCardinality.MANDATORY)
    protected CoreService coreService;

    @Reference(cardinality = ReferenceCardinality.MANDATORY)
    protected PacketService packetService;

    @Reference(cardinality = ReferenceCardinality.MANDATORY)
    protected FlowInstallerService flowInstaller;

    @Reference(cardinality = ReferenceCardinality.MANDATORY)
    protected HostLocationService hostLocationService;

    @Reference(cardinality = ReferenceCardinality.MANDATORY)
    protected TopologyService topologyService;

    @Reference(cardinality = ReferenceCardinality.MANDATORY)
    protected PathService pathService;

    @Reference(cardinality = ReferenceCardinality.MANDATORY)
    protected DeviceService deviceService;

    @Reference(cardinality = ReferenceCardinality.MANDATORY)
    protected FlowRuleService flowRuleService;

    private final PacketProcessor processor = new ReactiveProcessor();
    private ApplicationId appId;
    private TrafficSelector ipv4Selector;

    // Thread-safe label allocation
    private final AtomicInteger labelAllocator = new AtomicInteger(0);
    private final ConcurrentMap<DeviceId, Integer> deviceLabels = new ConcurrentHashMap<>();

    @Activate
    protected void activate() {
        appId = coreService.registerApplication("org.student.idlocatortracker");
        packetService.addProcessor(processor, PacketProcessor.director(2));

        ipv4Selector = DefaultTrafficSelector.builder()
            .matchEthType(Ethernet.TYPE_IPV4)
            .build();
        packetService.requestPackets(ipv4Selector, PacketPriority.REACTIVE, appId);

        // Register callback with HostLocationManager
        if (hostLocationService instanceof HostLocationManager) {
            HostLocationManager manager = (HostLocationManager) hostLocationService;

            manager.registerHostMovementCallback((hostId, mac, oldLoc, newLoc) -> {
                log.info("🔄 [CALLBACK] Host movement detected: {} moved from {} to {}",
                    mac,
                    oldLoc != null ? oldLoc.deviceId() : "unknown",
                    newLoc.deviceId());

                // At this point, hostTable is GUARANTEED to be updated
                // because this callback is invoked AFTER recordHostLocation()
                removeStaleRules(mac, oldLoc != null ? oldLoc.deviceId() : null, newLoc.deviceId());
            });

            log.info("✅ FlowManagerService registered with HostLocationManager callbacks");
        } else {
            log.warn("⚠️  HostLocationService is not an instance of HostLocationManager!");
            log.warn("   Host movement callbacks will not work properly");
        }

        log.info("FlowManagerService activated.");
    }

    @Deactivate
    protected void deactivate() {
        packetService.removeProcessor(processor);
        packetService.cancelPackets(ipv4Selector, PacketPriority.REACTIVE, appId);
        deviceLabels.clear();
        log.info("FlowManagerService deactivated.");
    }

    private int getMplsLabel(DeviceId deviceId) {
        return deviceLabels.computeIfAbsent(deviceId, k -> labelAllocator.getAndIncrement());
    }
    // We keep track of installed core rules to avoid redundant installations,
    // because of delay in flow rule installation
    private Set<String> installedRules = ConcurrentHashMap.newKeySet();
    private String getRuleKey(DeviceId deviceId, int mplsLabel, PortNumber outPort) {
        return deviceId + ":" + mplsLabel + ":" + outPort;
    }

    private class ReactiveProcessor implements PacketProcessor {
        @Override
        public void process(PacketContext ctx) {
            if (ctx.isHandled()) { // Another processor has already handled this packet
                return;
            }

            Ethernet eth = ctx.inPacket().parsed();
            if (eth == null) { // Not an Ethernet packet
                return;
            }

            // IDs are based on MAC addresses
            HostId dstId = HostId.hostId(eth.getDestinationMAC());
            HostId srcId = HostId.hostId(eth.getSourceMAC());

            if (!hostLocationService.hasHost(dstId)) {
                log.debug("Unknown host {}, ignoring packet.", dstId);
                return;
            }

            log.info("📥 Received packet from device {}",
                ctx.inPacket().receivedFrom().deviceId());
                ctx.block(); // Block the packet to prevent it from being processed by other applications

            HostLocationManager.HostLocationRecord record = hostLocationService.getRecord(dstId);
            if (record == null) {
                return;
            }

            HostLocationManager.HostLocationRecord inRecord = hostLocationService.getRecord(srcId);
            if (inRecord == null) {
                return;
            }

            // Extract necessary information for flow rule installation
            DeviceId dstDevice = record.location.deviceId();
            PortNumber dstPort = record.location.port();
            MacAddress dstMac = record.mac;
            DeviceId ingressDevice = inRecord.location.deviceId();

            // Allocate a unique MPLS label for the destination device
            int mplsLabel = getMplsLabel(dstDevice);

            // Edge device logic
            if (ingressDevice.equals(dstDevice)) {
                log.info("Packet from host-attached switch.");
                ctx.treatmentBuilder().setOutput(dstPort);
                ctx.send();
                return;
            }

            // Core routing logic
            Set<Path> paths = pathService.getPaths(ingressDevice, dstDevice);
            if (paths.isEmpty()) {
                log.warn("No path found from ingress {} to egress {}", ingressDevice, dstDevice);
                return;
            }

            // For simplicity, we take the first available path.
            // In production, we might want to implement better path selection logic.
            Path path = paths.iterator().next();
            Link firstLink = path.links().get(0);

            // Install flow rules along the path
            // Ingress rule on the first switch: match dst MAC, push MPLS, output to next hop
            flowInstaller.installIngressRule(
                ingressDevice,
                eth.getDestinationMAC(),
                mplsLabel,
                firstLink.src().port()
            );
            // Core rules on intermediate switches: match MPLS label, output to next hop
            for (Link link : path.links()) {
                DeviceId device = link.src().deviceId();
                if (device.equals(ingressDevice)) {
                    continue;
                }
                PortNumber outPort = link.src().port();
                // If core switch has already an identical flow rule, do nothing
                String ruleKey = getRuleKey(device, mplsLabel, outPort);
                if (!installedRules.contains(ruleKey)) {
                    flowInstaller.installCoreRule(device, mplsLabel, outPort);
                    installedRules.add(ruleKey);
                }
            }
            // Egress rule on the last switch: match MPLS label, pop MPLS, output to host port
            flowInstaller.installEgressRule(dstDevice, mplsLabel, dstMac, dstPort);

            // Send the packet out the first hop towards the destination
            ctx.treatmentBuilder()
                    .pushMpls()
                    .setMpls(MplsLabel.mplsLabel(mplsLabel))
                    .setOutput(firstLink.src().port());
            ctx.send();
        }
    }

    // Removes stale rules that match a specific host MAC address from previous Location.
    private void removeStaleRules(MacAddress hostMac, DeviceId oldLocation, DeviceId newLocation) {
        // Retrieve the old MPLS label for the previous location, if it exists
        Integer oldMplsLabel = deviceLabels.get(oldLocation);

        // If we had previously assigned an MPLS label to the old location,
        // we can attempt to remove the corresponding ingress rules
        deviceService.getAvailableDevices().forEach(device -> {
            if (device.id().equals(newLocation)) {
                return; // Skip the new location device
            }
            flowRuleService.getFlowEntries(device.id()).forEach(flowEntry -> {
                if (flowEntry.appId() == appId.id()) {
                    // Check if this rule matches the host MAC address
                    boolean matchesHostMac = flowEntry.selector().criteria().stream()
                        .filter(c -> c.type() == Criterion.Type.ETH_DST)
                        .map(c -> (EthCriterion) c)
                        .anyMatch(eth -> eth.mac().equals(hostMac));

                    if (!matchesHostMac) {
                        return;  // Skip if MAC doesn't match
                    }

                    // Check if this rule matches the old MPLS label (if we have one)
                    boolean matchesOldMpls = (oldMplsLabel != null) &&
                        flowEntry.selector().criteria().stream()
                            .filter(c -> c.type() == Criterion.Type.MPLS_LABEL)
                            .anyMatch(c -> {
                                org.onosproject.net.flow.criteria.MplsCriterion mplsCrit =
                                    (org.onosproject.net.flow.criteria.MplsCriterion) c;
                                return mplsCrit.label().toInt() == oldMplsLabel;
                            });

                    if (matchesHostMac && matchesOldMpls) {
                        flowRuleService.removeFlowRules(flowEntry);
                        log.info("🗑 Removed outdated rule for host {} on device {}",
                            hostMac,
                            device.id());
                    } else if (matchesHostMac) {
                        // If we don't have an old MPLS label, this indicated an egress rule
                        flowRuleService.removeFlowRules(flowEntry);
                        log.info("🗑 Removed outdated rule for host {} on device {}",
                            hostMac,
                            device.id());
                    }
                }
            });
        });
    }
}