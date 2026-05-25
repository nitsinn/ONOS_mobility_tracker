# -----------------------------------------------------------
# Dynamic ONOS Application Deployment Script
# -----------------------------------------------------------

# 1. Prompt for the application folder/artifact ID
APP_NAME="id-locator-tracker" # You can change this to your application name if different

# The version is assumed to be 1.0-SNAPSHOT as is standard for development
APP_VERSION="1.0-SNAPSHOT"

# 2. Construct the full path to the .oar file
# The path is <app-name>/target/<app-name>-<version>.oar
OAR_PATH="${APP_NAME}/target/${APP_NAME}-${APP_VERSION}.oar"

# 3. Check if the file exists before attempting deployment
if [ ! -f "$OAR_PATH" ]; then
    echo ""
    echo "ERROR: OAR file not found at: $OAR_PATH"
    echo "Please ensure you have successfully run 'mvn clean install' inside the '${APP_NAME}' directory."
    exit 1
fi

echo ""
# Changed 127.0.0.1 to localhost
echo "Deploying $OAR_PATH to ONOS at localhost:8181..."
echo "--------------------------------------------------------"

# 4. Execute the deployment using curl
# Note: IP address is set for localhost container access
# Credentials are default: onos/rocks
curl -i -X POST -u onos:rocks \
     -H "Content-Type: application/octet-stream" \
     http://localhost:8181/onos/v1/applications \
     --data-binary "@$OAR_PATH"

echo "--------------------------------------------------------"
echo "Deployment command sent."
# ESCAPED PARENTHESES to fix the syntax error
echo "Next steps: Log into the ONOS CLI \(ssh -p 8101 onos@localhost\) and run:"
echo "apps -s"
echo "app activate org.foo.hosttracker (or your application ID)"