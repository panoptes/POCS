#!/bin/bash -ex

WINDOW="${1}"
DB="${2:-meta}"
echo "Running $(basename "${0}") at $(date), WINDOW=${WINDOW}"
echo "Creating proxy connection to ${DB} database"

tmux send-keys -t "${WINDOW}" "date" C-m
sleep 0.5s
tmux send-keys -t "${WINDOW}" \
     "python $POCS/scripts/connect_clouddb_proxy --database ${DB} --verbose" C-m

echo "Done at $(date)"
