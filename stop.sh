#!/bin/bash
# Stops Mahmut and any speaking processes cleanly.
# (A plain `pkill python` leaves `say`/`afplay` orphaned and still
#  reading; this script stops those too.)
cd "$(dirname "$0")"

# 1) Kill the recorded playback processes
if [ -f .tts.pids ]; then
  while read -r pid; do
    [ -n "$pid" ] || continue
    name=$(ps -p "$pid" -o comm= 2>/dev/null)
    case "$name" in
      *say|*afplay) kill "$pid" 2>/dev/null && echo "  ses süreci durduruldu: $pid" ;;
    esac
  done < .tts.pids
  rm -f .tts.pids
fi

# 2) Stop the app (SIGTERM -> it cleans up after itself)
if pgrep -x Mahmut >/dev/null 2>&1; then
  pkill -x Mahmut && echo "  Mahmut durduruldu"
else
  echo "  Mahmut zaten kapalı"
fi
sleep 1
pgrep -x Mahmut >/dev/null 2>&1 && { pkill -9 -x Mahmut; echo "  (zorla kapatıldı)"; }
pkill -f "claudevoice.app" 2>/dev/null
echo "bitti"
