# Claude Code Dev Container Feature - Troubleshooting Guide

## Quick Reference

### Files on the Host

`init-host.sh` creates `~/.claude` as the `initializeCommand`. Everything inside it is optional, and only `.credentials.json` is load-bearing for an authenticated `claude`.

```bash
~/.claude/               # one bind mount, read-write, shared with every container
├── .credentials.json    # OAuth tokens
├── .claude.json         # Account info, setup state
├── CLAUDE.md            # Global instructions
├── settings.json        # Settings
├── agents/              # Custom agents
├── commands/            # Custom commands
└── hooks/               # Event hooks
```

Every one of these is writable from inside the container, and a write lands on the host. See "Security Considerations" below for what follows from that.

### Critical Configuration in devcontainer.json

```json
{
  "image": "ghcr.io/blooop/python_template/devcontainer:latest",
  "containerEnv": {
    "CLAUDE_CONFIG_DIR": "/home/vscode/.claude",
    "XDG_CONFIG_HOME": "/home/vscode/.config",
    "XDG_CACHE_HOME": "/home/vscode/.cache",
    "XDG_DATA_HOME": "/home/vscode/.local/share"
  },
  "mounts": [
    "source=${localEnv:HOME}/.claude,target=/home/vscode/.claude,type=bind"
  ]
}
```

The `../claude-code` feature is declared in `.devcontainer/ci/devcontainer.json`, the config CI builds the image from, so there is no `features` block here -- and no `runArgs` either.

## Common Issues and Solutions

### Issue 1: Setup Wizard Runs on Every Container Rebuild

**Symptoms:**
- Interactive `claude` shows theme selection screen
- After selecting theme, asks for OAuth authentication
- Happens every time you rebuild the container

**Root Cause:**
Claude tracks setup completion per-workspace in `.claude.json`:
```json
{
  "projects": {
    "/workspaces/<workspace>": {
      "projectOnboardingSeenCount": 0  // ← This!
    }
  }
}
```

`<workspace>` is the devpod workspace name -- `devpod list` shows it, and `dl --ls` shows it for workspaces devlaunch created.

**Solution:**
```bash
# On HOST machine, set a high count to skip wizard
jq '.projects["/workspaces/<workspace>"].projectOnboardingSeenCount = 999' \
  ~/.claude/.claude.json > ~/.claude/.claude.json.tmp
mv ~/.claude/.claude.json.tmp ~/.claude/.claude.json

# Also ensure themeMode is set (global setting)
jq '. + {themeMode: "dark"}' ~/.claude/.claude.json > ~/.claude/.claude.json.tmp
mv ~/.claude/.claude.json.tmp ~/.claude/.claude.json

# Then restart `claude` in the container -- the mount is live, so no rebuild is needed
```

**Why 999?** The field is `projectOnboardingSeenCount` - it increments each time you see the wizard. Setting it high tells Claude "this workspace has been onboarded many times, skip the wizard."

**Verification:**
```bash
# From the host, shell into the container
devpod ssh <workspace>
claude  # Should go straight to interactive mode without wizard
```

### Issue 2: OAuth Callback Hangs at "Paste code here"

**Symptoms:**
- Browser opens, you click "Authorize"
- CLI shows "Paste code here >" and waits forever
- Browser callback URL fails to connect

**Root Cause:**
OAuth callback server runs inside container on a random port (e.g., `localhost:35673`). Your browser tries to connect to that port on the HOST, but the container's port isn't accessible.

**Solution:**
Authenticate on the host, where the browser can reach the callback port, and let the container read the resulting credentials through the `~/.claude` bind mount. No OAuth flow then runs in the container at all.

**Alternative, if you want the login to happen inside the container:**
Add `--network=host` to devcontainer.json:

```json
{
  "runArgs": ["--network=host"]
}
```

This makes the container share the host's network namespace, so ports inside the container are accessible from the host browser.

