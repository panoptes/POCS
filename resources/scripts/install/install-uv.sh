#!/usr/bin/env bash

curl -LsSf https://astral.sh/uv/install.sh | sh
echo "export PATH=\$HOME/.local/bin:\$PATH" >> "${HOME}/.zshrc"
echo "export PATH=\$HOME/.local/bin:\$PATH" >> "${HOME}/.bashrc"
