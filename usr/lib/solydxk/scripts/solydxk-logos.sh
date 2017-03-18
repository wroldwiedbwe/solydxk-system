#!/bin/bash

# Create symlinks of the SolydXK logos to any icon theme installed

ICONSDIR="/usr/share/icons"
ORGDIR="$ICONSDIR/evolvere-additional/apps/scalable"
if [ -e "$ORGDIR/solydx.svg" ] && [ -e "$ORGDIR/solydk.svg" ]; then
  for D in $(ls $ICONSDIR | grep -v 'evolvere-additional'); do
    # Evolvere icon theme
    DEST="$ICONSDIR/$D/apps/64/"
    if [ ! -d "$DEST" ]; then
      # Usually this one exists in a theme
      DEST="$ICONSDIR/$D/48x48/apps/"
    fi
    if [ -d "$DEST" ]; then
      ln -sf "$ORGDIR/solydx.svg" "$DEST"
      ln -sf "$ORGDIR/solydk.svg" "$DEST"
    fi
  done
fi
