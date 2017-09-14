#!/bin/bash

# ==============================================
# DDM Nvidia driver installation for Stretch
# ==============================================
# Based on:
# https://wiki.debian.org/NvidiaGraphicsDrivers
# https://wiki.debian.org/Bumblebee
# ==============================================

# Bumblebee packages
BUMBLEBEE='bumblebee-nvidia primus-libs-ia32:i386'

# Additional legacy drivers
ADDITIONALLEGACY='nvidia-settings-legacy-304xx'
ADDITIONALLEGACY64='libgl1-nvidia-legacy-304xx-glx:i386'

# Additional packages
ADDITIONALPCKS="linux-headers-$(uname -r) build-essential firmware-linux-nonfree xserver-xorg-video-intel"

# Purge these in any case
PURGEPCKS='nvidia-xconfig'

# Default value to use backports
BACKPORTS=false

# Additional apt parameters
APTFORCE='--allow-downgrades --allow-remove-essential --allow-change-held-packages'

# Default value for testing
# Set TESTHWCARD to test the script with different hardware.
TEST=false
#TESTHWCARD='NVIDIA Corporation GK104 [GeForce GTX 680] [10de:1180]'
TESTHWCARD='NVIDIA Corporation G80 [GeForce 8800 GTS] [10de:0193]'

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
  echo '-s           Show supported hardware.'
  echo
  echo '-t           For developers: simuluate driver installation.'
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
  echo '[NVIDIA] Cannot get the Debian version from /etc/debian_version.' | tee -a $LOG
  echo '[NVIDIA] Please install the base-files package.' | tee -a $LOG
  exit 8
fi

# Non-numeric values means that it's testing (sid)
if [[ $DISTRIB_RELEASE =~ '^[0-9]+$' ]] ; then
  if [ $DISTRIB_RELEASE -lt 9 ]; then
    echo '[NVIDIA] This script is for Debian Stretch and beyond.' | tee -a $LOG
    exit 0
  fi
fi

# Get device id for Nvidia
BCID='10de'
HWCARDS=`lspci -nn -d $BCID: | egrep -i " 3d | display | vga "`
# Cleanup
HWCARDS="${HWCARDS#*: }"
HWCARDS="${HWCARDS%(rev*}"
# Testing
if $TEST; then
  HWCARDS=$TESTHWCARD
fi
DEVICEIDS=$(echo "$HWCARDS" | grep -Po '(?<=\:)[0-9a-z]*(?=\])')

if [ "$HWCARDS" == '' ]; then
  if ! $SHOW; then
    echo '[NVIDIA] No Nvidia card found.' | tee -a $LOG
  fi
  exit 0
fi

# Try to avoid detecting dual video cards where nvidia is still primary.
# The old method would try to install bumblebee on desktops with nvidia cards and intel integrated on the motherboard
if ! $TEST; then
  apt-get update
fi
# Check for Optimus
if lspci -vnn | grep Intel | grep -q 0300 ; then
  if lspci -vnn | grep NVIDIA | grep -q 0302 ; then
    if ! $SHOW; then
      echo '[NVIDIA] Nvidia Optimus detected.' | tee -a $LOG
    fi
    PCKS=$BUMBLEBEE
    for PCK in $PCKS; do
      if [[ "$PCK" =~ "bumblebee" ]]; then
        CANDIDATE=`env LANG=C apt-cache policy $PCK | grep Candidate | awk '{print $2}' | tr -d ' '`
        break
      fi
    done
  fi
fi
if [ -z $PCKS ]; then
  # Backport?
  BP=''
  if $BACKPORTS; then
    BP=$(get_backports_string nvidia-detect)
  fi
  # Install nvidia-detect
  INSTALLED=$(dpkg-query -l nvidia-detect 2>/dev/null | awk '/^[hi]i/{print $2}')
  if [ "$INSTALLED" == '' ]; then
    apt-get install -qq $BP -y $APTFORCE nvidia-detect 2>&1 | tee -a $LOG
    apt-get install -qq $BP -y $APTFORCE nvidia-installer-cleanup 2>&1 | tee -a $LOG
  fi
  if $TEST; then
    TSTIDS=$DEVICEIDS
  fi
  PCKS=$(nvidia-detect $TSTIDS | grep nvidia- | tr -d ' ' | cut -d'/' -f 1)
  CANDIDATE=`env LANG=C apt-cache policy $PCKS | grep Candidate | awk '{print $2}' | tr -d ' '`
