package org.student.idlocatortracker.flowlogic;

import org.onlab.packet.Ethernet;
import org.onlab.packet.MacAddress;
import org.onlab.packet.MplsLabel;
import org.onosproject.core.ApplicationId;
import org.onosproject.core.CoreService;
import org.onosproject.net.DeviceId;
import org.onosproject.net.PortNumber;
import org.onosproject.net.flow.DefaultFlowRule;
import org.onosproject.net.flow.DefaultTrafficSelector;
import org.onosproject.net.flow.DefaultTrafficTreatment;
import org.onosproject.net.flow.FlowRule;
import org.onosproject.net.flow.FlowRuleService;
import org.osgi.service.component.annotations.Component;
import org.osgi.service.component.annotations.Reference;
import org.osgi.service.component.annotations.ReferenceCardinality;
import org.osgi.service.component.annotations.Activate;
import org.osgi.service.component.annotations.Deactivate;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;


import org.onlab.packet.EthType;

@Component(immediate = true, service = FlowInstallerService.class)
public class FlowInstallerService {

    private final Logger log = LoggerFactory.getLogger(getClass());

    @Reference(cardinality = ReferenceCardinality.MANDATORY)
    protected FlowRuleService flowRuleService;

    @Reference(cardinality = ReferenceCardinality.MANDATORY)
    protected CoreService coreService;

    private ApplicationId appId;

    @Activate
    protected void activate() {
        this.appId = coreService.registerApplication("org.student.idlocatortracker");
        log.info("FlowInstallerService activated");
    }

    @Deactivate
    protected void deactivate() {
        log.info("FlowInstallerService deactivated");
    }

    public void installIngressRule(DeviceId deviceId,
                                   MacAddress dstMac,
                                   int mplsLabel,
                                   PortNumber outPort) {
        log.info("🟢 INGRESS: Installing rule on device {}: match dst MAC {}, push MPLS label {}, out port {}",
            deviceId, dstMac, mplsLabel, outPort);
        FlowRule rule = DefaultFlowRule.builder()
                .forDevice(deviceId)
                .withSelector(DefaultTrafficSelector.builder()
                        .matchEthType(Ethernet.TYPE_IPV4)
                        .matchEthDst(dstMac)
                        .build())
                .withTreatment(DefaultTrafficTreatment.builder()
                        .pushMpls()
                        .setMpls(MplsLabel.mplsLabel(mplsLabel))
                        .setOutput(outPort)
                        .build())
                .withPriority(60000)
                .fromApp(appId)
                .makeTemporary(60)
                // .makePermanent()
                .build();

        flowRuleService.applyFlowRules(rule);
    }

    public void installCoreRule(DeviceId deviceId,
                                int mplsLabel,
                                PortNumber outPort) {
        log.info("🟠 CORE: Installing rule on device {}: match MPLS label {}, out port {}",
            deviceId, mplsLabel, outPort);
        FlowRule rule = DefaultFlowRule.builder()
                .forDevice(deviceId)
                .withSelector(DefaultTrafficSelector.builder()
                        .matchEthType(Ethernet.MPLS_UNICAST)
                        .matchMplsLabel(MplsLabel.mplsLabel(mplsLabel))
                        .build())
                .withTreatment(DefaultTrafficTreatment.builder()
                        .setOutput(outPort)
                        .build())
                .withPriority(60000)
                .fromApp(appId)
                // .makeTemporary(300)
                .makePermanent()
                .build();

        flowRuleService.applyFlowRules(rule);
    }

    public void installEgressRule(DeviceId deviceId,
                                  int mplsLabel,
                                  MacAddress dstMac,
                                  PortNumber hostPort) {
        log.info("🔴 EGRESS: Installing rule on device {}: match MPLS label {}, pop MPLS, out port {}",
            deviceId, mplsLabel, hostPort);
        FlowRule rule = DefaultFlowRule.builder()
                .forDevice(deviceId)
                .withSelector(DefaultTrafficSelector.builder()
                        .matchEthType(Ethernet.MPLS_UNICAST)
                        .matchMplsLabel(MplsLabel.mplsLabel(mplsLabel))
                        .matchEthDst(dstMac)
                        .build())
                .withTreatment(DefaultTrafficTreatment.builder()
                        .popMpls(new EthType(Ethernet.TYPE_IPV4))
                        .setOutput(hostPort)
                        .build())
                .withPriority(60000)
                .fromApp(appId)
                .makeTemporary(60)
                // .makePermanent()
                .build();

        flowRuleService.applyFlowRules(rule);
    }
}