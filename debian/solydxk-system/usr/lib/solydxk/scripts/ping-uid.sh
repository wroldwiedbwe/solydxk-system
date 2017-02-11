#!/bin/bash
PING=$(which ping)
if [ -f "$PING" ]; then
  sudo chmod u+s "$PING"
fi
