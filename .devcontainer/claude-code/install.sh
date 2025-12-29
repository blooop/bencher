#!/bin/sh
set -eu

# Claude Code CLI Local Feature Install Script
# Based on: https://github.com/anthropics/devcontainer-features/pull/25
# Combines CLI installation with configuration directory setup

# Function to install Claude Code CLI
install_claude_code() {
    echo "Installing Claude Code CLI globally..."

    # Verify Node.js and npm are available
    if ! command -v node >/dev/null || ! command -v npm >/dev/null; then
        cat <<EOF

ERROR: Node.js and npm are required but not found!

This should not happen as the Node.js feature is automatically installed
via the 'installsAfter' mechanism in devcontainer-feature.json.

Please check:
1. The devcontainer feature specification is correct
2. The Node.js feature (ghcr.io/devcontainers/features/node) is available
3. Your devcontainer build logs for errors

EOF
        exit 1
    fi

    # Install with npm
    npm install -g @anthropic-ai/claude-code

    # Verify installation
    if command -v claude >/dev/null; then
        echo "Claude Code CLI installed successfully!"
        claude --version
        return 0
    else
        echo "ERROR: Claude Code CLI installation failed!"
        return 1
    fi
}

# Function to create Claude configuration directories
# These directories will be mounted from the host, but we create them
# in the container to ensure they exist and have proper permissions
create_claude_directories() {
    echo "Creating Claude configuration directories..."

    # Determine the target user's home directory
    # $_REMOTE_USER is set by devcontainer, fallback to 'vscode'
    local target_user="${_REMOTE_USER:-vscode}"
    local target_home="${_REMOTE_USER_HOME:-/home/${target_user}}"

    # Be defensive: if the resolved home does not exist, fall back to $HOME,
    # then to /home/${target_user}. If neither is available, fail clearly.
    if [ ! -d "$target_home" ]; then
        if [ -n "${HOME:-}" ] && [ -d "$HOME" ]; then
            echo "Warning: target_home '$target_home' does not exist, falling back to \$HOME: $HOME" >&2
            target_home="$HOME"
        elif [ -d "/home/${target_user}" ]; then
            echo "Warning: target_home '$target_home' does not exist, falling back to /home/${target_user}" >&2
            target_home="/home/${target_user}"
        else
            echo "Error: No suitable home directory found for '${target_user}'. Tried:" >&2
            echo "  - _REMOTE_USER_HOME='${_REMOTE_USER_HOME:-}'" >&2
            echo "  - \$HOME='${HOME:-}'" >&2
            echo "  - /home/${target_user}" >&2
            echo "Please set _REMOTE_USER_HOME to a valid, writable directory." >&2
            exit 1
        fi
    fi

    echo "Target home directory: $target_home"
    echo "Target user: $target_user"

    # Create the main .claude directory
    mkdir -p "$target_home/.claude"
    mkdir -p "$target_home/.claude/agents"
    mkdir -p "$target_home/.claude/commands"
    mkdir -p "$target_home/.claude/hooks"

    # Create empty config files if they don't exist
    # This ensures the bind mounts won't fail if files are missing on host
    if [ ! -f "$target_home/.claude/.credentials.json" ]; then
        echo "{}" > "$target_home/.claude/.credentials.json"
        chmod 600 "$target_home/.claude/.credentials.json"
    fi

    if [ ! -f "$target_home/.claude/.claude.json" ]; then
        echo "{}" > "$target_home/.claude/.claude.json"
        chmod 600 "$target_home/.claude/.claude.json"
    fi

    # Set proper ownership
    # Note: These will be overridden by bind mounts from the host,
    # but this ensures the directories exist with correct permissions
    # if the mounts fail or for non-mounted directories
    if [ "$(id -u)" -eq 0 ]; then
        chown -R "$target_user:$target_user" "$target_home/.claude" || true
    fi

    echo "Claude directories created successfully"
}

# Main script starts here
main() {
    echo "========================================="
    echo "Activating feature 'claude-code' (local)"
    echo "========================================="

    # Install Claude Code CLI (or verify it's already installed)
    if command -v claude >/dev/null; then
        echo "Claude Code CLI is already installed"
        claude --version
    else
        install_claude_code || exit 1
    fi

    # Create Claude configuration directories
    create_claude_directories

    echo "========================================="
    echo "Claude Code feature activated successfully!"
    echo "========================================="
    echo ""
    echo "Configuration files mounted from host:"
    echo "  Read-Write (auth & state):"
    echo "    - ~/.claude/.credentials.json (OAuth tokens)"
    echo "    - ~/.claude/.claude.json (account, setup tracking)"
    echo ""
    echo "  Read-Only (security-protected):"
    echo "    - ~/.claude/CLAUDE.md"
    echo "    - ~/.claude/settings.json"
    echo "    - ~/.claude/agents/"
    echo "    - ~/.claude/commands/"
    echo "    - ~/.claude/hooks/"
    echo ""
    echo "Authentication:"
    echo "  - If you're already authenticated on your host, credentials are shared"
    echo "  - Otherwise, run 'claude' and follow the OAuth flow"
    echo "  - The OAuth callback may open in your host browser"
    echo "  - Credentials are stored on your host at ~/.claude/.credentials.json"
    echo ""
    echo "To modify config files, edit on your host machine and rebuild the container."
    echo ""
}

# Execute main function
main