**What that costs:**
VS Code extensions stop installing (known issue: [#9212](https://github.com/microsoft/vscode-remote-release/issues/9212)), the container gets full access to the host's network, and every port the container binds becomes a host port -- so two branch containers of the same repo collide on the first port they share.

### Issue 3: `claude --print` Works But Interactive `claude` Asks for Login

**Symptoms:**
- `echo "test" | claude --print` works without authentication
- Running just `claude` shows setup wizard or login prompt

**Root Cause:**
Two different issues:
1. **Setup wizard** (theme/onboarding) - see Issue 1
2. **Print mode skips workspace trust dialogs** - expected behavior

**Solution:**
- For setup wizard: See Issue 1
- For workspace trust: Use `--dangerously-skip-permissions` in trusted containers

### Issue 4: Authentication Doesn't Persist After Container Rebuild

**Symptoms:**
- You authenticate in the container
- Rebuild the container
- Have to authenticate again

**Root Cause:**
`~/.claude` is not mounted, so `claude` wrote its credentials into the container's own filesystem and they went away with the container.

**Solution:**

1. **Verify the mount in the container:**
   ```bash
   # From the host, shell into the container (`devpod list` shows `<workspace>`,
   # `dl --ls` for workspaces devlaunch created)
   devpod ssh <workspace>
   mount | grep claude
   ```

   Should show one bind of the directory, read-write:
   ```
   /dev/... on /home/vscode/.claude type ext4 (rw,...)
   ```

2. **Check files exist on host:**
   ```bash
   ls -la ~/.claude/.credentials.json ~/.claude/.claude.json
   ```

3. **Check the mount is read-write:**
   A refresh has to persist, so `rw` in the line above is load-bearing. The feature declares no `ro` flag, so a read-only mount means something outside it added one.

### Issue 5: A Container Changed the Host's Claude Configuration

**Symptoms:**
- `~/.claude/CLAUDE.md`, `settings.json` or a file under `hooks/` differs from what you left on the host
- A hook or setting you did not write takes effect when you start `claude` on the host

**Root Cause:**
Not a malfunction. `~/.claude` is one read-write bind of the whole directory, so the host and every container share it and anything in a container can write any of it. `hooks/` and `settings.json` are executed by Claude Code wherever it runs, so what a container leaves there runs on the host next time.

**Solution:**
Restore the files from wherever your configuration lives -- keeping `~/.claude` under version control is what makes a change like this visible and reversible. Then look at what put it there: a `postCreateCommand`, a hook, or an agent session in the container all reach that far.

### Issue 6: File Permission Errors (600 vs 664)

**Symptoms:**
- Cannot read credentials file
- Permission denied errors

**Solution:**
```bash
# On HOST
chmod 600 ~/.claude/.credentials.json
chmod 600 ~/.claude/.claude.json
```

These files contain sensitive data and should only be readable by you.

## Debugging Commands

### Check Authentication Status

```bash
# In container
cat ~/.claude/.credentials.json | jq '.claudeAiOauth.accessToken' | head -c 30
# Should show: sk-ant-oat01-...

cat ~/.claude/.claude.json | jq '.oauthAccount.emailAddress'
# Should show your email
```

### Verify Mounts

```bash
# In container
mount | grep claude
# Should show one bind of /home/vscode/.claude, rw

ls -la ~/.claude/
# Should show files from your host
```

### Check Environment Variables

```bash
# In container
env | grep -E "(CLAUDE|XDG)" | sort
```

Should show:
```
CLAUDE_CONFIG_DIR=/home/vscode/.claude
XDG_CACHE_HOME=/home/vscode/.cache
XDG_CONFIG_HOME=/home/vscode/.config
XDG_DATA_HOME=/home/vscode/.local/share
```

### Test Claude Without Authentication

```bash
# This should work if you're authenticated
echo "what is 2+2" | claude --print
```

### Check Setup State

```bash
# On HOST
cat ~/.claude/.claude.json | jq '.projects["/workspaces/<workspace>"]'
```

Look for:
- `projectOnboardingSeenCount`: Should be > 0 (e.g., 999)
- Check your actual workspace path matches

### Verify Network Mode

```bash
# On HOST
docker inspect <container-id> | jq '.[0].HostConfig.NetworkMode'
# "host" only if you opted into --network=host; otherwise the default bridge network
```

## Complete Setup Checklist

When setting up a new workspace:

- [ ] `../claude-code` feature declared in `.devcontainer/ci/devcontainer.json`, so the published image carries it
- [ ] `claude` authenticated on the host, so no OAuth flow runs in the container
- [ ] Environment variables added (CLAUDE_CONFIG_DIR, XDG_*)
- [ ] Files exist on host: `.credentials.json`, `.claude.json`
- [ ] File permissions: `chmod 600` on sensitive files
- [ ] `projectOnboardingSeenCount` set to 999 in `.claude.json`
- [ ] `themeMode` set (e.g., "dark") in `.claude.json`
- [ ] Container rebuilt: `devpod up . --recreate`
- [ ] Test: `claude --print "test"` works
- [ ] Test: `claude` goes to interactive mode without wizard

## File Explanation

### `.credentials.json`
Contains OAuth access and refresh tokens. Format:
```json
{
  "claudeAiOauth": {
    "accessToken": "sk-ant-oat01-...",
    "refreshToken": "sk-ant-ort01-...",
    "expiresAt": 1234567890000
  }
}
```

**Why writable:** Tokens need to be refreshed periodically.

### `.claude.json`
Contains account info, feature flags, and per-workspace state. Key fields:
```json
{
  "oauthAccount": { ... },
  "userID": "...",
  "themeMode": "dark",
  "projects": {
    "/workspaces/<workspace>": {
      "projectOnboardingSeenCount": 999,
      "hasTrustDialogAccepted": false,
      ...
    }
  }
}
```

**Why writable:** Claude updates `projectOnboardingSeenCount` and other workspace state.

## Advanced Debugging

### Capture Complete Claude Startup

```bash
# In container
script -qec "timeout 3 claude 2>&1" /tmp/claude-startup.log
cat /tmp/claude-startup.log
```

### Compare Config Before/After

```bash
# Before operation
cp ~/.claude/.claude.json ~/.claude/.claude.json.before

# Do operation (e.g., run claude)

# After
diff <(jq -S . ~/.claude/.claude.json.before) <(jq -S . ~/.claude/.claude.json)
```

### Check What Changed on Host

```bash
# On HOST, monitor file changes
watch -n 1 'stat ~/.claude/.claude.json | grep Modify'
```

## Security Considerations

### What the Mount Actually Is
One read-write bind of the whole `~/.claude` directory. No `ro` flag, no per-file mounts. `.credentials.json`, `.claude.json`, `CLAUDE.md`, `settings.json`, `agents/`, `commands/` and `hooks/` are all writable from inside the container, and a write lands on the host's copy.

### The Consequence
`hooks/` and `settings.json` are executed by Claude Code wherever it runs, so content a container writes there runs on the **host** the next time Claude Code starts there -- a `postCreateCommand` from a repository nobody read is enough. The container also holds the live Claude credentials from the mount and, under `dl`, a `GH_TOKEN` carrying repo and workflow scopes. It is not a confidentiality or integrity boundary.

### Why It Is Accepted
Sharing one config directory is what makes credentials work across the host and every branch container: the access token is short-lived, so a read-only or copied arrangement drifts into a re-auth, and a container that cannot write `.claude.json` re-onboards on every launch. The isolation buys reproducible dependencies and non-colliding concurrent work, not safety against hostile code. `blooop/wayfinder`'s `.devcontainer/devcontainer.json` writes out the same threat model above its `mounts` block.

Keeping `~/.claude` under version control is the one practical measure here: it makes a change from a container visible instead of silent.

## Known Limitations

1. **VS Code extensions may not install with --network=host**
   - Issue: https://github.com/microsoft/vscode-remote-release/issues/9212
   - Workaround: Build without runArgs first, then add it

2. **Per-workspace setup tracking**
   - Each workspace path needs its own `projectOnboardingSeenCount`
   - Renaming workspace requires updating the flag

3. **No credential isolation**
   - All containers share same host credentials
   - Can't use different Claude accounts per container

4. **OAuth callback browser routing**
   - Requires `--network=host` or manual code pasting
   - May not work in some network environments

## Getting Help

If issues persist:

1. Check `/tmp/claude/debug.log` in container
2. Run `claude --debug` for verbose output
3. Review this guide with an AI agent:
   - Share: `.devcontainer/claude-code/TROUBLESHOOTING.md`
   - Include: Output of debugging commands above
   - Describe: Exact symptoms and when they occur

## References

- Dev Container Features: https://containers.dev/implementers/features/
- Claude Code Docs: https://code.claude.com/docs/
- deps_rocker reference: https://github.com/blooop/deps_rocker
- OAuth callback issue: https://github.com/anthropics/claude-code/issues/1529
- Network=host issue: https://github.com/microsoft/vscode-remote-release/issues/9212
