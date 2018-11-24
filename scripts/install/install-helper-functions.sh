#!/bin/bash 
# This file is to be sourced into another to add helper functions, rather than
# executed directly.

#-------------------------------------------------------------------------------
# Logging support (nascent; I want to add more control and a log file).

# Print a separator bar of # characters.
function echo_bar() {
  local terminal_width
  if [ -n "${TERM}" ] && [ -t 0 ] ; then
    if [[ -n "$(which resize)" ]] ; then
      terminal_width="$(resize 2>/dev/null | grep COLUMNS= | cut -d= -f2)"
    elif [[ -n "$(which stty)" ]] ; then
      terminal_width="$(stty size 2>/dev/null | cut '-d ' -f2)"
    fi
  fi
  printf "%${terminal_width:-80}s\n" | tr ' ' '#'
}

function echo_running_sudo() {
  if [ "$(id -u -n)" == "root" ] ; then
    echo "Running $1"
  else
    echo "Running sudo $1; you may be prompted for your password."
  fi
}

#-------------------------------------------------------------------------------
# Misc helper functions.

# Execute the args (a command) as root, either using sudo or directly if already
# running as root.
function my_sudo() {
  if [ "$(id -u -n)" == "root" ] ; then
    "$@"
  else
    (set -x ; sudo "$@")
  fi
}

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

# Match a line that looks like this:
#     8.8.8.8 via 192.168.86.1 dev wlp3s0 src 192.168.86.36 uid 1000
# And extract either the "via" or the "src" address.
# $1 (first and only arge) should be "via" or "src".
function sbin_ip_route_addr() {
  local -r pattern="${1}"
  local cmd
  if [ -x "$(safe_which ip)" ] ; then
    cmd='ip'
  elif [ -x /sbin/ip ] ; then
    cmd='/sbin/ip'
  else
    return 0
  fi
  "${cmd}" route get 8.8.8.8 | awk -F" ${pattern} " 'NR==1{split($2,a," ");print a[1]}'
}

#-------------------------------------------------------------------------------
# Helpers for finding the IP gateway of this device.

# Get the address of the gateway stored in /proc/net/route. Available inside
# a docker container or in Ubuntu 18.04. When executed inside a container,
# the address is that of the host; when executed on the host, the address is
# that of the IP gateway on the lan segment (e.g. the adjacent router).
function proc_net_route_gateway() {
  if [ ! -e /proc/net/route ] ; then
    return 0
  fi
  # This can be done with awk, but that is then much harder to debug.
  # /proc/net/route has contents like this:
  #    Iface Destination Gateway  Flags RefCnt Use Metric Mask     MTU Window IRTT                                                       
  #    eth0  00000000    010011AC 0003  0      0   0      00000000 0   0      0                                                                               
  # We're looking to find a line like the second one, with zero for the destination
  # and the Gateway is the 32-bit hex value for the IPv4 address of the docker host,
  # where the last two characters represent the leading (high) bits of the address.
  local -r -a words=( $(grep -E -i '^[a-z][a-z0-9]+\s00000000\s[0-9a-f][0-9a-f][0-9a-f][0-9a-f]' /proc/net/route ) )
  local -r gateway="${words[2]}"
  local -r a="0x${gateway:6:2}"
  local -r b="0x${gateway:4:2}"
  local -r c="0x${gateway:2:2}"
  local -r d="0x${gateway:0:2}"
  printf "%d.%d.%d.%d\n" "${a}" "${b}" "${c}" "${d}"
}

# Print the address of the first gateway on the route to 8.8.8.8, i.e. to
# Google's public DNS server. Inside a docker container, this will be the
# address of the host. Requires the iproute2 package be installed, which it
# is not by default in an ubuntu-18.04 docker image.
function sbin_ip_gateway() {
  sbin_ip_route_addr via
}

# Try all methods, output all gateway addresses (there could be duplicates).
function get_gateway_ips() {
  proc_net_route_gateway
  sbin_ip_gateway
}

#-------------------------------------------------------------------------------
# Helpers for finding the IP address of this device.

# Get the IP addresses of the host, of which there may be multiple or none.
function hostname_addresses() {
  if [ -x "$(safe_which hostname)" ] ; then
    hostname --all-ip-addresses
  fi
}

# Print the first IP on the route to 8.8.8.8, i.e. to Google's public DNS
# server. Inside a docker container, this will be the address of the container,
# and on a host, this will be the address of one of the interfaces or nothing
# if 'ip' is not installed or there is no interfaces enabled.
# Requires the iproute2 package be installed, which it is not by default in an
# ubuntu-18.04 docker image.
function sbin_ip_host() {
  sbin_ip_route_addr src
}

# Try all methods, output all host addresses (there could be duplicates).
function get_host_ips() {
  hostname_addresses
  sbin_ip_host
}

#-------------------------------------------------------------------------------
# Helpers for finding the APT caching proxy.

# Checks whether $1 (a URL) is for a server that will respond.
# Returns status code:
#    1 if the URL ($1) is invalid
#    $2 if no tool available to check the validity
#    0 otherwise
function check_is_url() {
  local -r url="${1}"
  local -r default_status="${2}"

  # curl supports head requests, exactly what we want.
  if [ -x "$(safe_which curl)" ] ; then
    local -r response_head="$(curl --silent --fail-early --head --max-time 3 "${url}" || /bin/true)"
    if beginswith "${response_head}" "HTTP/" ; then
      return 0
    fi
    echo "curl unable to fetch headers for ${url}" 1>&2
    return 1
  fi

  if [ -x "$(safe_which wget)" ] ; then
    (set +e ; wget --quiet --spider --tries 1 "${url}")
    case $? in
      0|6|8)  # No error, auth failure or HTTP error.
        return 0
        ;;
      *)
        echo "wget unable to fetch headers for ${url}" 1>&2
        return 1
    esac
  fi

  return "${default_status}"
}

# Print the URL for the APT caching proxy. Looks for the port to use as
# the first arg (if any are provided), else the APT_PROXY_PORT environment
# variable; if neither is set, then no URL is printed.
# If curl is available, it is used to test whether the URL is valid, but if
# not then the URL is assumed valid.
function get_apt_proxy_url() {
  local -r apt_proxy_port="${1:-${APT_PROXY_PORT}}"
  if [ -z "${apt_proxy_port}" ] ; then
    cat <<EOF 1>&2
No apt cache proxy declared via APT_PROXY_PORT or script argument.
EOF
    return 0
  fi
  # echo "APT_PROXY_PORT: ${apt_proxy_port}" 1>&2

  local -a addresses
  if grep ':/docker/' /proc/1/cgroup -qa; then
    # Running inside docker, so look for the proxy on the docker host first,
    # then inside the container.
    addresses+=($(get_gateway_ips))
    addresses+=(localhost)
    addresses+=($(get_host_ips))
  else
    # Not running inside docker, so look on this host only.
    addresses+=($(get_host_ips))
    addresses+=(localhost)
  fi

  # See if we can connect to a webserver at our address and the apt proxy port.
  local -A tested_addresses
  for address in "${addresses[@]}" ; do
    if [ -z "${address}" ] ; then
      continue
    fi
    # Don't waste time trying to connect to an address we already checked.
    if [ -n "${tested_addresses["${address}"]}" ] ; then
      # This address is a duplicate.
      continue
    fi
    tested_addresses["${address}"]="seen"

    local apt_proxy_url="http://${address}:${apt_proxy_port}"
    if check_is_url "${apt_proxy_url}" 0 ; then
      echo "${apt_proxy_url}"
      return 0
    fi
  done
}
