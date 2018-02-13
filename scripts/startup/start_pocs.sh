#!/bin/bash

WINDOW="${1}"
echo "Running $(basename "${0}") at $(date), WINDOW=${WINDOW}"

# Wait for bash to be ready (not necessary, but makes
# the window look tidier when you attach later).
sleep 1s

tmux send-keys -t "${WINDOW}" "date" C-m
tmux send-keys -t "${WINDOW}" "cd $POCS" C-m
tmux send-keys -t "${WINDOW}" "bin/pocs_shell" C-m
sleep 10s
tmux send-keys -t "${WINDOW}" "setup_pocs" C-m
sleep 20s
tmux send-keys -t "${WINDOW}" "display_config" C-m
sleep 1s
tmux send-keys -t "${WINDOW}" "run_pocs" C-m

echo "Done at $(date)"
