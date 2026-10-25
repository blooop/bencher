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

# 3. The environment itself, installed from the committed lock as it stands.
#
# --frozen, because a plain `pixi install` lets the image's pixi rewrite
# pixi.lock -- pixi 0.83 turns a version-6 lock into version 7 -- and a clone
# that is dirty before anyone has touched it makes `dl rm` refuse it as
# unsaved work. --locked is not the answer either: it fails container creation
# whenever the lock's format is older than this pixi writes. To change
# dependencies, run `pixi install` (or `pixi add`) yourself and commit the lock.
pixi install --frozen

# 4. Optional tasks. A descendant that does not define one simply skips it --
# hardcoding `pixi run prek-install` here fails container creation outright with
# exit 127 on every repo that lacks the task, which is most of them. This list is
# the one place a child repo adds its own; it stays an array so adding a second
# entry is a one-word edit.
optional_tasks=(prek-install)

# `pixi task list` prints to stderr, not stdout -- redirecting it to /dev/null
# silently yields an empty list and skips tasks the repo really does define. The
# summary is `<env> (by design): a, b, c` per line, so split on both separators
# to get one task per line (tr pads the shorter set2 out to match set1).
tasks=$(pixi task list --summary 2>&1 | tr ' ,' '\n' || true)
for task in "${optional_tasks[@]}"; do
    if grep -qx "$task" <<<"$tasks"; then
        echo "post-create: running '$task'"
        pixi run --frozen "$task"
    else
        echo "post-create: no '$task' task in this repo, skipping"
    fi
done
