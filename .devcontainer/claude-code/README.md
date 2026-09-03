# Claude Code CLI - Local Dev Container Feature

A local Dev Container Feature that installs the Claude Code CLI and bind-mounts your host machine's Claude configuration directory into the container.

## What This Feature Does

This feature combines two capabilities:

1. **CLI Installation**: `install.sh` runs `pixi global install --channel https://prefix.dev/blooop claude-shim`, and downloads pixi to `/usr/local/bin/pixi` first if the base image does not already carry it
2. **Configuration Mounting**: Bind-mounts your host machine's `~/.claude` directory into the container, read-write

## What Gets Installed

- **Claude Code CLI**: The `claude` command becomes available in your container. It comes from the `claude-shim` package on the `blooop` prefix.dev channel, so that channel is a dependency of this feature. `install.sh` checks only that the pixi trampoline exists -- the binary it points at is downloaded on the first `claude` run.
- **VS Code Extension**: Automatically installs the `anthropic.claude-code` extension
- **Configuration Directories**: `install.sh` creates the `.claude/` tree, though it does so while the image is built -- at runtime the host's bind mount covers it

## What Gets Mounted

One mount, and it is the whole directory:

```
source=${localEnv:HOME}/.claude,target=/home/vscode/.claude,type=bind
```

There is no `ro` flag and no per-file mount. The host and every container of every branch share one `~/.claude`, read-write, so anything running in a container can modify any of it -- `CLAUDE.md`, `settings.json`, `agents/`, `commands/` and `hooks/` included.

### What That Means

`hooks/` and `settings.json` are executed by Claude Code wherever it runs. Content a container writes there therefore runs on the **host**, the next time Claude Code starts on the host, and a `postCreateCommand` from a repository you have not read is enough to put it there.

It is not a confidentiality boundary either: code running in the container holds the live Claude credentials the mount carries, and under `dl` a `GH_TOKEN` with repo and workflow scopes.

### Why It Is Still One Read-Write Directory

Sharing the directory is what makes credentials work across the host and every branch container. `.credentials.json` has to be writable because the access token is short-lived and a refresh has to persist -- a read-only or copied arrangement drifts into a re-auth. `.claude.json` has to be writable because Claude tracks per-workspace onboarding and trust state there, so a container that cannot write it re-onboards on every launch.

Splitting the rest of the directory into separate read-only binds is possible and is not what this feature does today. What the container buys as it stands is reproducible dependencies and non-colliding concurrent work, not safety against hostile code. `blooop/wayfinder`'s `.devcontainer/devcontainer.json` states the same threat model in the comment above its `mounts` block.

## Usage

### Setup

The feature is declared where the image is built, in `.devcontainer/ci/devcontainer.json`:

```json
{
  "build": {
    "dockerfile": "../Dockerfile",
    "context": "."
  },
  "features": {
    "../claude-code": {}
  }
}
```

CI publishes that image, and the `devcontainer.json` every branch launches from pulls it and declares neither `features` nor `runArgs`:

```json
{
  "image": "ghcr.io/blooop/python_template/devcontainer:latest",
  "containerEnv": {
    "CLAUDE_CONFIG_DIR": "/home/vscode/.claude"
  },
  "mounts": [
    "source=${localEnv:HOME}/.claude,target=/home/vscode/.claude,type=bind"
  ]
}
```

Declaring the feature a second time there makes the devcontainer spec build a derived image on the first launch of every branch, reinstalling what the pulled image already carries.

### Authentication Uses Host Credentials, Not Host Networking

No OAuth flow runs inside the container. You authenticate `claude` once on the host, and the `~/.claude` bind mount plus `CLAUDE_CONFIG_DIR=/home/vscode/.claude` point the container at those same credentials, refresh tokens included. Every container of every branch reads them, and nothing has to reach the host's network to do it.

### Why You Might Opt Into `--network=host`

The one thing the bind mount does not give you is the interactive OAuth login *from inside* the container, which needs host networking to complete:

1. You run `claude` → it starts a callback server on a random port in the container
2. Your browser opens the authorize page, you click "Authorize", and it redirects to `http://localhost:<that-port>/callback`
3. On the default bridge network that port belongs to the container, not the host, so the browser cannot reach it and the CLI sits at "Paste code here"

With `--network=host` the container shares the host's network namespace, port X in the container *is* port X on the host, and the callback lands.

Two costs come with it, and they are why this template does not set it:

