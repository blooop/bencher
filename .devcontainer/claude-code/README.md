# Claude Code CLI - Local Dev Container Feature

A local Dev Container Feature that installs the Claude Code CLI and configures it with read-only mounts to your host machine's Claude configuration.

## What This Feature Does

This feature combines two capabilities:

1. **CLI Installation**: Installs the `@anthropic-ai/claude-code` npm package globally
2. **Configuration Mounting**: Mounts your host machine's Claude configuration files into the container as read-only binds

## What Gets Installed

- **Claude Code CLI**: The `claude` command becomes available in your container
- **VS Code Extension**: Automatically installs the `anthropic.claude-code` extension
- **Configuration Directories**: Creates `.claude/` structure in the container

## What Gets Mounted

The following files and directories from your **host machine** are mounted into the container:

### Read-Only Mounts (Security-Protected)
- `~/.claude/CLAUDE.md` → Global project instructions
- `~/.claude/settings.json` → Claude CLI settings
- `~/.claude/agents/` → Custom agent configurations
- `~/.claude/commands/` → Command definitions
- `~/.claude/hooks/` → Event-driven shell hooks

These are **read-only** (`ro` flag) to prevent:
- Prompt injection attacks that could modify your Claude configuration
- Accidental modification of shared configuration from within containers
- Security issues related to hook manipulation

### Read-Write Mounts (Authentication & State)
- `~/.claude/.credentials.json` → OAuth access/refresh tokens
- `~/.claude/.claude.json` → Account info, user ID, workspace setup tracking

These files **must be writable** to enable:
- OAuth authentication flow and token refresh
- Workspace setup state tracking (`projectOnboardingSeenCount`)
- Session continuity across container rebuilds

### Why These Must Be Writable

**`.credentials.json`**: OAuth tokens need to be refreshed periodically. Claude writes updated tokens to this file.

**`.claude.json`**: Claude tracks per-workspace setup state here. The `projectOnboardingSeenCount` field must be writable so Claude doesn't show the setup wizard on every launch.

⚠️ **Security Note**: These files contain sensitive data and are mounted read-write by necessity. They are only accessible by the container user and stored with `600` permissions. Only use this feature with trusted repositories.

## Usage

### Setup

Add this feature to your `devcontainer.json`:

```json
{
  "features": {
    "./claude-code": {}
  },
  "runArgs": ["--network=host"]
}
```

**Note**: Node.js is automatically installed via the `installsAfter` dependency mechanism - you don't need to explicitly add it to your features.

### Why `--network=host` is Required

The `runArgs: ["--network=host"]` is **critical for OAuth authentication** to work in containers.

**How OAuth works:**
1. You run `claude` → starts OAuth flow
2. Opens browser → you click "Authorize"
3. Browser redirects to `http://localhost:<random-port>/callback`
4. OAuth server running in container receives the callback

**The problem without host networking:**
- OAuth server runs on port X **inside container**
- Browser callback goes to port X on **host's localhost**
- ❌ Container's port is not accessible from host → **callback fails**

**The solution:**
- With `--network=host`, container shares host's network namespace
- OAuth server on port X in container = port X on host
- ✅ Browser callback reaches the container → **authentication succeeds**

**Security note:** Host networking gives the container full network access. Only use in trusted environments.

**Alternative (if host networking is not acceptable):**
- Authenticate Claude on your host machine first
- Credentials in `~/.claude/.credentials.json` are automatically shared with container
- No OAuth flow needed in container

### Build the Container

With DevPod:
```bash
devpod up . --recreate
```

With VS Code:
- Open the folder in VS Code
- Run: "Dev Containers: Rebuild Container"

## Requirements

### Host Machine

