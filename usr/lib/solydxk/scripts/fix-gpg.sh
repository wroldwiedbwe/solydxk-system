#!/bin/bash

D=/etc/apt
[ -e $D/trusted.gpg ] || { echo "$D/trusted.gpg not present"; exit 1; }
K=$D/trusted.gpg.obsolete
mv -f $D/trusted.gpg $K
echo "$D/trusted.gpg renamed to $K"
L=1
T=$(LANG=C apt-key list 2>/dev/null)
while read -r R; do
   ((++L))
   if [ "${R:0:3}" == pub ]; then
      [ "${R#*expired:}" != "$R" ] && L=1 || L=0
   elif [ $L -eq 1 ]; then
      if grep -q "$R" <<<$T; then
         echo "$R already present"
      else
         echo "$R exported to trusted.gpg.d"
         R="${R// /}"
         apt-key --keyring $K export $R 2>/dev/null >$D/trusted.gpg.d/$R.asc
      fi
   fi
done < <(LANG=C apt-key --keyring $K list 2>/dev/null) 
