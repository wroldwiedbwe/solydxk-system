#!/bin/bash

# ==============================================
# DDM PAE kernel installation for Stretch
# ==============================================
# ==============================================

# Default value to use backports
BACKPORTS=false

# PAE packages
PAEPCKS='linux-headers-686-pae linux-image-686-pae'

# Additional apt parameters
APTFORCE='--allow-downgrades --allow-remove-essential --allow-change-held-packages'

# Default value for testing
TEST=false

# Default to show supported hardware only
SHOW=false

# ==============================================
# End configuration
# ==============================================

# Log file for traceback
MAX_SIZE_KB=5120
LOG_SIZE_KB=0
LOG=/var/log/solydxk-system.log
LOG2=/var/log/solydxk-system.log.1
if [ -f $LOG ]; then
  LOG_SIZE_KB=$(ls -s $LOG | awk '{print $1}')
  if [ $LOG_SIZE_KB -gt $MAX_SIZE_KB ]; then
    mv -f $LOG $LOG2
  fi
fi

# ==============================================

function get_backports_string() {
  PCK=$1
  local BPSTR=''
  BP=$(grep backports /etc/apt/sources.list /etc/apt/sources.list.d/*.list | grep debian | grep -v 'list:#' | awk '{print $3}')
  if [ "$BP" != '' ]; then
    BP=$(echo $BP | cut -d' ' -f 1)
    PCKCHK=$(apt-cache madison $PCK | grep "$BP")
    if [ "$PCKCHK" != '' ]; then
      BPSTR="-t $BP"
    fi
  fi
  echo $BPSTR
}

# ==============================================

function usage() {
  echo
  echo "Device Driver Manager Help for $(basename $0)"
  echo 
  echo 'The following options are allowed:'
  echo
  echo '-b           Use backported packages when available.'
  echo
  echo '-h           Show this help.'
  echo
  echo '-s           Show supported and available hardware.'
  echo
  echo '-t           For developers: simuluate PAE installation.'
  echo
}

# ==============================================
# ==============================================

# Get bash arguments
FORCE=false
while getopts ':bfhst' opt; do
  case $opt in
    b)
      # Backports
      BACKPORTS=true
      ;;
    f)
      FORCE=true
      ;;
    h)
      usage
      exit 0
      ;;
    s)
      # Show supported hardware
      SHOW=true
      ;;
    t)
      # Testing
      TEST=true
      ;;
    :)
      echo "Option -$OPTARG requires an argument."
      exit 2
      ;;
    *)
      # Unknown error
      echo "Unknown argument $@"
      exit 2
      ;;
  esac
done

# Run this script as root
if [ $UID -ne 0 ] && ! $SHOW; then
  sudo "$0" "$@"
  exit $?
fi

# Get distribution release
if [ -f /etc/debian_version ]; then
  DISTRIB_RELEASE=$(head -n 1 /etc/debian_version 2>/dev/null | sed 's/[a-zA-Z]/0/' | cut -d'.' -f 1)
fi

if [ -z $DISTRIB_RELEASE ]; then
  echo '[PAE] Cannot get the Debian version from /etc/debian_version.' | tee -a $LOG
  echo '[PAE] Please install the base-files package.' | tee -a $LOG
  exit 8
fi

# Non-numeric values means that it's testing (sid)
if [[ $DISTRIB_RELEASE =~ '^[0-9]+$' ]] ; then
  if [ $DISTRIB_RELEASE -lt 9 ]; then
    echo '[PAE] This script is for Debian Stretch and beyond.' | tee -a $LOG
    exit 0
  fi
fi

# Check if system is PAE capable
MACHINE=$(uname -m)
      
if $TEST; then
  MACHINE='i686'
fi

# Install PAE when more than one CPU and not running on 64-bit system
if [ $MACHINE == "i686" ]; then
  if $SHOW; then
    # Just show OS description and drivers
    OS=$(grep DISTRIB_DESCRIPTION /etc/lsb-release 2>/dev/null | awk -F'=' '{print $2}' | sed 's#\"##g')
    if [ "$OS" == '' ]; then
      OS=$(uname -sm)
    fi
    # Need dummy ids or else the gui gets upset
    echo "$OS PAE [pae0:pae0] [$PAEPCKS]"
  else
    if $TEST && ! $FORCE; then
      echo "[PAE] - TEST - Install PAE kernel: $PAEPCKS." | tee -a $LOG
    else
      apt-get update
      # Backport?
      BP=''
      if $BACKPORTS; then
        BP=$(get_backports_string $PCK)
      fi
      echo "[PAE] Run command: apt-get install --reinstall $BP -y $APTFORCE $PCK." | tee -a $LOG
      apt-get install --reinstall $BP -y $APTFORCE $PAEPCKS 2>&1 | tee -a $LOG
    fi
  fi
else
  if ! $SHOW; then
    echo "[PAE] $MACHINE machine: not installing." | tee -a $LOG
  fi
fi
