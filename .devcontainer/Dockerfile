FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04

ARG PIXI_VERSION=v0.75.0

RUN curl -L -o /usr/local/bin/pixi -fsSL --compressed "https://github.com/prefix-dev/pixi/releases/download/${PIXI_VERSION}/pixi-$(uname -m)-unknown-linux-musl" \
    && chmod +x /usr/local/bin/pixi \
    && pixi info

# The base image ships a CA bundle that still trusts emSign ECC Root CA - G3,
# whose intermediates had their keys cracked in October 2026
# (CVE-2026-111943). Ubuntu removed it in ca-certificates 20260816ubuntu0.24.04.1;
# the test fails the build if the apt mirror has not caught up.
RUN apt-get update \
    && apt-get install -y --no-install-recommends --only-upgrade ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && test ! -e /etc/ssl/certs/emSign_ECC_Root_CA_-_G3.pem

# set some user and workdir settings to work nicely with vscode
USER vscode
WORKDIR /home/vscode

RUN echo 'eval "$(pixi completion -s bash)"' >> /home/vscode/.bashrc \
    && echo 'export PATH="$HOME/.pixi/bin:$PATH"' >> /home/vscode/.profile \
    && echo '# Workaround: pixi trampoline fails for bash scripts, so add env bin directly' >> /home/vscode/.profile \
    && echo '[ -d "$HOME/.pixi/envs/claude-shim/bin" ] && export PATH="$HOME/.pixi/envs/claude-shim/bin:$PATH"' >> /home/vscode/.profile

# Create .config/gh so the host's GitHub CLI config mounts cleanly onto it
RUN mkdir -p /home/vscode/.config/gh
