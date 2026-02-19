#!/usr/bin/env bash

PANDIR="${PANDIR:-${HOME}/POCS}"

function install_zsh() {
  if [ ! -d "${HOME}/.antidote" ]; then
    echo "Using zsh for a better shell experience."

    # Install Antidote plugin manager
    git clone --depth=1 https://github.com/mattmc3/antidote.git "${HOME}/.antidote"

    write_zsh_plugins
    write_zshrc

    # Generate the static plugin file so plugins are actually downloaded
    echo "Downloading zsh plugins..."
    zsh -c "source '${HOME}/.antidote/antidote.zsh' && antidote bundle <'${HOME}/.zsh_plugins.txt' >'${HOME}/.zsh_plugins.zsh'"

    # Configure starship if available
    if command -v starship &>/dev/null; then
      mkdir -p ~/.config
      starship preset plain-text-symbols -o ~/.config/starship.toml
    fi
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

# Initialize zsh completion system before loading plugins
autoload -Uz compinit
compinit

# Antidote plugin manager
source "\${HOME}/.antidote/antidote.zsh"

# Set the name of the static .zsh plugins file antidote will generate.
zsh_plugins="\${HOME}/.zsh_plugins.zsh"

# Ensure you have a .zsh_plugins.txt file where you can add plugins.
zsh_plugins_txt="\${HOME}/.zsh_plugins.txt"

# Lazy-load antidote from its functions directory.
fpath=("\${HOME}/.antidote/functions" \$fpath)
autoload -Uz antidote

# Generate a new static plugins file if it doesn't exist or is outdated.
if [[ ! \$zsh_plugins -nt \$zsh_plugins_txt ]]; then
  antidote bundle <\$zsh_plugins_txt >\$zsh_plugins
fi

# Source the plugins file.
source \$zsh_plugins

# History configuration
HISTFILE="\${HOME}/.zsh_history"
HISTSIZE=10000
SAVEHIST=10000
setopt append_history        # Append to history file instead of replacing
setopt inc_append_history    # Write to history file immediately, not on shell exit
setopt hist_ignore_dups      # Don't record duplicate consecutive commands
setopt hist_ignore_space     # Don't record commands that start with a space
unsetopt share_history       # Don't share history between terminals in real-time

# Starship prompt
if command -v starship &>/dev/null; then
  eval "\$(starship init zsh)"
fi


EOT
}

install_zsh
