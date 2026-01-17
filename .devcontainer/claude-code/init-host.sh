#!/bin/sh
# Initialize Claude Code host directory for devcontainer bind mount
# This script runs on the HOST before the container is created.
# mkdir -p is idempotent - it only creates if missing, won't clobber existing.

mkdir -p "$HOME/.claude"
