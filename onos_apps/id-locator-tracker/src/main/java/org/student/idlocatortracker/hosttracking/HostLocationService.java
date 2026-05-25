package org.student.idlocatortracker.hosttracking;

import org.onlab.packet.IpAddress;
import org.onlab.packet.MacAddress;
import org.onosproject.net.HostId;
import org.onosproject.net.HostLocation;

import java.util.Map;
import java.util.Set;

/**
 * Service interface for managing host locations in the network.
 * Provides methods to query and retrieve host location information.
 */
public interface HostLocationService {
    /**
     * Checks whether the table contains information for the given host.
     *
     * @param hostId the ID of the host to check
     * @return true if the host exists in the table, false otherwise
     */
    boolean hasHost(HostId hostId);

    /**
     * Retrieves the HostLocationRecord for a specific host.
     *
     * @param hostId the ID of the host
     * @return the HostLocationRecord if present, or null if the host is not in the table
     */
    HostLocationManager.HostLocationRecord getRecord(HostId hostId);

    /**
     * Returns an immutable copy of the full host table.
     *
     * @return a map of all HostId to HostLocationRecord entries
     */
    Map<HostId, HostLocationManager.HostLocationRecord> getAllRecords();

    /**
     * Manually updates the host location record.
     * Useful for detecting host movements via packet sniffing when standard
     * ONOS host events are unreliable.
     *
     * @param hostId the ID of the host
     * @param mac the MAC address of the host
     * @param ips the set of IP addresses
     * @param location the new host location (device + port)
     */
    void manualUpdate(HostId hostId, MacAddress mac, Set<IpAddress> ips, HostLocation location);

    /**
     * Register a callback to be notified when a host moves.
     * The callback is guaranteed to be called AFTER the internal hostTable is updated.
     *
     * @param callback the callback to register
     */
    void registerHostMovementCallback(HostMovementCallback callback);
}