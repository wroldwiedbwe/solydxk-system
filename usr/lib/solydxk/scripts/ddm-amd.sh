#!/bin/bash

# ==============================================
# DDM AMD driver installation for Stretch
# ==============================================
# Based on: https://wiki.debian.org/AtiHowTo
# ==============================================

# New supported cards (GCN): https://en.wikipedia.org/wiki/Graphics_Core_Next
SUPPORTEDCARDS='Tonga,Iceland,Topaz,Carrizo,Fiji,Grenada,Antigua,Trinidad,Tobago,Stoney,Bristol,Polaris,Bonaire,Temash,Liverpool,Durango,Kabini,Mullins,Kaveri,Godavari,Beema,Hawaii,Cape Verde,Pitcairn,Tahiti,Oland,Hainan,Raven,Navi,New Zealand,Malta'

# Default value to use backports
BACKPORTS=false

# Old AMD packages
OLDAMD='xserver-xorg-video-ati xserver-xorg-video-radeon xserver-xorg-video-r128 xserver-xorg-video-mach64'

# New AMD
NEWAMD='xserver-xorg-video-amdgpu'

# Additional packages
ADDITIONALPCKS="linux-headers-$(uname -r) build-essential firmware-linux-nonfree"

# Purge these in any case
PURGEPCKS='fglrx* libgl1-fglrx-glx* amd-opencl-icd'

# Additional apt parameters
APTFORCE='--allow-downgrades --allow-remove-essential --allow-change-held-packages'

# Default value for testing
# Set TESTHWCARD to test the script with different AMD/ATI hardware.
TEST=false
#TESTHWCARD='Advanced Micro Devices, Inc. [AMD/ATI] Bonaire [FirePro W5100]'
#TESTHWCARD='Advanced Micro Devices, Inc. [AMD/ATI] RS780L [Radeon 3000]'
#TESTHWCARD='Advanced Micro Devices, Inc. [AMD/ATI] Tonga PRO [Radeon R9 285]'
#TESTHWCARD='Advanced Micro Devices, Inc. [AMD/ATI] RV710 [Radeon HD 4350/4550'
#TESTHWCARD='Advanced Micro Devices [AMD/ATI] Tobago PRO [Radeon R7 360 / R9 360 OEM]'
TESTHWCARD='Advanced Micro Devices, Inc. [AMD/ATI] Hawaii PRO [Radeon R9 290] [1002:67b1]'

# Default to show supported hardware only
SHOW=false

# ==============================================
# End configuration
# ==============================================

# Run this script as root
if [ $UID -ne 0 ]; then
  sudo "$0" "$@"
  exit $?
fi

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
  echo '-t           For developers: simuluate driver installation.'
  echo '             Change TESTHWCARD in this script to select different hardware.'
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

# Get distribution release
if [ -f /etc/debian_version ]; then
  DISTRIB_RELEASE=$(head -n 1 /etc/debian_version 2>/dev/null | sed 's/[a-zA-Z]/0/' | cut -d'.' -f 1)
fi

if [ -z $DISTRIB_RELEASE ]; then
  echo '[AMD] Cannot get the Debian version from /etc/debian_version.' | tee -a $LOG
  echo '[AMD] Please install the base-files package.' | tee -a $LOG
  exit 8
fi

# Non-numeric values means that it's testing (sid)
if [[ $DISTRIB_RELEASE =~ '^[0-9]+$' ]] ; then
  if [ $DISTRIB_RELEASE -lt 9 ]; then
    echo '[AMD] This script is for Debian Stretch and beyond.' | tee -a $LOG
    exit 0
  fi
fi

# Get AMD graphical cards
BCID='1002'
HWCARDS=`lspci -nn -d $BCID: | egrep -i " 3d | display | vga "`
# Cleanup
HWCARDS="${HWCARDS#*: }"
HWCARDS="${HWCARDS%(rev*}"
# Testing
if $TEST; then
  HWCARDS=$TESTHWCARD
fi
#DEVICEIDS=$(echo "$HWCARDS" | grep -Po '(?<=\:)[0-9a-z]*(?=\])')

if [ "$HWCARDS" == '' ]; then
  if ! $SHOW; then
    echo '[AMD] No AMD/ATI card found.' | tee -a $LOG
  fi
  exit 0
fi

# Check if card is supported by amdgpu driver
PCKS=$OLDAMD
OLDIFS=$IFS
IFS=','
# Match patterns case-insensitive
shopt -s nocasematch
for CARD in $SUPPORTEDCARDS; do
  if [[ "$HWCARDS" =~ "$CARD" ]]; then
    PCKS=$NEWAMD
    break
  fi
done
IFS=$OLDIFS

# Show supported hardware only (include drivers)
if [ "$HWCARDS" != '' ] && $SHOW; then
  echo "$HWCARDS [$PCKS]"
  exit 0
fi

# If old driver is needed, make sure the new driver is not installed
if [ "$PCKS" == "$OLDAMD" ]; then
  PURGEPCKS="$NEWAMD $PURGEPCKS"
fi

# Add additional packages
PCKS="$ADDITIONALPCKS $PCKS"

# Check if all these packages exist in the repository
if [ ! $TEST ]; then
  apt-get update
fi
for PCK in $PCKS; do
  PCKINFO=$(apt-cache show "$PCK" 2>/dev/null)
  if [ "$PCKINFO" == '' ]; then
    echo "[AMD] Unable to install $PCK: not in repository." | tee -a $LOG
    exit 7
  fi
done

# Start installing the packages
if $TEST && ! $FORCE; then
  echo "[AMD] - TEST - Install packages: $PCKS." | tee -a $LOG
  if [ "$PURGEPCKS" != '' ]; then
    echo "[AMD] - TEST - Purge packages: $PURGEPCKS." | tee -a $LOG
  fi
else
  for PCK in $PCKS; do
    # Backport?
    BP=''
    if $BACKPORTS; then
      BP=$(get_backports_string $PCK)
    fi
    echo "[AMD] Run command: apt-get install --reinstall $BP -y $APTFORCE $PCK." | tee -a $LOG
    apt-get install --reinstall $BP -y $APTFORCE $PCK 2>&1 | tee -a $LOG
  done
    
  # Purge packages if needed
  for PCK in $PURGEPCKS; do
    echo "[AMD] Run command: apt-get purge -y $APTFORCE $PCK" | tee -a $LOG
    apt-get purge -y $APTFORCE $PCK 2>&1 | tee -a $LOG
  done
    
  echo '[AMD] AMD driver installed.' | tee -a $LOG
fi