fi

if [ "$PCKS" == '' ] || [ "$CANDIDATE" == '' ]; then
  if ! $SHOW; then
    echo '[NVIDIA] No driver available.' | tee -a $LOG
  fi
  exit 3
fi

# Show supported hardware only
if [ "$HWCARDS" != '' ] && $SHOW; then
  echo "$HWCARDS [$PCKS]"
  exit 0
fi

# Add additional legacy packages
if [[ "$PCKS" =~ "legacy" ]]; then
  # Legacy drivers
  ARCHITECTURE=$(uname -m)
  PCKS="$PCKS $ADDITIONALLEGACY"
  if [ "$ARCHITECTURE" == "x86_64" ]; then
    PCKS="$PCKS $ADDITIONALLEGACY64"
  fi
fi

# Add additional packages
PCKS="$ADDITIONALPCKS $PCKS"

# Check if all these packages exist in the repository
for PCK in $PCKS; do
  PCKINFO=$(apt-cache show "$PCK" 2>/dev/null)
  if [ "$PCKINFO" == '' ]; then
    echo "[NVIDIA] Unable to install $PCK: not in repository."
    exit 7
  fi
done

# Install the Nvidia drivers
if $TEST && ! $FORCE; then
  echo "[NVIDIA] - TEST - Install packages: $PCKS." | tee -a $LOG
  if [ "$PURGEPCKS" != '' ]; then
    echo "[NVIDIA] - TEST - Purge packages: $PURGEPCKS." | tee -a $LOG
  fi
else
  # Preseed debconf answers
  echo 'nvidia-support nvidia-support/check-xorg-conf-on-removal boolean false' | debconf-set-selections
  echo 'nvidia-support nvidia-support/check-running-module-version boolean true' | debconf-set-selections
  echo 'nvidia-installer-cleanup nvidia-installer-cleanup/delete-nvidia-installer boolean true' | debconf-set-selections
  echo 'nvidia-installer-cleanup nvidia-installer-cleanup/remove-conflicting-libraries boolean true' | debconf-set-selections
  echo "nvidia-support nvidia-support/last-mismatching-module-version string $CANDIDATE" | debconf-set-selections
  echo 'nvidia-support nvidia-support/needs-xorg-conf-to-enable note ' | debconf-set-selections
  echo 'nvidia-support nvidia-support/create-nvidia-conf boolean true' | debconf-set-selections
  echo 'nvidia-installer-cleanup nvidia-installer-cleanup/uninstall-nvidia-installer boolean true' | debconf-set-selections
  
  # Install the packages
  for PCK in $PCKS; do
    # Backport?
    BP=''
    if $BACKPORTS; then
      BP=$(get_backports_string $PCK)
    fi
    echo "[NVIDIA] Run command: apt-get install --reinstall $BP -y $APTFORCE $PCK." | tee -a $LOG
    apt-get install --reinstall $BP -y $APTFORCE $PCK 2>&1 | tee -a $LOG
  done
    
  # Purge packages if needed
  for PCK in $PURGEPCKS; do
    echo "[NVIDIA] Run command: apt-get purge -y $APTFORCE $PCK" | tee -a $LOG
    apt-get purge -y $APTFORCE $PCK 2>&1 | tee -a $LOG
  done
    
  # Configure
  if [[ "$PCKS" =~ "bumblebee" ]]; then
    USER=$(logname)
    if [ "$USER" != '' ] && [ "$USER" != "root" ]; then
      echo "[NVIDIA] Set Bumblebee permissions for user: $USER" | tee -a $LOG
      groupadd bumblebee
      groupadd video
      usermod -a -G bumblebee,video $USER
      service bumblebeed restart
      # Adapt nvidia settings
      if [ -f /usr/lib/nvidia/current/nvidia-settings.desktop ]; then
        sed -i 's/Exec=nvidia-settings/Exec=optirun -b none nvidia-settings -c :8/' /usr/lib/nvidia/current/nvidia-settings.desktop
      fi
    else
      echo "[NVIDIA] - ERROR - Unable to configure Bumblebee for user: $USER" | tee -a $LOG
      exit 9
    fi
  fi
    
  echo '[NVIDIA] Nvidia driver installed.' | tee -a $LOG
fi
