#!/bin/bash
set -euo pipefail

# Migrate devcontainer.json from local builds to a prebuilt GHCR image.
# Also attempts to make the GHCR package public.

DEVCONTAINER_JSON=".devcontainer/devcontainer.json"

# --- Check prerequisites ---
if ! command -v gh >/dev/null 2>&1; then
    echo "WARNING: GitHub CLI (gh) not found. Will skip making the package public." >&2
    GH_AVAILABLE=false
else
    GH_AVAILABLE=true
fi

# --- Resolve GitHub owner/repo from git remote ---
REMOTE_URL=$(git remote get-url origin 2>/dev/null) || {
    echo "ERROR: No git remote 'origin' found." >&2
    exit 1
}

# Handle common GitHub remote URL formats
REPO=$(echo "$REMOTE_URL" | sed -E 's#(ssh://git@github\.com/|git@github\.com:|https?://github\.com/|git://github\.com/)##; s/\.git$//')

if [[ -z "$REPO" || "$REPO" != */* ]]; then
    echo "ERROR: Could not parse owner/repo from remote URL: $REMOTE_URL" >&2
    exit 1
fi

IMAGE="ghcr.io/${REPO}/devcontainer:latest"
echo "Repository: $REPO"
echo "Image:      $IMAGE"

# --- Check current state: look for an uncommented "image": line ---
if grep -q '^[[:space:]]*"image"[[:space:]]*:' "$DEVCONTAINER_JSON"; then
    echo "Already using a prebuilt image. Nothing to do."
    exit 0
fi

# --- Replace the file using awk for reliable block manipulation ---
awk -v image="$IMAGE" '
    # Comment out uncommented "build" block (4-space indent open/close).
    # NOTE: assumes no nested {} within these blocks.
    /^    "build": \{/ { in_build=1 }
    in_build {
        sub(/^    /, "    // ")
        if (/^    \/\/ \}/) in_build=0
        print; next
    }

    # Comment out uncommented "features" block (4-space indent open/close).
    # NOTE: assumes no nested {} within these blocks.
    /^    "features": \{/ { in_features=1 }
    in_features {
        sub(/^    /, "    // ")
        if (/^    \/\/ \}/) in_features=0
        print; next
    }

    # Uncomment the image line and set the correct reference
    /^    \/\/ "image":/ {
        printf "    \"image\": \"%s\",\n", image
        next
    }

    { print }
' "$DEVCONTAINER_JSON" > "${DEVCONTAINER_JSON}.tmp" && mv "${DEVCONTAINER_JSON}.tmp" "$DEVCONTAINER_JSON"

echo ""
echo "Updated $DEVCONTAINER_JSON to use prebuilt image."

# --- Try to make the GHCR package public ---
echo ""
echo "Attempting to make GHCR package public..."

OWNER=$(echo "$REPO" | cut -d'/' -f1)
PACKAGE_NAME=$(echo "$REPO" | cut -d'/' -f2)
ENCODED_PACKAGE="${PACKAGE_NAME}%2Fdevcontainer"

if ! $GH_AVAILABLE; then
    echo "Skipping: gh CLI not available."
    echo ""
    echo "To make the package public, install gh and run:"
    echo "  gh auth refresh -s write:packages"
    echo "  gh api --method PATCH /user/packages/container/${ENCODED_PACKAGE} -f visibility=public"
    exit 0
fi

# Determine if owner is an org or a user
IS_ORG=false
if gh api "/orgs/${OWNER}" >/dev/null 2>&1; then
    IS_ORG=true
fi

if $IS_ORG; then
    API_PATH="/orgs/${OWNER}/packages/container/${ENCODED_PACKAGE}"
    SETTINGS_URL="https://github.com/orgs/${OWNER}/packages/container/${ENCODED_PACKAGE}/settings"
else
    API_PATH="/user/packages/container/${ENCODED_PACKAGE}"
    SETTINGS_URL="https://github.com/users/${OWNER}/packages/container/${ENCODED_PACKAGE}/settings"
fi

if API_OUTPUT=$(gh api --method PATCH "$API_PATH" -f visibility=public 2>&1); then
    echo "GHCR package is now public."
else
    echo "Could not set package visibility automatically."
    echo "API response: $API_OUTPUT"
    echo ""
    echo "To make the package public manually, either:"
    echo ""
    echo "  1. Visit: $SETTINGS_URL"
    echo "     -> Danger Zone -> Change visibility -> Public"
    echo ""
    echo "  2. Run:"
    echo "     gh auth refresh -s write:packages"
    echo "     gh api --method PATCH $API_PATH -f visibility=public"
fi
