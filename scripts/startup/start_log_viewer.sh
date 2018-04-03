#!/bin/bash -ex

WINDOW="${1}"
LOGFILE="${2}"
echo "Running $(basename "${0}") at $(date), WINDOW=${WINDOW}, LOGFILE=${LOGFILE}"

tmux send-keys -t "${WINDOW}" "date" C-m
sleep 0.5s
tmux send-keys -t "${WINDOW}" "cd \"${PANLOG}\"" C-m
sleep 0.5s
tmux send-keys -t "${WINDOW}" "while [[ ! -f \"${LOGFILE}\" ]] ; do echo \"Waiting for ${LOGFILE} to exist\" ; sleep 1s ; done" C-m
sleep 2s
tmux send-keys -t "${WINDOW}" "less --follow-name \"${LOGFILE}\"" C-m
sleep 2s
tmux send-keys -t "${WINDOW}" "F"

echo "Done at $(date)"
