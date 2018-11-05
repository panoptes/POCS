#!/bin/bash -ex

mkdir -p $PANDIR

# If appropriate, create a user to own $PANDIR

if [ $PANUSER != root ] ; then
  if [ $PANUSER != $user_name ] ; then 
    echo "PANUSER ($PANUSER) doesn't match user_name ($user_name)"
    exit 1
  fi
  if [ -z $group_name ] ; then
    echo "group_name is not set!"
    exit 1
  fi
  if [ -z $group_id ] ; then
    echo "group_id is not set!"
    exit 1
  fi

  groupadd -g $group_id $group_name

  if [ -z $user_name ] ; then
    echo "user_name is not set!"
    exit 1
  fi
  if [ -z $user_id ] ; then
    echo "user_id is not set!"
    exit 1
  fi

  useradd -u $user_id -g $group_id -m -d /home/$user_name -s /bin/bash $user_name

  chown -R $user_id:$group_id $PANDIR
fi


  echo_bar
  echo
  echo "Installing miniconda. License at: https://conda.io/docs/license.html"
  local -r the_script="${PANDIR}/tmp/miniconda.sh"
  mkdir -p "$(dirname "${the_script}")"
  wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh \
       -O "${the_script}"
  bash "${the_script}" -b -p "${CONDA_INSTALL_DIR}"
  rm "${the_script}"



declare -a PACKAGES=(
  # Package description...
)

if [ ${#PACKAGES[@]} -ne 0 ] ; then
  echo "Installing extra packages."

  # Suppress prompting for input during package processing.
  export DEBIAN_FRONTEND=noninteractive

  # Update the information we know about package versions.
  apt-get update --fix-missing

  apt-get install --no-install-recommends --yes "${PACKAGES[@]}"

  # Docker best practices calls for cleaning the apt cache before
  # the end of this RUN so that it is not stored in the image.
  rm -rf /var/lib/apt/lists/*
else
  echo "No extra packages are listed."
fi
