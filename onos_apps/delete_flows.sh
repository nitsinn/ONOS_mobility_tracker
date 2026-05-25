#!/bin/bash
ONOS_IP=localhost
USER="onos"
PASS="rocks"

# List and delete all flows
flows=$(curl -s -u $USER:$PASS http://$ONOS_IP:8181/onos/v1/flows | jq -r '.flows[] | "\(.deviceId) \(.id)"')

while read device flow; do
    echo "Deleting $flow on $device"
    curl -s -u $USER:$PASS -X DELETE \
        http://$ONOS_IP:8181/onos/v1/flows/$device/$flow
done <<< "$flows"