You should have these files/directories on your host machine (they will be created if they don't exist):

```bash
~/.claude/
├── CLAUDE.md           # Optional: global instructions
├── settings.json       # Optional: Claude settings
├── agents/             # Optional: custom agents
├── commands/           # Optional: custom commands
└── hooks/              # Optional: event hooks
```

**Note**: If these don't exist on your host, the container will still build successfully, but you may see mount warnings. You can create them with:

```bash
mkdir -p ~/.claude/{agents,commands,hooks}
touch ~/.claude/CLAUDE.md
touch ~/.claude/settings.json
```

### Container

- **Node.js 18+** and **npm** are automatically installed via the `installsAfter` dependency mechanism
- No manual configuration required

## Assumptions

1. **Container User**: This feature assumes the container user is `vscode` (standard for Dev Containers)
   - Configuration files are mounted to `/home/vscode/.claude/`
   - If your container uses a different user (e.g., `root`, `codespace`), you'll need to customize the mounts in your `devcontainer.json`

2. **HOME Environment Variable**: Must be set on the host machine (standard on Unix systems)

3. **Persistence**: Your host machine's `~/.claude/` directory should persist across container rebuilds

4. **Platform**: Designed for Linux/macOS hosts
   - Windows WSL2 should work
   - Windows native may require path adjustments

## How to Iterate Locally

### Quick Changes

1. Edit files in `.devcontainer/claude-code/`:
   - `devcontainer-feature.json` - Change mounts, extensions, or metadata
   - `install.sh` - Modify installation logic
   - `README.md` - Update documentation

2. Rebuild the container:
   ```bash
   devpod up . --recreate
   ```

### Testing Install Script

You can test the install script standalone:

```bash
cd .devcontainer/claude-code
sudo ./install.sh
```

### Debugging

Check if Claude is installed:
```bash
claude --version
```

Check mounted files:
```bash
ls -la ~/.claude/
```

Verify mounts are read-only:
```bash
echo "test" >> ~/.claude/CLAUDE.md  # Should fail with "Read-only file system"
```

## Authentication

### How It Works

1. **Already Authenticated on Host**: If you have Claude Code set up on your host machine, credentials are automatically shared with the container
2. **First-Time Setup**: Run `claude` in the container and follow the OAuth flow:
   - The CLI will provide an OAuth URL
   - Open the URL in your browser (on your host machine)
   - Click "Authorize"
   - The callback should complete automatically, or you may need to paste the code
   - Credentials are saved to `~/.claude/.credentials.json` on your host

### OAuth Callback Behavior

The OAuth flow opens a local callback server. In containers, this can behave differently:
- **VS Code Dev Containers**: Usually handles port forwarding automatically
- **DevPod**: May require manual code pasting if callback doesn't complete
- **SSH/Remote**: Callback URL opens in your local browser

### Troubleshooting Authentication

**"Paste code here" prompt hangs forever:**
- Check that `~/.claude/.credentials.json` exists on your host with proper permissions (`600`)
- Try authenticating on your host machine first, then rebuild the container
- If the callback fails, look for the authorization code in the URL after clicking "Authorize"

**Credentials not persisting:**
- Ensure the `.credentials.json` file exists on your host before rebuilding
- Check file permissions: `chmod 600 ~/.claude/.credentials.json`

**Setup wizard runs on every rebuild (theme selection, OAuth):**

This happens because Claude tracks setup completion **per-workspace**, not globally.

**Quick fix:**
```bash
# On your HOST machine:
# Set the onboarding flag for your workspace
jq '.projects["/workspaces/pythontemplate"].projectOnboardingSeenCount = 1' ~/.claude/.claude.json > ~/.claude/.claude.json.tmp
mv ~/.claude/.claude.json.tmp ~/.claude/.claude.json

# Also ensure themeMode is set (if needed)
jq '. + {themeMode: "dark"}' ~/.claude/.claude.json > ~/.claude/.claude.json.tmp
mv ~/.claude/.claude.json.tmp ~/.claude/.claude.json

# Rebuild container
devpod up . --recreate
```

**Root cause:** Claude tracks setup wizard completion per-workspace in `.claude.json` under `.projects["/workspaces/pythontemplate"].projectOnboardingSeenCount`. When this is `0`, the setup wizard runs. Set it to `1` to mark setup as complete.

**For future workspaces:** Replace `/workspaces/pythontemplate` with your actual container workspace path.

## Modifying Configuration

Configuration files (except credentials) are read-only. You **cannot** modify Claude settings from within the container.

To change configuration:

1. Edit files on your **host machine**: `~/.claude/settings.json`, `~/.claude/CLAUDE.md`, etc.
2. Restart or rebuild the container to see changes

This is by design for security (prevents prompt injection attacks).

## What Would Change Before Publishing to GHCR

If you wanted to publish this feature to GitHub Container Registry later:

### 1. Repository Structure

Move from `.devcontainer/claude-code/` to a dedicated repo:

```
anthropics/devcontainer-features/
└── src/
    └── claude-code/
        ├── devcontainer-feature.json
        ├── install.sh
        └── README.md
```

### 2. Metadata Updates

In `devcontainer-feature.json`:

```json
{
  "id": "claude-code",
  "version": "1.0.0",  // Semantic versioning
  "documentationURL": "https://github.com/anthropics/devcontainer-features/tree/main/src/claude-code",
  // ... rest of config
}
```

### 3. Testing Infrastructure

Add GitHub Actions workflow (`.github/workflows/test.yaml`):

```yaml
- name: "Create test prerequisites"
  run: |
    mkdir -p ~/.claude/agents
    mkdir -p ~/.claude/commands
    mkdir -p ~/.claude/hooks
    touch ~/.claude/settings.json
    touch ~/.claude/CLAUDE.md
```

### 4. Publishing Workflow

Add release workflow to build and push to `ghcr.io/anthropics/devcontainer-features/claude-code:1`

### 5. Reference Change

Users would then reference it as:

```json
{
  "features": {
    "ghcr.io/anthropics/devcontainer-features/claude-code:1": {}
  }
}
```

Instead of `"./claude-code": {}`

## Optional: Future Composition

### Splitting into Modular Features

This feature could be split into:

1. **`claude-code-core`**: Just CLI installation, no mounts
   ```json
   {
     "features": {
       "./claude-code-core": {}
     }
   }
   ```

2. **`claude-code-mounts`**: Just configuration mounts (requires `claude-code-core`)
   ```json
   {
     "features": {
       "./claude-code-core": {},
       "./claude-code-mounts": {}
     }
   }
   ```

Benefits:
- Users can install CLI without mounts (useful for Codespaces or CI)
- More flexible composition
- Easier to maintain and test separately

### Composition with Custom Features

You could create a personal feature that extends this:

```json
// .devcontainer/my-claude-setup/devcontainer-feature.json
{
  "id": "my-claude-setup",
  "installsAfter": ["./claude-code"],
  "customizations": {
    "vscode": {
      "settings": {
        "claude.someCustomSetting": "value"
      }
    }
  }
}
```

Then use both:

```json
{
  "features": {
    "./claude-code": {},
    "./my-claude-setup": {}
  }
}
```

## Troubleshooting

### OAuth callback hangs at "Paste code here"

**Problem**: Browser clicks "Authorize" but container never receives the callback.

**Solution**: Add `--network=host` to your `devcontainer.json`:

```json
{
  "runArgs": ["--network=host"]
}
```

See "Why `--network=host` is Required" section above for details.

### Interactive `claude` asks for authentication but `claude --print` works

**Problem**: You're authenticated (credentials mounted) but interactive mode prompts for login.

**Root cause**: Without `--network=host`, OAuth callbacks can't reach the container.

**Solution**: Add `"runArgs": ["--network=host"]` to devcontainer.json.

### VS Code extensions don't install with `--network=host`

**Known Issue**: [Using runArgs network=host prevents extensions from installing](https://github.com/microsoft/vscode-remote-release/issues/9212)

**Workarounds:**
1. **Rebuild without runArgs first**, let extensions install, then add runArgs (extensions persist)
2. **Authenticate on host**, mount credentials, remove runArgs (no OAuth needed in container)
3. **Manually install extensions** after container starts

### Mount warnings about missing files

**Solution**: Create the directories on your host:

```bash
mkdir -p ~/.claude/{agents,commands,hooks}
touch ~/.claude/CLAUDE.md ~/.claude/settings.json
```

## Security Notes

This implementation makes conscious security trade-offs to enable OAuth authentication and persistent setup state:

### What's Protected (Read-Only Mounts)
- **CLAUDE.md**: Prevents prompt injection attacks that could modify your global instructions
- **settings.json**: Prevents config tampering
- **agents/**, **commands/**, **hooks/**: Prevents malicious code execution through modified hooks

### What's Writable (Necessary Trade-off)
- **`.credentials.json`**: OAuth tokens must be writable for token refresh to work
- **`.claude.json`**: Workspace state must be writable to persist `projectOnboardingSeenCount` and other setup tracking

### Security Mitigations
- Files have `600` permissions (user-only access)
- Only use this feature in **trusted repositories**
- Container user isolation provides some protection
- Writable files are limited to authentication/state only
- All configuration and code execution files remain read-only

### Known Risks
- A malicious process in the container could exfiltrate OAuth tokens from `.credentials.json`
- A malicious process could modify workspace state in `.claude.json`
- **Recommendation**: Only use in repositories you trust, as you would with any dev container configuration

See related security discussions:
- [anthropics/claude-code#4478](https://github.com/anthropics/claude-code/issues/4478)
- [anthropics/claude-code#2350](https://github.com/anthropics/claude-code/issues/2350)
- Original read-only approach: [PR #25](https://github.com/anthropics/devcontainer-features/pull/25)

## Reference

- **Dev Container Features Spec**: https://containers.dev/implementers/features/
- **Local Features**: https://containers.dev/implementers/features/#local-features
- **Based on PR**: https://github.com/anthropics/devcontainer-features/pull/25
- **Upstream Features**: https://github.com/anthropics/devcontainer-features

## License

Based on the Anthropic devcontainer-features repository (MIT License).
