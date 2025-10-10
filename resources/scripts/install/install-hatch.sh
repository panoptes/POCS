#!/usr/bin/env bash

pipx install hatch >> install.log 2>&1
echo "export PATH=\$HOME/.local/bin:\$PATH" >> "${HOME}/.zshrc"
echo "export PATH=\$HOME/.local/bin:\$PATH" >> "${HOME}/.bashrc"
source "${HOME}/.bashrc"
