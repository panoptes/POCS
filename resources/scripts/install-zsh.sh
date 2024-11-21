#!/usr/bin/env bash

PANUSER="${PANUSER:-panoptes}"
PANDIR="${PANDIR:-${HOME}/POCS}"

function install_zsh() {
  if [ ! -d "${HOME}/.oh-my-zsh" ]; then
    echo "Using zsh for a better shell experience."

    sudo chsh --shell /usr/bin/zsh "${PANUSER}"

    # Oh my zsh
    wget -q https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh -O /tmp/install-ohmyzsh.sh
    bash /tmp/install-ohmyzsh.sh --unattended

    export ZSH_CUSTOM="$HOME/.oh-my-zsh"

    # Autosuggestions plugin
    git clone https://github.com/zsh-users/zsh-autosuggestions "${ZSH_CUSTOM:-~/.oh-my-zsh/custom}"/plugins/zsh-autosuggestions

    write_zshrc
  fi
}

function write_zshrc() {
  cat >"${HOME}/.zshrc" <<EOT

zstyle ':omz:update' mode disabled

export PATH="\$HOME/bin:\$HOME/.local/bin:/usr/local/bin:\$PATH"
export ZSH="/home/${PANUSER}/.oh-my-zsh"
export PANDIR="${PANDIR}"

ZSH_THEME="agnoster"

plugins=(git sudo zsh-autosuggestions docker docker-compose python)
source \$ZSH/oh-my-zsh.sh
unsetopt share_history

EOT
}

install_zsh
