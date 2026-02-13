#!/usr/bin/env bash

PANDIR="${PANDIR:-${HOME}/POCS}"

function install_zsh() {
  if [ ! -d "${HOME}/.antidote" ]; then
    echo "Using zsh for a better shell experience."

    # Install Antidote plugin manager
    git clone --depth=1 https://github.com/mattmc3/antidote.git "${HOME}/.antidote"

    write_zsh_plugins
    write_zshrc

    starship preset plain-text-symbols -o ~/.config/starship.toml
  fi
}

function write_zsh_plugins() {
  cat >"${HOME}/.zsh_plugins.txt" <<EOT
# oh-my-zsh plugins
ohmyzsh/ohmyzsh path:plugins/git
ohmyzsh/ohmyzsh path:plugins/sudo
ohmyzsh/ohmyzsh path:plugins/docker
ohmyzsh/ohmyzsh path:plugins/docker-compose
ohmyzsh/ohmyzsh path:plugins/python

# zsh-users plugins
zsh-users/zsh-autosuggestions
zsh-users/zsh-syntax-highlighting

EOT
}

function write_zshrc() {
  cat >"${HOME}/.zshrc" <<EOT

export PATH="\$HOME/bin:\$HOME/.local/bin:/usr/local/bin:\$PATH"
export PANDIR="${PANDIR}"

# Antidote plugin manager
source "\${HOME}/.antidote/antidote.zsh"
antidote load "\${HOME}/.zsh_plugins.txt"

# Starship prompt
eval "\$(starship init zsh)"

# Disable share_history
unsetopt share_history

EOT
}

install_zsh
