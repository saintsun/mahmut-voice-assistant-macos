#!/bin/bash
# Tek komutluk kurulum: bagimliliklar + venv + model + .app bundle.
# Cift tiklamayla calistirmak icin: Kur.command
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# MAHMUT_UNATTENDED=1: pencere acmaz, soru sormaz (test/otomasyon icin).
UNATTENDED="${MAHMUT_UNATTENDED:-0}"
ask() {   # ask "soru" -> cevabi yazar; gozetimsizde varsayilani doner
  local q="$1" def="$2" a=""
  if [ "$UNATTENDED" = "1" ] || [ ! -r /dev/tty ]; then echo "$def"; return; fi
  printf '%s' "$q" >&2
  read -r a </dev/tty || a="$def"
  echo "${a:-$def}"
}

say_step() { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }
say_ok()   { printf '    \033[1;32m✓\033[0m %s\n' "$1"; }
say_err()  { printf '    \033[1;31m✗\033[0m %s\n' "$1"; }

# --- 0) Makine kontrolu -------------------------------------------------
say_step "makine kontrol ediliyor"
[ "$(uname -s)" = "Darwin" ] || { say_err "Bu uygulama yalnizca macOS icindir."; exit 1; }
[ "$(uname -m)" = "arm64" ] || {
  say_err "Apple Silicon (M serisi) gerekiyor — konusma tanima GPU'da calisiyor."
  exit 1; }
MACOS="$(sw_vers -productVersion)"
say_ok "macOS $MACOS / Apple Silicon"

if [ ! -d "/Applications/Claude.app" ]; then
  printf '    \033[1;33m!\033[0m Claude masaustu uygulamasi bulunamadi.\n'
  printf '      Mahmut mesajlari ona yaziyor: https://claude.ai/download\n'
fi

# --- 1) Homebrew --------------------------------------------------------
say_step "Homebrew"
if ! command -v brew >/dev/null 2>&1; then
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    [ -x "$b" ] && eval "$("$b" shellenv)" && break
  done
fi
if ! command -v brew >/dev/null 2>&1; then
  ans="$(ask '    Homebrew yok. Kurulsun mu? (paket yoneticisi, ~2 dk) [E/h] ' e)"
  case "${ans:-e}" in
    [hHnN]*) say_err "Homebrew olmadan devam edilemez."; exit 1 ;;
  esac
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    [ -x "$b" ] && eval "$("$b" shellenv)" && break
  done
fi
command -v brew >/dev/null || { say_err "brew bulunamadi"; exit 1; }
say_ok "brew $(brew --version | head -1 | cut -d" " -f2)"

# --- 2) Sistem paketleri ------------------------------------------------
say_step "sistem paketleri"
for pkg in portaudio ffmpeg; do
  if brew list "$pkg" >/dev/null 2>&1; then
    say_ok "$pkg zaten kurulu"
  else
    echo "    $pkg kuruluyor..."
    brew install "$pkg" >/dev/null
    say_ok "$pkg kuruldu"
  fi
done

# --- 3) Python ----------------------------------------------------------
say_step "Python"
PY=""
for cand in python3.13 python3.12 python3.11; do
  p="$(brew --prefix 2>/dev/null)/bin/$cand"
  [ -x "$p" ] && { PY="$p"; break; }
done
if [ -z "$PY" ]; then
  echo "    python@3.13 kuruluyor..."
  brew install python@3.13 >/dev/null
  PY="$(brew --prefix)/bin/python3.13"
fi
[ -x "$PY" ] || { say_err "python bulunamadi"; exit 1; }
say_ok "$("$PY" -V) — $PY"

# Bundle, python'u kendi icinde calistiriyor: embed baglama bayraklari sart.
PYV="$("$PY" -c 'import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PYCFG="$(dirname "$PY")/python$PYV-config"
"$PYCFG" --embed --ldflags >/dev/null 2>&1 || {
  say_err "$PYCFG --embed calismiyor (framework kurulumu gerekli)."
  say_err "Cozum: brew reinstall python@$PYV"
  exit 1; }
say_ok "embed baglama hazir"

xcode-select -p >/dev/null 2>&1 || {
  say_step "derleyici araclari"
  echo "    Xcode Command Line Tools kuruluyor (pencere acilacak)..."
  xcode-select --install || true
  echo "    Kurulum bitince bu dosyayi tekrar calistir."
  exit 1; }

# --- 4) Sanal ortam -----------------------------------------------------
say_step "python paketleri"
[ -d .venv ] || "$PY" -m venv .venv
./.venv/bin/pip -q install --upgrade pip
./.venv/bin/pip -q install -r requirements.txt
say_ok "$(./.venv/bin/pip list 2>/dev/null | wc -l | tr -d ' ') paket hazir"

# --- 5) Ayar dosyasi ----------------------------------------------------
say_step "ayarlar"
if [ -f config.json ]; then
  PYTHONPATH=. ./.venv/bin/python sync_config.py >/dev/null 2>&1 || true
  say_ok "mevcut config.json korundu (eksik ayarlar eklendi)"
else
  PYTHONPATH=. ./.venv/bin/python -c "
from claudevoice.config import Config
Config().write_default()" 2>/dev/null || true
  say_ok "config.json olusturuldu"
fi

# --- 6) Model -----------------------------------------------------------
say_step "konusma tanima modeli (ilk sefer ~1.5GB indirir)"
PYTHONPATH=. ./.venv/bin/python -c "
from claudevoice.config import Config
from claudevoice.stt import Transcriber
t = Transcriber(Config()['stt'])
print('    model hazir' if t.warmup() else '    HATA: ' + str(t.load_error))
"

# --- 7) Bundle ----------------------------------------------------------
say_step "uygulama paketleniyor"
./build_app.sh

# --- 8) Baslat + izinler ------------------------------------------------
say_step "baslatiliyor"
if [ "$UNATTENDED" != "1" ]; then
  pkill -x Mahmut 2>/dev/null || true
  rm -f .app.lock
  sleep 1
  open Mahmut.app
  sleep 3
fi

printf '\n\033[1;36m==> izinler\033[0m\n'
printf '    Iki izin gerekiyor; ikisi de Sistem Ayarlari > Gizlilik ve Guvenlik altinda:\n'
printf '      1) Mikrofon        — konustugunu duymasi icin\n'
printf '      2) Erisilebilirlik — mesaji Claude penceresine yazmasi icin\n'
printf '    Erisilebilirlik listesinde Mahmut yoksa: "+" > bu klasordeki Mahmut.app\n'
printf '    Ayar penceresi aciliyor...\n'
sleep 1
[ "$UNATTENDED" = "1" ] || \
  open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility" 2>/dev/null || true

printf '\n    Izni verdikten sonra uygulamayi bir kez kapatip ac:\n'
printf '      ./stop.sh && open Mahmut.app\n'

auto="$(ask "$(printf '\n\033[1;36m==> acilista otomatik baslasin mi?\033[0m [E/h] ')" h)"
case "${auto:-e}" in
  [eEyY]*) ./install_autostart.sh ;;
  *) echo "    atlandi — sonra: ./install_autostart.sh" ;;
esac

cat <<'EOF'

====================================================================
 Kurulum bitti.

   Panel      : http://127.0.0.1:8765/   (menubar > Panel)
   Baslat     : "Mahmut basla" de
   Mesaj yolla: konus, sonunda "tamam Mahmut" de
   Okumayi kes: ⌥⌘K
   Kontrol     : ./selftest.py   ya da   ./verify.sh
====================================================================
EOF
