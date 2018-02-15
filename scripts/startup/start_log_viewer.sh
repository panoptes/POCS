#!/bin/bash -ex

WINDOW="${1}"
LOGFILE="${2}"
echo "Running $(basename "${0}") at $(date), WINDOW=${WINDOW}, LOGFILE=${LOGFILE}"

# Wait for bash to be ready (not necessary, but makes
# the window look tidier when you attach later).
sleep 1s

tmux send-keys -t "${WINDOW}" "date" C-m
tmux send-keys -t "${WINDOW}" "cd \"${PANLOG}\"" C-m
tmux send-keys -t "${WINDOW}" "less --follow-name \"${LOGFILE}\"" C-m
sleep 2s
tmux send-keys -t "${WINDOW}" "F"

echo "Done at $(date)"
