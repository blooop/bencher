# Claude Code Dev Container Feature - Troubleshooting Guide

## Quick Reference

### Files That Must Exist on Host

```bash
~/.claude/
├── .credentials.json    # OAuth tokens (must be writable)
├── .claude.json         # Account info, setup state (must be writable)
├── CLAUDE.md           # Global instructions (read-only)
├── settings.json       # Settings (read-only)
├── agents/             # Custom agents (read-only)
├── commands/           # Custom commands (read-only)
└── hooks/              # Event hooks (read-only)
```

### Critical Configuration in devcontainer.json

```json
{
  "features": {
    "ghcr.io/devcontainers/features/node:1": {},
    "./claude-code": {}
  },
  "runArgs": ["--network=host"],
  "containerEnv": {
    "CLAUDE_CONFIG_DIR": "/home/vscode/.claude",
    "XDG_CONFIG_HOME": "/home/vscode/.config",
    "XDG_CACHE_HOME": "/home/vscode/.cache",
    "XDG_DATA_HOME": "/home/vscode/.local/share"
  }
}
```

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
    "/workspaces/pythontemplate": {
      "projectOnboardingSeenCount": 0  // ← This!
    }
  }
}
```

**Solution:**
```bash
# On HOST machine, set a high count to skip wizard
jq '.projects["/workspaces/pythontemplate"].projectOnboardingSeenCount = 999' \
  ~/.claude/.claude.json > ~/.claude/.claude.json.tmp
mv ~/.claude/.claude.json.tmp ~/.claude/.claude.json

# Also ensure themeMode is set (global setting)
jq '. + {themeMode: "dark"}' ~/.claude/.claude.json > ~/.claude/.claude.json.tmp
mv ~/.claude/.claude.json.tmp ~/.claude/.claude.json

# Rebuild container
devpod up . --recreate
```

**Why 999?** The field is `projectOnboardingSeenCount` - it increments each time you see the wizard. Setting it high tells Claude "this workspace has been onboarded many times, skip the wizard."

**Verification:**
```bash
# In container
devpod ssh pythontemplate
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
Add `--network=host` to devcontainer.json:

```json
{
  "runArgs": ["--network=host"]
}
```

This makes the container share the host's network namespace, so ports inside the container are accessible from the host browser.

**Trade-off:**
Using `--network=host` gives the container full network access and may prevent VS Code extensions from installing (known issue: [#9212](https://github.com/microsoft/vscode-remote-release/issues/9212)).

**Workaround if you can't use --network=host:**
Authenticate on your host machine first, then credentials are shared via mounts.

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
`.credentials.json` or `.claude.json` is not mounted, or is mounted read-only.

**Solution:**

1. **Verify mounts in container:**
   ```bash
   devpod ssh pythontemplate
   mount | grep claude
   ```

   Should show:
   ```
   /dev/... on /home/vscode/.claude/.credentials.json type ext4 (rw,...)
   /dev/... on /home/vscode/.claude/.claude.json type ext4 (rw,...)
   ```

2. **Check files exist on host:**
   ```bash
   ls -la ~/.claude/.credentials.json ~/.claude/.claude.json
   ```

3. **Verify files are writable (not ro):**
   The mounts MUST be read-write for auth to persist.

### Issue 5: "Read-only file system" Error

**Symptoms:**
- Error when trying to write to `~/.claude/CLAUDE.md` or similar
- Operations fail with "Read-only file system"

**Expected Behavior:**
This is intentional! Security files are mounted read-only:
- `CLAUDE.md`, `settings.json`, `agents/`, `commands/`, `hooks/` → Read-only

**Why?**
Prevents prompt injection attacks that could modify your Claude configuration.

**Solution:**
Edit these files on your HOST machine, then restart/rebuild the container.

Only `.credentials.json` and `.claude.json` are read-write (needed for auth and state).

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
# Should show all mounted files/directories

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
cat ~/.claude/.claude.json | jq '.projects["/workspaces/pythontemplate"]'
```

Look for:
- `projectOnboardingSeenCount`: Should be > 0 (e.g., 999)
- Check your actual workspace path matches

### Verify Network Mode

```bash
# On HOST
docker inspect <container-id> | jq '.[0].HostConfig.NetworkMode'
# Should show: "host"
```

## Complete Setup Checklist

When setting up a new workspace:

- [ ] Node.js feature added to devcontainer.json
- [ ] `./claude-code` feature added
- [ ] `runArgs: ["--network=host"]` added
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
    "/workspaces/pythontemplate": {
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

### What's Protected (Read-Only)
- `CLAUDE.md` - Prevents prompt injection
- `settings.json` - Prevents config tampering
- `agents/`, `commands/`, `hooks/` - Prevents malicious modifications

### What's Writable (Necessary Risk)
- `.credentials.json` - OAuth tokens (necessary for auth)
- `.claude.json` - Setup state (necessary to skip wizard)

### Mitigation
- Only use in trusted repositories
- Files have `600` permissions (user-only access)
- Container user isolation
- Regular review of `.claude.json` changes

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
