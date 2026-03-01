#!/bin/bash
set -euo pipefail

# Switch devcontainer.json to build locally from Dockerfile.

DEVCONTAINER_JSON=".devcontainer/devcontainer.json"

# Already using local build?
if grep -q '^[[:space:]]*"build"' "$DEVCONTAINER_JSON"; then
    echo "Already using local build. Nothing to do."
    exit 0
fi

awk '
    # Uncomment commented build block
    /^    \/\/ "build": \{/ { in_build=1 }
    in_build {
        sub(/^    \/\/ /, "    ")
        if (/^    \}/) in_build=0
        print; next
    }

    # Uncomment commented features block
    /^    \/\/ "features": \{/ { in_features=1 }
    in_features {
        sub(/^    \/\/ /, "    ")
        if (/^    \}/) in_features=0
        print; next
    }

    # Comment out uncommented image line
    /^    "image":/ {
        sub(/^    /, "    // ")
        print; next
    }

    { print }
' "$DEVCONTAINER_JSON" > "${DEVCONTAINER_JSON}.tmp" && mv "${DEVCONTAINER_JSON}.tmp" "$DEVCONTAINER_JSON"

echo "Switched to local build from Dockerfile."
