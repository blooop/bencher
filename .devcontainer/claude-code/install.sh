#!/bin/sh
set -eu

# Claude Code CLI Local Feature Install Script
# Based on: https://github.com/anthropics/devcontainer-features/pull/25
# Combines CLI installation with configuration directory setup

# Function to detect the package manager and OS type
detect_package_manager() {
    for pm in apt-get apk dnf yum; do
        if command -v $pm >/dev/null; then
            case $pm in
                apt-get) echo "apt" ;;
                *) echo "$pm" ;;
            esac
            return 0
        fi
    done
    echo "unknown"
    return 1
}

# Function to install packages using the appropriate package manager
install_packages() {
    local pkg_manager="$1"
    shift
    local packages="$@"

    case "$pkg_manager" in
        apt)
            apt-get update
            apt-get install -y $packages
            ;;
        apk)
            apk add --no-cache $packages
            ;;
        dnf|yum)
            $pkg_manager install -y $packages
            ;;
        *)
            echo "WARNING: Unsupported package manager. Cannot install packages: $packages"
            return 1
            ;;
    esac

    return 0
}

# Function to install Node.js
install_nodejs() {
    local pkg_manager="$1"

    echo "Installing Node.js using $pkg_manager..."

    case "$pkg_manager" in
        apt)
            # Debian/Ubuntu - install more recent Node.js LTS
            install_packages apt "ca-certificates curl gnupg"
            mkdir -p /etc/apt/keyrings
            curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
            echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_18.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list
            apt-get update
            apt-get install -y nodejs
            ;;
        apk)
            # Alpine
            install_packages apk "nodejs npm"
            ;;
        dnf)
            # Fedora/RHEL
            install_packages dnf "nodejs npm"
            ;;
        yum)
            # CentOS/RHEL
            curl -sL https://rpm.nodesource.com/setup_18.x | bash -
            yum install -y nodejs
            ;;
        *)
            echo "ERROR: Unsupported package manager for Node.js installation"
            return 1
            ;;
    esac

    # Verify installation
    if command -v node >/dev/null && command -v npm >/dev/null; then
        echo "Successfully installed Node.js and npm"
        return 0
    else
        echo "Failed to install Node.js and npm"
        return 1
    fi
}

# Function to install Claude Code CLI
install_claude_code() {
    echo "Installing Claude Code CLI globally..."

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
    # $_REMOTE_USER is set by devcontainer, fallback to 'vscode' or current user
    local target_home="${_REMOTE_USER_HOME:-/home/${_REMOTE_USER:-vscode}}"
    local target_user="${_REMOTE_USER:-vscode}"

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

# Print error message about requiring Node.js feature
print_nodejs_requirement() {
    cat <<EOF

ERROR: Node.js and npm are required but could not be installed!
Please add the Node.js feature to your devcontainer.json:

  "features": {
    "ghcr.io/devcontainers/features/node:1": {},
    "./claude-code": {}
  }

EOF
    exit 1
}

# Main script starts here
main() {
    echo "========================================="
    echo "Activating feature 'claude-code' (local)"
    echo "========================================="

    # Detect package manager
    PKG_MANAGER=$(detect_package_manager)
    echo "Detected package manager: $PKG_MANAGER"

    # Check if Node.js and npm are available
    if ! command -v node >/dev/null || ! command -v npm >/dev/null; then
        echo "Node.js or npm not found, attempting to install automatically..."
        install_nodejs "$PKG_MANAGER" || print_nodejs_requirement
    else
        echo "Node.js and npm are already installed"
        node --version
        npm --version
    fi

    # Install Claude Code CLI
    # Check if already installed to make this idempotent
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
