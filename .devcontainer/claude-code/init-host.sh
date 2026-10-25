#!/bin/sh
# Create the host directories that devcontainer.json bind-mounts.
# This script runs on the HOST before the container is created. A bind mount
# whose source is missing fails container creation, so every bind source must
# exist even on a host that has never run claude or gh.
# mkdir -p is idempotent - it only creates if missing, won't clobber existing.

mkdir -p "$HOME/.claude" "$HOME/.config/gh"
