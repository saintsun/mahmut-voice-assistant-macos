#!/bin/bash
# DOUBLE-CLICK from Finder: a terminal opens and the uninstall starts.
cd "$(dirname "$0")"
chmod +x ./uninstall.sh 2>/dev/null || true
clear
cat <<'BANNER'

  Mahmut: Voice Assistant - kaldirma

  Uygulama, otomatik baslatma ve python ortami silinir.
  Ayarlarin ve indirilen konusma modeli icin ayri ayri sorulur.

BANNER
./uninstall.sh
echo
echo "Bu pencereyi kapatabilirsin."
