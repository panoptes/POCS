#!/usr/bin/env bash
set -e

# Pass arguments
exec gosu pocs-user /usr/bin/env bash -ic "$@"
