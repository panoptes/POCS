#!/bin/bash -e
# Install the Google Cloud SDK. This requires that we "teach" apt-get where
# to find the repository where the SDK is located.

THIS_DIR="$(dirname "$(readlink -f "${0}")")"
THIS_PROGRAM="$(basename "${0}")"

# shellcheck source=/var/panoptes/POCS/scripts/install/install-helper-functions.sh
source "${THIS_DIR}/install-helper-functions.sh"

echo_bar

if [ -n "$(safe_which gcloud)" ]
then
  echo "Google Cloud SDK (gcloud command) is already installed"
  exit
fi

if [ -z "$(safe_which lsb_release)" ]
then
  echo 2> "
Unable to determine the release. Is this OS really Debian or Ubuntu?
"
  exit 1
fi

CLOUD_SDK_REPO="cloud-sdk-$(lsb_release -c -s)"
echo "
Setting Google Cloud SDK repository location to:

   ${CLOUD_SDK_REPO}

You may be prompted for your password.
"
echo "deb http://packages.cloud.google.com/apt $CLOUD_SDK_REPO main" | \
    my_sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list | \
    cat >/dev/null

echo "
Importing the public key of that repository.
"
wget --quiet -O - https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -

echo "
Updating the package list (i.e. fetching from the new repository).
"
my_sudo apt-get --quiet update

echo "
Installing the Google Cloud SDK.
"
my_sudo apt-get --quiet install google-cloud-sdk


echo_bar
echo "
You'll now need to run [gcloud init] to set your credentials.
"
