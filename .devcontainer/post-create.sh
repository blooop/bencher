#!/usr/bin/env bash
# postCreateCommand for this repo and every repo cut from this template.
#
# It lives in a script rather than inline in devcontainer.json for two reasons:
# the steps below have to differ per repo (not every descendant defines every
# pixi task), and a one-line string in the JSON is a permanent merge-conflict
# surface for children pulling template updates.
set -euo pipefail

# 1. The .pixi volume is created by docker, owned by root.
sudo chown vscode .pixi

# 2. Seed known_hosts for the forge this clone actually uses.
#
# devpod forwards an ssh agent, so auth works without the host's ~/.ssh being
# mounted -- but host identity does not come with it. Without a known_hosts
# entry the first git operation over an ssh remote fails with "Host key
# verification failed": an interactive user gets a yes/no prompt, anything
# non-interactive (a script, an agent, CI in the container) just dies.
host=$(git config --get remote.origin.url 2>/dev/null |
    sed -nE 's#^(ssh://)?git@([^:/]+).*#\2#p') || true
if [ -n "${host:-}" ]; then
    mkdir -p ~/.ssh && chmod 700 ~/.ssh
    touch ~/.ssh/known_hosts && chmod 600 ~/.ssh/known_hosts
    if ! ssh-keygen -F "$host" >/dev/null 2>&1; then
        if scanned=$(ssh-keyscan -T 10 -t rsa,ecdsa,ed25519 "$host" 2>/dev/null) &&
           [ -n "$scanned" ]; then
            printf '%s\n' "$scanned" >> ~/.ssh/known_hosts
            sort -u -o ~/.ssh/known_hosts ~/.ssh/known_hosts
            echo "post-create: seeded known_hosts for $host"
        else
            # Non-fatal: no network at postCreate must not fail container creation.
            echo "post-create: could not reach $host, skipping known_hosts" >&2
        fi
    fi
fi

# 3. The environment itself.
pixi install

# 4. Optional tasks. A descendant that does not define one simply skips it --
# hardcoding `pixi run prek-install` here fails container creation outright with
# exit 127 on every repo that lacks the task, which is most of them.
# `pixi task list` prints to stderr, not stdout -- redirecting it to /dev/null
# silently yields an empty list and skips tasks the repo really does define.
tasks=$(pixi task list --summary 2>&1 | tr ' ,' '\n\n' || true)
for task in prek-install; do
    if grep -qx "$task" <<<"$tasks"; then
        echo "post-create: running '$task'"
        pixi run "$task"
    else
        echo "post-create: no '$task' task in this repo, skipping"
    fi
done
