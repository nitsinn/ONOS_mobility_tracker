package org.student.idlocatortracker.hosttracking;

import org.onlab.packet.MacAddress;
import org.onosproject.net.HostId;
import org.onosproject.net.HostLocation;

/**
 * Callback interface for host movement events.
 * Implementation must be thread-safe.
 */
public interface HostMovementCallback {
    /**
     * Called when a host moves to a new location.
     *
     * GUARANTEE: The HostLocationManager's hostTable has ALREADY been updated
     * with the new location before this callback is invoked.
     *
     * @param hostId the host ID
     * @param mac the MAC address of the host
     * @param oldLocation the previous location (device/port), or null if unknown
     * @param newLocation the new location (device/port)
     */
    void onHostMoved(HostId hostId, MacAddress mac,
                     HostLocation oldLocation, HostLocation newLocation);
}