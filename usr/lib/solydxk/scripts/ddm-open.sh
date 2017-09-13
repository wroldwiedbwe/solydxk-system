#!/bin/bash

# ==============================================
# DDM driver cleanup for Stretch
# ==============================================
# ==============================================

# Drivers that can be purged
PURGEDRVS='amd nvidia broadcom pae'

# Get installed packages that can be purged
PURGEAMD=$(dpkg -l | grep 'amdgpu' | grep -v 'drm' | awk '/^[hi]i/{print $2}')
PURGENVIDIA=$(dpkg -l | grep 'nvidia' | egrep -v 'detect|cleanup' | awk '/^[hi]i/{print $2}')
PURGEBUMBLEBEE=$(dpkg -l | egrep  'bumblebee*|primus*|primus*:i386' | awk '/^[hi]i/{print $2}')
BROADCOMDRV=$(ddm -i broadcom -s | awk -F'[' '{print $NF}' | tr -d '[]')
PURGEBROADCOM=$(dpkg -l | grep "$BROADCOMDRV" | awk '/^[hi]i/{print $2}')
PURGEPAE=$(dpkg -l | grep '\-pae' | awk '/^[hi]i/{print $2}')


# Additional apt parameters
APTFORCE='--allow-downgrades --allow-remove-essential --allow-change-held-packages'

# Default value for testing
TEST=false

# ==============================================
# End configuration
# ==============================================

# Run this script as root
if [ $UID -ne 0 ]; then
  sudo "$0" "$@"
  exit $?
fi

function usage() {
  echo
  echo "Device Driver Manager Help for $(basename $0)"
  echo 
  echo 'The following options are allowed:'
  echo
  echo '-h           Show this help.'
  echo
  echo '-p driver    Purge given driver.'
  echo "             driver: $PURGEDRVS"
  echo
  echo '-t           For developers: simuluate driver installation.'
  echo
}

function install_open {
  # Make sure you have the most used drivers installed 
  # These are installed by default on SolydXK
  OPENDRVS="xserver-xorg-video-nouveau xserver-xorg-video-vesa xserver-xorg-video-intel xserver-xorg-video-fbdev xserver-xorg-video-ati xserver-xorg-video-radeon xserver-xorg-video-r128 xserver-xorg-video-mach64"
  
  if $TEST; then
    echo "[OPEN] - TEST - Install open drivers: $OPENDRVS" | tee -a $LOG
  else
    # Install the packages
    apt-get update
    for DRV in $OPENDRVS; do
      INSTALLED=$(dpkg-query -l $DRV 2>/dev/null | awk '/^[hi]i/{print $2}')
      if [ "$INSTALLED" == "$DRV" ]; then
        echo "[OPEN] Install package: $DRV" | tee -a $LOG
        apt-get install -y $APTFORCE $DRV 2>&1 | tee -a $LOG
      fi
    done
  fi
}

# ==============================================
# ==============================================

# Get bash arguments
FORCE=false
while getopts ':fhp:t' opt; do
  case $opt in
    f)
      FORCE=true
      ;;
    h)
      usage
      exit 0
      ;;
    p)
      # Purge
      for DRV in $PURGEDRVS; do
        if [ "$OPTARG" == "$DRV" ]; then
          PURGE=$DRV
          break
        fi
      done
      if [ "$PURGE" == '' ]; then
        echo "$OPTARG is not allowed: $PURGEDRVS"
      fi
      ;;
    t)
      # Testing
      TEST=true
      ;;
    :)
      echo "Option -$OPTARG requires one of these arguments: $PURGEDRVS."
      exit 2
      ;;
    *)
      # Unknown error
      echo "Unknown argument $@"
      exit 2
      ;;
  esac
done

# Purge all drivers if no arguments were given
if [ -z $PURGE ]; then
  echo "[OPEN] -p not given. Nothing to purge."
  exit 0
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

# Loop through the given drivers to purge
for DRV in $PURGE; do
  echo "[OPEN] Remove drivers for: $DRV." | tee -a $LOG
  case $DRV in
    amd)
      if [ "$PURGEAMD" != '' ]; then
        if $TEST && ! $FORCE; then
          echo "[OPEN] - TEST - Run command: apt-get purge -y $APTFORCE $PURGEAMD." | tee -a $LOG
        else
          apt-get purge -y $APTFORCE $PURGEAMD 2>&1 | tee -a $LOG
          install_open
        fi
      fi
      ;;
    nvidia)
      if [ "$PURGENVIDIA" != '' ]; then
        if $TEST && ! $FORCE; then
          echo "[OPEN] - TEST - Run command: apt-get purge -y $APTFORCE $PURGENVIDIA." | tee -a $LOG
        else
          apt-get purge -y $APTFORCE $PURGENVIDIA 2>&1 | tee -a $LOG
          install_open
        fi
      fi
      if [ "$PURGEBUMBLEBEE" != '' ]; then
        if $TEST && ! $FORCE; then
          echo "[OPEN] - TEST - Run command: apt-get purge -y $APTFORCE $PURGEBUMBLEBEE" | tee -a $LOG
        else
          apt-get purge -y $APTFORCE $PURGEBUMBLEBEE 2>&1 | tee -a $LOG
          install_open
        fi
      fi
      if ! $TEST; then
        rm -v /etc/X11/xorg.conf 2>/dev/null | tee -a $LOG
        rm -v /etc/modprobe.d/nvidia* 2>/dev/null | tee -a $LOG
        rm -v /etc/modprobe.d/blacklist-nouveau.conf 2>/dev/null | tee -a $LOG
      fi
      ;;
    broadcom)
      if [ "$PURGEBROADCOM" != '' ]; then
        if $TEST && ! $FORCE; then
          echo "[OPEN] - TEST - Run command: apt-get purge -y $APTFORCE $PURGEBROADCOM" | tee -a $LOG
        else
          apt-get purge -y $APTFORCE $PURGEBROADCOM 2>&1 | tee -a $LOG
        fi
      fi
      if ! $TEST; then
        rm -v '/etc/modprobe.d/blacklist-broadcom.conf' 2>/dev/null | tee -a $LOG
      fi
      ;;
    pae)
      RELEASE=`uname -r`
      if [[ "$RELEASE" =~ "pae" ]]; then
        echo "[OPEN] - ERROR - Cannot remove PAE kernel when PAE is booted. Please boot into another kernel." | tee -a $LOG
        exit 6
      else
        if $TEST && ! $FORCE; then
          echo "[OPEN] - TEST - Run command: apt-get purge -y $APTFORCE $PURGEPAE" | tee -a $LOG
        else
          apt-get purge -y $APTFORCE $PURGEPAE 2>&1 | tee -a $LOG
        fi
      fi
      ;;
  esac
done
