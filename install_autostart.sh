#!/bin/bash
# macOS acilisinda Mahmut'u otomatik baslatir.
#   ./install_autostart.sh            -> install
#   ./install_autostart.sh --remove   -> uninstall
#   ./install_autostart.sh --status   -> status
#
# NOTE: the launcher script is written under ~/Library/Application Support,
# NOT into the project folder. A project under ~/Desktop is TCC protected by
# protected; launchd cannot run a script from there ("Operation not
# permitted", exit 126).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.erengunes.mahmut"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
SUP="$HOME/Library/Application Support/Mahmut"
DOMAIN="gui/$(id -u)"

case "${1:-}" in
  --remove)
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    rm -f "$PLIST" "$SUP/autostart.sh"
    echo "Otomatik baslatma kaldirildi."
    exit 0 ;;
  --status)
    if launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
      echo "Kurulu."
      launchctl print "$DOMAIN/$LABEL" | grep -E "^\s+(state|runs|last exit code) " || true
    else
      echo "Kurulu degil."
    fi
    exit 0 ;;
esac

[ -d "$ROOT/Mahmut.app" ] || { echo "HATA: Mahmut.app yok, once ./setup.sh"; exit 1; }
mkdir -p "$HOME/Library/LaunchAgents" "$SUP"

cat > "$SUP/autostart.sh" <<INNER
#!/bin/bash
# The LaunchAgent calls this: it starts the app when it is not running.
APP="$ROOT/Mahmut.app"

# Surec ADINA gore tam eslesme. 'pgrep -f' kullanilmaz: komut satirinda bu
# another process containing that text (a terminal, say) is a false positive.
if pgrep -x Mahmut >/dev/null 2>&1; then
  exit 0
fi

# 'open' instead of running the binary directly: LaunchServices then
# opens it through LaunchServices, so Accessibility/Microphone stay valid.
exec /usr/bin/open -a "\$APP"
INNER
chmod +x "$SUP/autostart.sh"

cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$SUP/autostart.sh</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>StartInterval</key><integer>300</integer>
  <key>ProcessType</key><string>Interactive</string>
  <key>StandardOutPath</key><string>$SUP/autostart.log</string>
  <key>StandardErrorPath</key><string>$SUP/autostart.log</string>
</dict>
</plist>
PLISTEOF

launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST"
launchctl enable "$DOMAIN/$LABEL" 2>/dev/null || true

echo "Kuruldu."
echo "  ajan  : $PLIST"
echo "  script: $SUP/autostart.sh"
echo
echo "macOS her acildiginda Mahmut baslayacak."
echo "Ayrica 5 dakikada bir kontrol edilir; uygulama cokerse geri getirilir."
echo "Kaldirmak: ./install_autostart.sh --remove"
