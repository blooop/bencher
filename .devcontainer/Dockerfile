FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04

ARG PIXI_VERSION=v0.62.2

RUN curl -L -o /usr/local/bin/pixi -fsSL --compressed "https://github.com/prefix-dev/pixi/releases/download/${PIXI_VERSION}/pixi-$(uname -m)-unknown-linux-musl" \
    && chmod +x /usr/local/bin/pixi \
    && pixi info

# set some user and workdir settings to work nicely with vscode
USER vscode
WORKDIR /home/vscode

RUN echo 'eval "$(pixi completion -s bash)"' >> /home/vscode/.bashrc \
    && echo 'export PATH="$HOME/.pixi/bin:$PATH"' >> /home/vscode/.profile \
    && echo '# Workaround: pixi trampoline fails for bash scripts, so add env bin directly' >> /home/vscode/.profile \
    && echo '[ -d "$HOME/.pixi/envs/claude-shim/bin" ] && export PATH="$HOME/.pixi/envs/claude-shim/bin:$PATH"' >> /home/vscode/.profile

# Create .ssh directory with proper permissions for SSH config mounts
RUN mkdir -p /home/vscode/.ssh && chmod 700 /home/vscode/.ssh
