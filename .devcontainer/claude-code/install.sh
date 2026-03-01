#!/bin/sh
set -eu

# Claude Code CLI Local Feature Install Script
# Installs Claude Code via pixi and sets up configuration directories

# Global variables set by resolve_target_home
TARGET_USER=""
TARGET_HOME=""

# Function to resolve target user and home directory with validation
# Sets TARGET_USER and TARGET_HOME global variables
resolve_target_home() {
    TARGET_USER="${_REMOTE_USER:-vscode}"
    TARGET_HOME="${_REMOTE_USER_HOME:-}"

    # If _REMOTE_USER_HOME is not set, try to infer from current user or /home/<user>
    if [ -z "${TARGET_HOME}" ]; then
        if [ "$(id -un 2>/dev/null)" = "${TARGET_USER}" ] && [ -n "${HOME:-}" ]; then
            TARGET_HOME="${HOME}"
        elif [ -d "/home/${TARGET_USER}" ]; then
            TARGET_HOME="/home/${TARGET_USER}"
        fi
    fi

    # If TARGET_HOME is set but doesn't exist, try fallbacks
    if [ -n "${TARGET_HOME}" ] && [ ! -d "${TARGET_HOME}" ]; then
        if [ -n "${HOME:-}" ] && [ -d "$HOME" ]; then
            echo "Warning: TARGET_HOME '${TARGET_HOME}' does not exist, falling back to \$HOME: $HOME" >&2
            TARGET_HOME="$HOME"
        elif [ -d "/home/${TARGET_USER}" ]; then
            echo "Warning: TARGET_HOME '${TARGET_HOME}' does not exist, falling back to /home/${TARGET_USER}" >&2
            TARGET_HOME="/home/${TARGET_USER}"
        fi
    fi

    # Ensure we ended up with a valid, existing home directory
    if [ -z "${TARGET_HOME}" ] || [ ! -d "${TARGET_HOME}" ]; then
        echo "Error: could not determine a valid home directory for user '${TARGET_USER}'." >&2
        echo "Checked _REMOTE_USER_HOME ('${_REMOTE_USER_HOME:-}'), \$HOME ('${HOME:-}'), and /home/${TARGET_USER}." >&2
        exit 1
    fi
}

# Function to install pixi if not found
install_pixi() {
    echo "Installing pixi..."

    # Detect architecture
    case "$(uname -m)" in
        x86_64|amd64) ARCH="x86_64" ;;
        aarch64|arm64) ARCH="aarch64" ;;
        *) echo "Unsupported architecture: $(uname -m)" >&2; exit 1 ;;
    esac

    # Download and install pixi
    curl -fsSL "https://github.com/prefix-dev/pixi/releases/latest/download/pixi-${ARCH}-unknown-linux-musl" -o /usr/local/bin/pixi
    chmod +x /usr/local/bin/pixi

    echo "pixi installed successfully"
    pixi --version
}

# Function to install Claude Code CLI via pixi
install_claude_code() {
    echo "Installing Claude Code CLI via pixi..."

    # Install pixi if not available
    if ! command -v pixi >/dev/null; then
        install_pixi
    fi

    # Resolve target user and home (sets TARGET_USER and TARGET_HOME)
    resolve_target_home

    # Install with pixi global from blooop channel
    # Run as target user so it installs to their home directory
    if [ "$(id -u)" -eq 0 ] && [ "$TARGET_USER" != "root" ]; then
        su - "$TARGET_USER" -c "pixi global install --channel https://prefix.dev/blooop claude-shim"
    else
        pixi global install --channel https://prefix.dev/blooop claude-shim
    fi

    # Add pixi bin path to user's profile if not already there
    local profile="$TARGET_HOME/.profile"
    local pixi_path_line='export PATH="$HOME/.pixi/bin:$PATH"'
    if [ -f "$profile" ] && ! grep -q '\.pixi/bin' "$profile"; then
        echo "$pixi_path_line" >> "$profile"
    elif [ ! -f "$profile" ]; then
        echo "$pixi_path_line" > "$profile"
        chown "$TARGET_USER:$TARGET_USER" "$profile" 2>/dev/null || true
    fi

    # Workaround: pixi trampoline fails for bash scripts, so add env bin directly
    # This conditionally adds the path only if the env exists
    local env_path_line='[ -d "$HOME/.pixi/envs/claude-shim/bin" ] && export PATH="$HOME/.pixi/envs/claude-shim/bin:$PATH"'
    if [ -f "$profile" ] && ! grep -q 'pixi/envs/claude-shim' "$profile"; then
        echo "# Workaround: pixi trampoline fails for bash scripts" >> "$profile"
        echo "$env_path_line" >> "$profile"
    fi

    # Verify installation by checking the trampoline exists (don't run it - that triggers download)
    local pixi_bin_path="$TARGET_HOME/.pixi/bin"
    local claude_bin="$pixi_bin_path/claude"
    if [ -x "$claude_bin" ]; then
        echo "Claude Code CLI installed successfully!"
        echo "(Claude binary will be downloaded on first run)"
        return 0
    else
        echo "ERROR: Claude Code CLI installation failed! Binary not found at $claude_bin"
        return 1
    fi
}

# Function to create Claude configuration directories
create_claude_directories() {
    echo "Creating Claude configuration directories..."

    # Resolve target user and home (sets TARGET_USER and TARGET_HOME)
    resolve_target_home

    echo "Target home directory: $TARGET_HOME"
    echo "Target user: $TARGET_USER"

    # Create the main .claude directory and subdirectories
    mkdir -p "$TARGET_HOME/.claude"
    mkdir -p "$TARGET_HOME/.claude/agents"
    mkdir -p "$TARGET_HOME/.claude/commands"
    mkdir -p "$TARGET_HOME/.claude/hooks"

    # Create empty config files if they don't exist
    if [ ! -f "$TARGET_HOME/.claude/.credentials.json" ]; then
        echo "{}" > "$TARGET_HOME/.claude/.credentials.json"
        chmod 600 "$TARGET_HOME/.claude/.credentials.json"
    fi

    if [ ! -f "$TARGET_HOME/.claude/.claude.json" ]; then
        echo "{}" > "$TARGET_HOME/.claude/.claude.json"
        chmod 600 "$TARGET_HOME/.claude/.claude.json"
    fi

    # Set proper ownership
    if [ "$(id -u)" -eq 0 ]; then
        chown -R "$TARGET_USER:$TARGET_USER" "$TARGET_HOME/.claude" || true
    fi

    echo "Claude directories created successfully"
}

# Main script
main() {
    echo "========================================="
    echo "Activating feature 'claude-code' (local)"
    echo "========================================="

    # Resolve target user and home (sets TARGET_USER and TARGET_HOME)
    resolve_target_home

    local claude_bin="$TARGET_HOME/.pixi/bin/claude"

    # Install Claude Code CLI
    if [ -x "$claude_bin" ]; then
        echo "Claude Code CLI is already installed"
    else
        install_claude_code || exit 1
    fi

    # Create Claude configuration directories
    create_claude_directories

    echo "========================================="
    echo "Claude Code feature activated successfully!"
    echo "========================================="
    echo ""
    echo "Configuration is bind-mounted from the host (~/.claude)"
    echo "and persists across container rebuilds."
    echo ""
    echo "To authenticate, run 'claude' and follow the OAuth flow."
    echo ""
}

main
