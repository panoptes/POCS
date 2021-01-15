#!/usr/bin/env bash
set -e

# Pass arguments
exec gosu panoptes /usr/bin/env bash -ic "$@"
