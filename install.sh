#!/bin/bash
# One-line installer. Downloads the project and runs setup.sh.
#
#   curl -fsSL https://raw.githubusercontent.com/saintsun/mahmut-voice-assistant-macos/main/install.sh | bash
#
# Everything else (Homebrew, PortAudio, FFmpeg, Python, the speech model and
# the app bundle) is handled by setup.sh. git is not required: without it the
# source is fetched as a tarball.
set -euo pipefail

REPO="saintsun/mahmut-voice-assistant-macos"
BRANCH="${MAHMUT_BRANCH:-main}"
DIR="${MAHMUT_DIR:-$HOME/Mahmut}"

say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }
ok()   { printf '    \033[1;32m✓\033[0m %s\n' "$1"; }
die()  { printf '    \033[1;31m✗\033[0m %s\n' "$1"; exit 1; }

say "makine kontrol ediliyor"
[ "$(uname -s)" = "Darwin" ] || die "Bu uygulama yalnızca macOS içindir."
[ "$(uname -m)" = "arm64" ] || die "Apple Silicon (M serisi) gerekiyor."
ok "macOS $(sw_vers -productVersion) / Apple Silicon"

say "dosyalar indiriliyor -> $DIR"
if [ -d "$DIR/.git" ] && command -v git >/dev/null 2>&1; then
  git -C "$DIR" pull --quiet --ff-only || true
  ok "mevcut kurulum güncellendi"
elif command -v git >/dev/null 2>&1; then
  [ -e "$DIR" ] && die "$DIR zaten var. Başka bir yere kurmak için: MAHMUT_DIR=~/BaskaKlasor"
  git clone --quiet --depth 1 -b "$BRANCH" "https://github.com/$REPO" "$DIR"
  ok "indirildi (git)"
else
  # git yoksa tarball: Xcode araçlarını kurmaya gerek kalmaz
  [ -e "$DIR" ] && die "$DIR zaten var. Başka bir yere kurmak için: MAHMUT_DIR=~/BaskaKlasor"
  TMP="$(mktemp -d)"
  curl -fsSL "https://codeload.github.com/$REPO/tar.gz/refs/heads/$BRANCH" \
    -o "$TMP/src.tar.gz" || die "indirme başarısız (internet bağlantını kontrol et)"
  mkdir -p "$DIR"
  tar -xzf "$TMP/src.tar.gz" -C "$DIR" --strip-components=1
  rm -rf "$TMP"
  ok "indirildi (tarball)"
fi

cd "$DIR"
chmod +x ./*.sh ./*.command ./*.py 2>/dev/null || true
xattr -dr com.apple.quarantine . 2>/dev/null || true

say "kurulum başlıyor"
exec ./setup.sh
