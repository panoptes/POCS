#!/bin/bash -ex

WINDOW="${1}"
echo "Running $(basename "${0}") at $(date), WINDOW=${WINDOW}"

tmux send-keys -t "${WINDOW}" "date" C-m
sleep 0.5s
tmux send-keys -t "${WINDOW}" \
     "python $POCS/scripts/run_social_messaging.py --from_config" C-m

echo "Done at $(date)"
