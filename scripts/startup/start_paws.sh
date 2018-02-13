#!/bin/bash -e

WINDOW="${1}"
echo "Running $(basename "${0}") at $(date), WINDOW=${WINDOW}"

# Wait for bash to be ready (not necessary, but makes
# the window look tidier when you attach later).
sleep 1s

tmux send-keys -t "${WINDOW}" "date" C-m
tmux send-keys -t "${WINDOW}" "python $PAWS/app.py" C-m

echo "Done at $(date)"