- **VS Code extensions stop installing**: [vscode-remote-release#9212](https://github.com/microsoft/vscode-remote-release/issues/9212), covered again under Troubleshooting below.
- **Every port the container binds becomes a host port.** A container per branch is the reason these repos are launched with `dl`, and two branch containers on the host's network namespace collide on the first port they share.

Host networking also gives the container full access to the host's network, so only use it in environments you trust.

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

`init-host.sh` runs on the host as the `initializeCommand` and creates `~/.claude` if it is missing. Nothing creates the contents below; they are optional, and the container starts without them:

```bash
~/.claude/
├── CLAUDE.md           # Optional: global instructions
├── settings.json       # Optional: Claude settings
├── agents/             # Optional: custom agents
├── commands/           # Optional: custom commands
└── hooks/              # Optional: event hooks
```

**Note**: The mount is the `~/.claude` directory itself, so a missing subdirectory or file costs nothing at launch. To create them anyway:

```bash
mkdir -p ~/.claude/{agents,commands,hooks}
touch ~/.claude/CLAUDE.md
touch ~/.claude/settings.json
```

### Container

- **pixi**, which the `Dockerfile` installs to `/usr/local/bin/pixi`; `install.sh` downloads it there itself if it is missing
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

You can test the install script standalone, from inside the container:

```bash
cd .devcontainer/claude-code
sudo ./install.sh
```

It resolves its target from `_REMOTE_USER` and `_REMOTE_USER_HOME` and falls back to `vscode`, so on a host with no `/home/vscode` it exits with an error rather than doing anything.

### Debugging

Check if Claude is installed:
```bash
claude --version
```

Check mounted files:
```bash
ls -la ~/.claude/
```

Verify the config directory is mounted, writable, and pointed at:
```bash
env | grep CLAUDE_CONFIG_DIR          # /home/vscode/.claude
mount | grep /home/vscode/.claude     # one bind, rw
touch ~/.claude/.mount-check && rm ~/.claude/.mount-check && echo writable
```

The write test uses a throwaway file on purpose. Do not test the mount by appending to `CLAUDE.md`, `settings.json` or anything under `hooks/`: the mount is read-write, so the write lands on the host's real configuration and is loaded into every later Claude Code session.

## Authentication

### How It Works

1. **Already Authenticated on Host**: If you have Claude Code set up on your host machine, credentials are automatically shared with the container
2. **First-Time Setup**: Run `claude` on the **host** and follow the OAuth flow there:
   - The CLI provides an OAuth URL
   - Open the URL in your browser
   - Click "Authorize"
   - The callback completes, because the CLI and the browser are both on the host
   - Credentials are saved to `~/.claude/.credentials.json`, and the mount carries them into every container

### OAuth Callback Behavior

The OAuth flow opens a local callback server. In containers, this can behave differently:
- **VS Code Dev Containers**: Usually handles port forwarding automatically
- **DevPod**: May require manual code pasting if callback doesn't complete
- **SSH/Remote**: Callback URL opens in your local browser

### Troubleshooting Authentication

**"Paste code here" prompt hangs forever:**
- Check that `~/.claude/.credentials.json` exists on your host with proper permissions (`600`)
- Try authenticating on your host machine first, then restart `claude` in the container -- the mount is live, so no rebuild is needed
- If the callback fails, look for the authorization code in the URL after clicking "Authorize"

**Credentials not persisting:**
- Ensure the `.credentials.json` file exists on your host before rebuilding
- Check file permissions: `chmod 600 ~/.claude/.credentials.json`

**Setup wizard runs on every rebuild (theme selection, OAuth):**

This happens because Claude tracks setup completion **per-workspace**, not globally.

**Quick fix:**
```bash
# On your HOST machine:
# Set the onboarding flag for your workspace (`devpod list` shows its name)
jq '.projects["/workspaces/<workspace>"].projectOnboardingSeenCount = 1' ~/.claude/.claude.json > ~/.claude/.claude.json.tmp
mv ~/.claude/.claude.json.tmp ~/.claude/.claude.json

# Also ensure themeMode is set (if needed)
jq '. + {themeMode: "dark"}' ~/.claude/.claude.json > ~/.claude/.claude.json.tmp
mv ~/.claude/.claude.json.tmp ~/.claude/.claude.json

# Then restart `claude` in the container -- the mount is live, so no rebuild is needed
```

**Root cause:** Claude tracks setup wizard completion per-workspace in `.claude.json` under `.projects["/workspaces/<workspace>"].projectOnboardingSeenCount`. When this is `0`, the setup wizard runs. Set it to `1` to mark setup as complete.

**Finding `<workspace>`:** it is the devpod workspace name, and the container mounts the repo at `/workspaces/<workspace>`. `devpod list` shows the name, and `dl --ls` shows it for workspaces devlaunch created.

## Modifying Configuration

The container writes to the same `~/.claude` as the host, so an edit made in either place is an edit to the one shared configuration.

Editing from the **host** is still the better habit: `~/.claude/settings.json`, `~/.claude/CLAUDE.md` and the rest are yours across every branch container, and a change made on the host is one you meant to make. The mount is live, so restarting `claude` picks up a change -- no rebuild needed.

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

Instead of `"../claude-code": {}`

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

**Solution**: Run `claude` on the host instead and let the container read the credentials it writes to `~/.claude`. If you need the login to happen inside the container, add `--network=host` and accept its costs -- see "Why You Might Opt Into `--network=host`" above.

### Interactive `claude` asks for authentication but `claude --print` works

**Problem**: You're authenticated (credentials mounted) but interactive mode prompts for login.

**Root cause**: Interactive mode tried to start an OAuth flow, which means it found no usable credentials under `CLAUDE_CONFIG_DIR`.

**Solution**: Authenticate on the host so `~/.claude/.credentials.json` holds a live token, and check that `~/.claude` is actually mounted and `CLAUDE_CONFIG_DIR` points at it.

### VS Code extensions don't install with `--network=host`

**Known Issue**: [Using runArgs network=host prevents extensions from installing](https://github.com/microsoft/vscode-remote-release/issues/9212)

**Workarounds:**
1. **Rebuild without runArgs first**, let extensions install, then add runArgs (extensions persist)
2. **Authenticate on host**, mount credentials, remove runArgs (no OAuth needed in container)
3. **Manually install extensions** after container starts

### `~/.claude` missing on the host

**Solution**: The `initializeCommand` (`init-host.sh`) creates it before the container starts. To lay out the rest yourself:

```bash
mkdir -p ~/.claude/{agents,commands,hooks}
touch ~/.claude/CLAUDE.md ~/.claude/settings.json
```

## Security Notes

The whole `~/.claude` directory is bind-mounted read-write as one mount, so nothing in it is held back from the container.

### What Code in the Container Can Read and Write
- **`.credentials.json`**: the live OAuth access and refresh tokens
- **`.claude.json`**: account info, user ID, per-workspace onboarding and trust state
- **`CLAUDE.md`**, **`settings.json`**, **`agents/`**, **`commands/`**, **`hooks/`**: the host's copies, in place

`install.sh` runs when the image is built, so the two `600` credential files it creates live in the image and the bind mount covers them at runtime. Permissions on the host's real files are whatever the host set -- see Issue 6 in TROUBLESHOOTING.md. Nothing here restricts code running inside the container, which runs as the user those files belong to.

### The Consequence Worth Naming
`hooks/` and `settings.json` are executed by Claude Code wherever it runs. Code in the container that writes there gets its content executed on the **host**, the next time Claude Code starts there -- a `postCreateCommand` from a repository you have not read reaches that far. The container also carries the live Claude credentials and, under `dl`, a `GH_TOKEN` with repo and workflow scopes, so it is not a confidentiality boundary either.

### Why It Is Accepted
One shared config directory is what makes auth work across the host and every branch container without a re-auth, and it is why a container never re-onboards. That is the trade; the isolation buys reproducible dependencies and non-colliding concurrent work, not protection from hostile code. `blooop/wayfinder`'s `.devcontainer/devcontainer.json` writes out the same threat model above its `mounts` block. Treat a repository you launch this way as code you are running with your own credentials, because that is what it is.

Whether the non-credential paths should become read-only binds is an open question, not a settled one.

See related security discussions:
- [anthropics/claude-code#4478](https://github.com/anthropics/claude-code/issues/4478)
- [anthropics/claude-code#2350](https://github.com/anthropics/claude-code/issues/2350)
- Per-file read-only approach this feature does not implement: [PR #25](https://github.com/anthropics/devcontainer-features/pull/25)

## Reference

- **Dev Container Features Spec**: https://containers.dev/implementers/features/
- **Local Features**: https://containers.dev/implementers/features/#local-features
- **Based on PR**: https://github.com/anthropics/devcontainer-features/pull/25
- **Upstream Features**: https://github.com/anthropics/devcontainer-features

## License

Based on the Anthropic devcontainer-features repository (MIT License).
