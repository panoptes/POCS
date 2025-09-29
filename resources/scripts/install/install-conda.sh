#!/usr/bin/env bash

CONDA_URL="https://micro.mamba.pm/install.sh"

echo "Installing micromamba"

wget --no-check-certificate "${CONDA_URL}" -O install-micromamba.sh
sh install-micromamba.sh
rm install-micromamba.sh

echo "micromamba activate" >> ~/.bashrc
source ~/.bashrc

~/.local/bin/micromamba shell init -s bash -r ~/micromamba
~/.local/bin/micromamba shell init -s zsh -r ~/micromamba

~/.local/bin/micromamba config append channels conda-forge
~/.local/bin/micromamba config set channel_priority strict

~/.local/bin/micromamba install python=3.12 hatch click=8.2.1 -y

echo "micromamba activate" >> ~/.zshrc

~/.local/bin/micromamba clean --all
