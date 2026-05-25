# ----------------------------------------------------------------------
# STEP 1: CONFIGURE APPLICATION NAME
# ONLY change the values for the four variables below.
# ----------------------------------------------------------------------

# 1. Human-readable name (used in ONOS GUI):
APP_NAME="ID/Locator Host Tracking"

# 2. Short, hyphenated project/folder name (MANDATORY for Maven):
ARTIFACT_ID="tracker-mpls"

# 3. Base Group/Domain (e.g., org.student or net.dtu):
GROUP_ID="org.student"

# 4. Root Java package (must combine GROUP_ID and ARTIFACT_ID/sub-namespace):
PACKAGE_NAME="${GROUP_ID}.${ARTIFACT_ID//-}" # e.g., org.student.idlocatortracker

# ----------------------------------------------------------------------
# STEP 2: DO NOT CHANGE BELOW THIS LINE
# Using 'onos-bundle-archetype' at 2.7.0.
# This archetype generates the basic OSGi module structure.
# ----------------------------------------------------------------------

mvn archetype:generate \
    -DarchetypeGroupId=org.onosproject \
    -DarchetypeArtifactId=onos-bundle-archetype \
    -DarchetypeVersion=2.7.0 \
    -DgroupId=$GROUP_ID \
    -DartifactId=$ARTIFACT_ID \
    -Dversion=1.0-SNAPSHOT \
    -Dname="$APP_NAME" \
    -Dpackage=$PACKAGE_NAME
