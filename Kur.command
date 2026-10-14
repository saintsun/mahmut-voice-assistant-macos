#!/bin/bash
# Finder'dan CIFT TIKLA: Terminal acilir ve kurulum baslar.
cd "$(dirname "$0")"
# Internetten indirilmis dosyalarda macOS karantina bayragi olur; kendi
# klasorumuzden temizliyoruz ki "gelistirici dogrulanamadi" cikmasin.
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
