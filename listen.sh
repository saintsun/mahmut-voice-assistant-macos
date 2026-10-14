#!/bin/bash
# Live view of what Mahmut hears. Speak, and see what it understood.
cd "$(dirname "$0")"
echo "Konuş — Mahmut'un duyduğu metin burada görünecek. Çıkmak için Ctrl+C."
echo "----------------------------------------------------------------"
LAST=""
while true; do
  if [ -f .state.json ]; then
    /opt/homebrew/bin/python3.13 - <<'PY'
import json
try: d = json.load(open(".state.json"))
except Exception: raise SystemExit
print(f"{d['state']:5}|{d['mic_rms']:.4f}|{d.get('last_transcript','')}|{d['status']}")
PY
  fi
  sleep 1
done | while IFS='|' read -r st rms txt status; do
  if [ "$txt" != "$LAST" ] && [ -n "$txt" ]; then
    echo "  🗣  duydu: $txt"
    echo "      → $status"
    LAST="$txt"
  fi
done
