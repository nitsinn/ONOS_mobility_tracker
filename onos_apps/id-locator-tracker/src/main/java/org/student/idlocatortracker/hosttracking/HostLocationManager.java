package org.student.idlocatortracker.hosttracking;

import org.onlab.packet.IpAddress;
import org.onlab.packet.MacAddress;

import org.onosproject.net.Host;
import org.onosproject.net.HostId;
import org.onosproject.net.HostLocation;
import org.onosproject.net.host.HostEvent;
import org.onosproject.net.host.HostListener;
import org.onosproject.net.host.HostService;
import org.osgi.service.component.annotations.Activate;
import org.osgi.service.component.annotations.Component;
import org.osgi.service.component.annotations.Deactivate;
import org.osgi.service.component.annotations.Reference;
import org.osgi.service.component.annotations.ReferenceCardinality;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Collections;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;


@Component(immediate = true, service = HostLocationService.class)
public class HostLocationManager implements HostLocationService {

    private final Logger log = LoggerFactory.getLogger(getClass());

    @Reference(cardinality = ReferenceCardinality.MANDATORY)
    protected HostService hostService;

    private final HostListener hostListener = new InnerHostListener();

    // ← NEW: Store callbacks registered by other components
    private final Set<HostMovementCallback> hostMovementCallbacks = ConcurrentHashMap.newKeySet();

    // Mapping table
    private final Map<HostId, HostLocationRecord> hostTable = new ConcurrentHashMap<>();

    @Activate
    protected void activate() {
        hostService.addListener(hostListener);
        log.info("Started host location manager");
    }

    @Deactivate
    protected void deactivate() {
        hostService.removeListener(hostListener);
        hostTable.clear();
        hostMovementCallbacks.clear();
        log.info("Stopped host location manager");
    }

    /**
     * ← NEW: Register a callback to be notified of host movements.
     * The callback will be invoked AFTER the hostTable is updated.
     */
    @Override
    public void registerHostMovementCallback(HostMovementCallback callback) {
        hostMovementCallbacks.add(callback);
        log.info("✅ HostMovementCallback registered: {}",
            callback.getClass().getSimpleName());
    }

    /**
     * Inner listener that listens to ONOS native host events.
     * This is the ONLY place that updates the hostTable.
     */
    private class InnerHostListener implements HostListener {
        @Override
        public void event(HostEvent event) {
            Host host = event.subject();

            switch (event.type()) {
                case HOST_ADDED:
                case HOST_UPDATED:
                case HOST_MOVED:
                    // For HOST_MOVED, we need to get the old location before updating
                    HostLocation oldLocation = null;
                    if (event.type() == HostEvent.Type.HOST_MOVED) {
                        HostLocationRecord existingRecord = hostTable.get(host.id());
                        oldLocation = (existingRecord != null) ? existingRecord.location : null;
                    }

                    // ← STEP 1: Update the table
                    recordHostLocation(host);

                    // ← STEP 2: If this is a movement, trigger callbacks
                    if (event.type() == HostEvent.Type.HOST_MOVED) {
                        log.info("🏃‍➡️ HOST_MOVED detected: {} from {} to {}",
                            host.mac(),
                            oldLocation != null ? oldLocation.deviceId() : "unknown",
                            host.location().deviceId());

                        // ← CRITICAL: Call callbacks AFTER updating table
                        // Callbacks are guaranteed to see the updated data
                        triggerHostMovementCallbacks(
                            host.id(),
                            host.mac(),
                            oldLocation,
                            host.location()
                        );
                    }
                    break;

                case HOST_REMOVED:
                    hostTable.remove(host.id());
                    break;

                default:
                    break;
            }
        }
    }

    private void recordHostLocation(Host host) {
        HostLocationRecord record =
                new HostLocationRecord(host.mac(),
                        host.ipAddresses(),
                        host.location());

        hostTable.put(host.id(), record);

        log.debug("Updated HostInfo: {} -> MAC={}, IPs={}, LOCATION={}",
                host.id(), record.mac, record.ips, record.location);
    }

    /**
     * ← NEW: Trigger all registered callbacks.
     * This happens AFTER recordHostLocation(), so data is guaranteed to be fresh.
     */
    private void triggerHostMovementCallbacks(HostId hostId, MacAddress mac,
                                              HostLocation oldLocation,
                                              HostLocation newLocation) {
        hostMovementCallbacks.forEach(callback -> {
            try {
                log.info("  → Invoking callback: {}", callback.getClass().getSimpleName());
                callback.onHostMoved(hostId, mac, oldLocation, newLocation);
            } catch (Exception e) {
                log.error("Error in HostMovementCallback: {}", callback.getClass().getSimpleName(), e);
            }
        });
    }

    // ----------  PUBLIC METHODS FOR OTHER COMPONENTS  ----------
    @Override
    public boolean hasHost(HostId hostId) {
        return hostTable.containsKey(hostId);
    }

    @Override
    public HostLocationRecord getRecord(HostId hostId) {
        return hostTable.get(hostId);
    }

    @Override
    public Map<HostId, HostLocationRecord> getAllRecords() {
        return Collections.unmodifiableMap(hostTable);
    }

    // ----------  PUBLIC RECORD CLASS (exposed) ----------
    public static class HostLocationRecord {
        public MacAddress mac;
        public Set<IpAddress> ips;
        public HostLocation location;

        public HostLocationRecord(MacAddress mac, Set<IpAddress> ips, HostLocation location) {
            this.mac = mac;
            this.ips = ips;
            this.location = location;
        }
    }

    @Override
    public void manualUpdate(HostId hostId, MacAddress mac, Set<IpAddress> ips, HostLocation location) {
        HostLocationRecord existingRecord = hostTable.get(hostId);

        // Use existing IPs if new IPs are null
        Set<IpAddress> ipsToUse = (ips != null) ? ips :
            (existingRecord != null ? existingRecord.ips : Set.of());

        HostLocationRecord record = new HostLocationRecord(mac, ipsToUse, location);
        hostTable.put(hostId, record);
        log.info("Manually updated HostInfo: {} -> MAC={}, IPs={}, LOCATION={}",
            hostId, mac, ipsToUse, location);
    }
}