#!/bin/bash -ex

WINDOW="${1}"
echo "Running $(basename "${0}") at $(date), WINDOW=${WINDOW}"

tmux send-keys -t "${WINDOW}" "date" C-m
sleep 0.5s
tmux send-keys -t "${WINDOW}" "cd ${POCS}" C-m
sleep 0.5s
tmux send-keys -t "${WINDOW}" "bin/pocs_shell" C-m
sleep 10s
tmux send-keys -t "${WINDOW}" "setup_pocs" C-m
sleep 20s
tmux send-keys -t "${WINDOW}" "display_config" C-m
sleep 1s
tmux send-keys -t "${WINDOW}" "run_pocs" C-m

echo "Done at $(date)"
