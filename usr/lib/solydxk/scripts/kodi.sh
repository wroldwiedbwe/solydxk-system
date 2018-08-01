#!/bin/bash

if dpkg -l | grep -qw kodi; then
  # Add kodi to the input group
  if id kodi >/dev/null 2>&1; then
    if ! id -nG kodi | grep -qw input; then
      usermod -a -G input kodi
    fi
  fi
  
  # Create some udev rules
  RULES='/etc/udev/rules.d/99-input.rules'
  if [ ! -f "$RULES" ]; then
    echo 'SUBSYSTEM==input, GROUP=input, MODE=0660
KERNEL==tty[0-9]*, GROUP=tty, MODE=0660' > "$RULES"
  fi
  
  RULES='/etc/udev/rules.d/10-permissions.rules'
  if [ ! -f "$RULES" ]; then
    echo '# input
KERNEL=="mouse*|mice|event*",   MODE="0660", GROUP="input"
KERNEL=="ts[0-9]*|uinput",      MODE="0660", GROUP="input"
KERNEL==js[0-9]*,               MODE=0660, GROUP=input
# tty
KERNEL==tty[0-9]*,              MODE=0666
# vchiq
SUBSYSTEM==vchiq,  GROUP=video, MODE=0660' > "$RULES"
  fi
fi
