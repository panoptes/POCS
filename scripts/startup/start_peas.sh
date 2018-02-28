#!/bin/bash -ex

WINDOW="${1}"
echo "Running $(basename "${0}") at $(date), WINDOW=${WINDOW}"

tmux send-keys -t "${WINDOW}" "date" C-m
sleep 0.5s
tmux send-keys -t "${WINDOW}" "cd ${POCS}" C-m
sleep 0.5s
tmux send-keys -t "${WINDOW}" "bin/peas_shell" C-m
sleep 10s
tmux send-keys -t "${WINDOW}" "display_config" C-m
sleep 1s
tmux send-keys -t "${WINDOW}" "load_environment" C-m
sleep 5s
tmux send-keys -t "${WINDOW}" "load_weather" C-m
sleep 5s
tmux send-keys -t "${WINDOW}" "start" C-m
sleep 20s
tmux send-keys -t "${WINDOW}" "status" C-m
sleep 10s
tmux send-keys -t "${WINDOW}" "last_reading environment" C-m
sleep 10s
tmux send-keys -t "${WINDOW}" "last_reading weather" C-m

echo "Done at $(date)"
