#!/bin/bash -e

WINDOW="${1}"
echo "Running $(basename "${0}") at $(date), WINDOW=${WINDOW}"

tmux send-keys -t "${WINDOW}" "date" C-m
sleep 0.5s
tmux send-keys -t "${WINDOW}" "cd \"${PAWS}\"" C-m
sleep 0.5s
tmux send-keys -t "${WINDOW}" "python app.py" C-m

echo "Done at $(date)"
