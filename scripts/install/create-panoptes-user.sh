#!/bin/bash -ex
#
# Create the user that will own /var/panoptes and will execute the
# panoptes software. Minimal usage:
#
#    PANUSER=panoptes ./create-panoptes-user.sh
#
# Looks for these environment variables:
#
#      PANUSER: Name of the user to create. Required
#   PANUSER_ID: Id (integer) of the user to create. Not required.
#     PANGROUP: Name of the group to to create for the user. Defaults to PANUSER.
#  PANGROUP_ID: Id (integer) of the group to create. Not required.
# NO_PROMPTING: If not empty, then no prompting for a password or GECOS info is done.

if [ -z "${PANUSER}" ] ; then
  echo "Environment variable PANUSER is not set"
  exit 1
fi

if [ "${PANUSER}" == "$(id -u -n)" ] ; then
  echo "PANUSER (${PANUSER}) is the current user, so already exists."
  exit 0
fi

user_id=$(id -u "${PANUSER}" 2> /dev/null || /bin/true)

if [ -n "$user_id" ] ; then
  echo "PANUSER (${PANUSER}) already exists with UID $user_id."
  exit 1
fi

if [ -n "${PANGROUP}" ] ; then
  # NOT testing if the group exists.
  if [ -n "${PANGROUP_ID}" ] ; then
    # The caller provided a group id.
    addgroup --debug --gid "${PANGROUP_ID}" "${PANGROUP}"
  else
    addgroup --debug "${PANGROUP}"
    PANGROUP_ID=$(id -g "${PANGROUP}")
  fi
elif [ -n "${PANGROUP_ID}" ] ; then
  echo "Specifying only the group id and not group name is not supported."
  exit 1
fi

CMD="adduser --debug"
CMD+=" --home /home/${PANUSER}"
CMD+=" --shell /bin/bash"
CMD+=" --add_extra_groups"
if [ -n "${PANUSER_ID}" ] ; then
  CMD+=" --uid ${PANUSER_ID}"
fi
if [ -n "${PANGROUP}" ] ; then
  CMD+=" --ingroup ${PANGROUP}"
fi
if [ -n "${NO_PASSWORD}" ] ; then
  CMD+=" --disabled-password --gecos ''"
fi

CMD+=" ${PANUSER}"

$CMD