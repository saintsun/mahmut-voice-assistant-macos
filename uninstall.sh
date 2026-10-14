#!/bin/bash
# Removes Mahmut from the machine.
#
#   ./uninstall.sh          asks before every optional step
#   ./uninstall.sh --all    removes everything, including the speech model
#   ./uninstall.sh --keep   removes only the app, keeps settings and model
#
# Homebrew packages (portaudio, ffmpeg, python) are never touched: other
# programs use them. The command to remove them by hand is printed at the end.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

LABEL="com.erengunes.mahmut"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
SUP="$HOME/Library/Application Support/Mahmut"
MODEL_DIR="$HOME/.cache/huggingface/hub/models--mlx-community--whisper-large-v3-turbo"
MODE="${1:-}"

case "$MODE" in
  -h|--help)
    sed -n "2,9p" "$0" | sed "s/^# \{0,1\}//"; exit 0 ;;
esac

say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }
ok()   { printf '    \033[1;32m✓\033[0m %s\n' "$1"; }
skip() { printf '    \033[1;33m-\033[0m %s\n' "$1"; }
die()  { printf '    \033[1;31m✗\033[0m %s\n' "$1"; exit 1; }

ask() {   # ask "soru" "varsayilan" -> cevap
  local q="$1" def="$2" a=""
  case "$MODE" in
    --all)  echo "e"; return ;;
    --keep) echo "h"; return ;;
  esac
  [ -r /dev/tty ] || { echo "$def"; return; }
  printf '    %s' "$q" >&2
  read -r a 2>/dev/null </dev/tty || a="$def"
  echo "${a:-$def}"
}
yes_p() { case "$1" in [eEyY]*) return 0 ;; *) return 1 ;; esac; }

# Guard: this must look like the Mahmut folder before anything is deleted.
[ -d "$ROOT/claudevoice" ] && [ -f "$ROOT/setup.sh" ] \
  || die "Bu klasor Mahmut kurulumu gibi gorunmuyor: $ROOT"

printf '\n\033[1;36mMahmut kaldiriliyor\033[0m  (%s)\n' "$ROOT"

# --- 1) Stop the app ----------------------------------------------------
say "uygulama durduruluyor"
./stop.sh >/dev/null 2>&1 || true
pkill -x Mahmut 2>/dev/null || true
rm -f .app.lock .tts.pids
ok "kapatildi"

# --- 2) Autostart -------------------------------------------------------
say "acilista otomatik baslatma"
if [ -f "$PLIST" ] || [ -d "$SUP" ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  rm -rf "$SUP"
  ok "launch agent ve kayitlari silindi"
else
  skip "zaten kurulu degil"
fi

# --- 3) App bundle and virtual environment -----------------------------
say "uygulama dosyalari"
rm -rf "$ROOT/Mahmut.app"; ok "Mahmut.app silindi"
rm -rf "$ROOT/.venv";      ok "python ortami silindi"
rm -rf "$ROOT/__pycache__" "$ROOT/claudevoice/__pycache__" 2>/dev/null || true
rm -f  "$ROOT"/*.log "$ROOT"/mahmut*.log 2>/dev/null || true
ok "gecici dosyalar temizlendi"

# --- 4) Settings --------------------------------------------------------
say "ayarlar"
if [ -f "$ROOT/config.json" ]; then
  a="$(ask 'config.json silinsin mi? (kendi komut kaliplarin burada) [e/H] ' h)"
  if yes_p "${a:-h}"; then rm -f "$ROOT/config.json"; ok "silindi"
  else skip "korundu: $ROOT/config.json"; fi
else
  skip "config.json yok"
fi

# --- 5) Speech model ----------------------------------------------------
say "konusma tanima modeli"
if [ -d "$MODEL_DIR" ]; then
  SIZE="$(du -shL "$MODEL_DIR" 2>/dev/null | cut -f1 | tr -d ' ')"
  a="$(ask "model silinsin mi? (${SIZE:-~1.5G} disk acilir, yeniden kurarsan tekrar iner) [e/H] " h)"
  if yes_p "${a:-h}"; then rm -rf "$MODEL_DIR"; ok "silindi"
  else skip "korundu: $MODEL_DIR"; fi
else
  skip "indirilmemis"
fi

# --- 6) Privacy permissions --------------------------------------------
say "izinler"
tccutil reset Microphone "$LABEL" >/dev/null 2>&1 || true
tccutil reset Accessibility "$LABEL" >/dev/null 2>&1 || true
ok "mikrofon ve erisilebilirlik kayitlari sifirlandi"
printf '    Sistem Ayarlari > Gizlilik ve Guvenlik listesinde Mahmut hala\n'
printf '    gorunuyorsa satiri secip "-" ile kaldirabilirsin.\n'

# --- 7) The folder itself ----------------------------------------------
say "proje klasoru"
a="$(ask "$ROOT klasoru da silinsin mi? [e/H] " h)"
if yes_p "${a:-h}"; then
  cd "$HOME"
  rm -rf "$ROOT"
  ok "klasor silindi"
  printf '\n\033[1;32mMahmut tamamen kaldirildi.\033[0m\n\n'
  exit 0
fi
skip "korundu: $ROOT"

cat <<EOF

====================================================================
 Mahmut kaldirildi.

 Homebrew paketlerine dokunulmadi (baska programlar da kullaniyor).
 Gercekten istiyorsan:
   brew uninstall portaudio ffmpeg

 Yeniden kurmak icin bu klasorde:
   ./setup.sh
====================================================================
EOF
