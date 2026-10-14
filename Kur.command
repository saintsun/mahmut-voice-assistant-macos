#!/bin/bash
# DOUBLE-CLICK from Finder: a terminal opens and the install starts.
cd "$(dirname "$0")"
# Files downloaded from the internet carry the macOS quarantine flag; it is
# cleared for our own folder so no "unidentified developer" dialog appears.
xattr -dr com.apple.quarantine . 2>/dev/null || true
chmod +x ./*.sh ./*.command 2>/dev/null || true
clear
cat <<'BANNER'
   __  __       _                  _
  |  \/  | __ _| |__  _ __ ___  _   _| |_
  | |\/| |/ _` | '_ \| '_ ` _ \| | | | __|
  | |  | | (_| | | | | | | | | | |_| | |_
  |_|  |_|\__,_|_| |_|_| |_| |_|\__,_|\__|   Voice Assistant

  Claude Code ile sesli konusma — kurulum basliyor.
BANNER
./setup.sh
echo
echo "Bu pencereyi kapatabilirsin."
