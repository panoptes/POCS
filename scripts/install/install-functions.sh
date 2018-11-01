# This file is to be sourced into another to add helper functions.


#-------------------------------------------------------------------------------
# Logging support (nascent; I want to add more control and a log file).

# Print a separator bar of # characters.
function echo_bar() {
  local terminal_width
  if [[ -n "$(which resize)" ]] ; then
    terminal_width="$(resize|grep COLUMNS=|cut -d= -f2)"
  elif [[ -n "$(which stty)" ]] ; then
    terminal_width="$(stty size | cut '-d ' -f2)"
  fi
  printf "%${terminal_width:-80}s\n" | tr ' ' '#'
}

function echo_running_sudo() {
  if [ "$(whoami)" == "root" ] ; then
    echo "Running $1"
  else
    echo "Running sudo $1; you may be prompted for your password."
  fi
}

function my_sudo() {
  if [ "$(whoami)" == "root" ] ; then
    "$@"
  else
    (set -x ; sudo "$@")
  fi
}

#-------------------------------------------------------------------------------
# Misc helper functions.

# Get the type of the first arg, i.e. shell function, executable, etc.
# For more info: https://ss64.com/bash/type.html
#            or: https://bash.cyberciti.biz/guide/Type_command
function safe_type() {
  type -t "${1}" || /bin/true
}

# Print the disk location of the first arg.
function safe_which() {
  type -p "${1}" || /bin/true
}

# Does the first arg start with the second arg?
function beginswith() { case "${1}" in "${2}"*) true;; *) false;; esac; }
