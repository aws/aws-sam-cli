#!/bin/bash
set -xeo pipefail

export SAM_CLI_TELEMETRY="${SAM_CLI_TELEMETRY:-0}"

if [ "$CI_OVERRIDE" = "1" ]; then
    sam_binary="sam-beta"
elif [ "$IS_NIGHTLY" = "1" ]; then
    sam_binary="sam-nightly"
elif [ "$SAM_CLI_DEV" = "1" ]; then
    sam_binary="samdev"
else
    sam_binary="sam"
fi

if ! command -v "$sam_binary" &> /dev/null; then
    echo "$sam_binary not found. Please check if it is in PATH"
    exit 1
fi

echo "Using ${sam_binary} as SAM CLI binary name" 

if [ "$sam_binary" = "sam" ]; then
    SAMCLI_INSTALLED_VERSION=$($sam_binary --version | cut -d " " -f 4)

    # Get latest SAM CLI version from GH main branch
    SAMCLI_LATEST_VERSION=$(curl -L https://raw.githubusercontent.com/aws/aws-sam-cli/master/samcli/__init__.py | tail -n 1 | cut -d '"' -f 2)

    # Check version
    if [[ "$SAMCLI_INSTALLED_VERSION" != "$SAMCLI_LATEST_VERSION" ]]; then
        echo "expected: $SAMCLI_LATEST_VERSION; got: $SAMCLI_INSTALLED_VERSION"
        exit 1
    fi

    echo "Version check succeeded"
fi

echo "Starting testing sam binary"
rm -rf sam-app-testing
"$sam_binary" init --no-interactive -n sam-app-testing --dependency-manager mod --runtime go1.x --app-template hello-world --package-type Zip --architecture x86_64
cd sam-app-testing
GOFLAGS="-buildvcs=false" "$sam_binary" build
"$sam_binary" validate

echo "sam init, sam build, and sam validate commands Succeeded"
