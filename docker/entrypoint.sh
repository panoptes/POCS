#!/bin/bash -e

# Authenticate if key has been set
if [ ! -z "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    echo "Found Google credentials, activating service account"
	gcloud auth activate-service-account --key-file=$GOOGLE_APPLICATION_CREDENTIALS
fi

# Pass arguments
exec "$@"
