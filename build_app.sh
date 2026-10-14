#!/bin/bash
# Mahmut.app bundle'ini uretir.
#
# Python, bundle'in ICINDE calisir: launcher libpython'a baglanip Py_BytesMain
# cagiriyor, yani ayri bir surec baslatmiyor. Eskiden bundle disindaki venv
# python'u exec ediliyordu; o zaman surecin bundle'i Python.app oluyor ve
# Dock'ta "Python" + roket ikonu gorunuyordu.
#
# Apple Developer hesabi GEREKMEZ: ad-hoc imza (codesign -s -) yerel calisir.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
APP="$ROOT/Mahmut.app"
PYBIN="$ROOT/.venv/bin/python3"
BUNDLE_ID="com.erengunes.mahmut"

[ -x "$PYBIN" ] || { echo "HATA: $PYBIN yok. Once ./setup.sh calistir."; exit 1; }

PYCFG="$("$PYBIN" -c 'import sys,sysconfig,os
v=f"{sys.version_info.major}.{sys.version_info.minor}"
print(os.path.join(sys.base_prefix,"bin",f"python{v}-config"))')"
[ -x "$PYCFG" ] || PYCFG="$(command -v python3-config || true)"
[ -x "$PYCFG" ] || { echo "HATA: python3-config bulunamadi"; exit 1; }
PY_HOME="$("$PYBIN" -c 'import sys;print(sys.base_prefix)')"
VENV_SITE="$("$PYBIN" -c 'import site;print(site.getsitepackages()[0])')"

# --- Idempotent build ---------------------------------------------------
# ad-hoc imza SABIT kimlik vermez; imza cdhash tabanlidir. Launcher ikilisi
# ya da Info.plist degisirse macOS'un verdigi Erisilebilirlik izni GECERSIZ
# olur. Python kodu bundle'in DISINDA durdugu icin kodu istedigin kadar
# degistirirsin; izin bozulmaz.
FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1
FINGERPRINT="$(printf '%s|%s|%s|%s' "$ROOT" "$PY_HOME" "$VENV_SITE" "v3-embedded" \
  | shasum -a 256 | cut -d" " -f1)"
STAMP="$APP/Contents/Resources/build.fingerprint"

if [ $FORCE -eq 0 ] && [ -x "$APP/Contents/MacOS/Mahmut" ] \
   && [ "$(cat "$STAMP" 2>/dev/null)" = "$FINGERPRINT" ]; then
  echo "bundle zaten guncel — dokunulmadi (Erisilebilirlik izni korundu)"
  echo "hazir: $APP"
  exit 0
fi

if [ -d "$APP" ]; then
  echo "UYARI: launcher yeniden derleniyor."
  echo "       Erisilebilirlik iznini YENIDEN vermen gerekecek:"
  echo "       Sistem Ayarlari > Gizlilik ve Guvenlik > Erisilebilirlik"
  echo "       'Mahmut' girisini '-' ile SIL, sonra '+' ile tekrar ekle."
fi

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cat > "$ROOT/.launcher.c" <<'C'
#include <Python.h>
#include <stdlib.h>
#include <unistd.h>

/* Python'u ALT SUREC olarak degil, KENDI icimizde calistiriyoruz: surecin
   bundle'i bu .app oluyor, Dock dogru ismi ve ikonu gosteriyor. */
int main(int argc, char **argv) {
    setenv("PYTHONHOME", PY_HOME, 1);
    setenv("PYTHONPATH", APP_ROOT ":" VENV_SITE, 1);
    setenv("PYTHONUNBUFFERED", "1", 1);
    setenv("PYTHONDONTWRITEBYTECODE", "1", 1);
    if (chdir(APP_ROOT) != 0) { perror("chdir"); return 1; }

    /* Kendi argumanlarimizi python'a aktar (ornek: --test-inject). */
    char **args = (char **)malloc(sizeof(char *) * (size_t)(argc + 3));
    if (!args) return 127;
    args[0] = argv[0];
    args[1] = "-m";
    args[2] = "claudevoice.app";
    for (int i = 1; i < argc; i++) args[i + 2] = argv[i];
    args[argc + 2] = NULL;
    return Py_BytesMain(argc + 2, args);
}
C

cc -O2 -Wall \
   $("$PYCFG" --includes) $("$PYCFG" --embed --ldflags) \
   -DAPP_ROOT="\"$ROOT\"" -DPY_HOME="\"$PY_HOME\"" -DVENV_SITE="\"$VENV_SITE\"" \
   -o "$APP/Contents/MacOS/Mahmut" "$ROOT/.launcher.c"
rm -f "$ROOT/.launcher.c"

# Ikon: assets/Mahmut.icns yoksa uret (pyobjc ile, ek bagimlilik yok)
[ -f "$ROOT/assets/Mahmut.icns" ] || "$PYBIN" "$ROOT/make_icon.py" >/dev/null
cp "$ROOT/assets/Mahmut.icns" "$APP/Contents/Resources/Mahmut.icns"

cat > "$APP/Contents/Info.plist" <<P
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Mahmut</string>
  <key>CFBundleDisplayName</key><string>Mahmut: Voice Assistant</string>
  <key>CFBundleIdentifier</key><string>$BUNDLE_ID</string>
  <key>CFBundleExecutable</key><string>Mahmut</string>
  <key>CFBundleIconFile</key><string>Mahmut</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleVersion</key><string>1.0.0</string>
  <key>CFBundleShortVersionString</key><string>1.0.0</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>NSMicrophoneUsageDescription</key>
  <string>Sesli komutlarınızı metne çevirmek için mikrofonu kullanır.</string>
  <key>NSAppleEventsUsageDescription</key>
  <string>Mesajınızı Claude penceresine iletmek için kullanılır.</string>
</dict>
</plist>
P

# ---------------------------------------------------------------------
# ONEMLI: "--sign -" AD-HOC imzadir; makinedeki hicbir Developer ID /
# kurum sertifikasi KULLANILMAZ, keychain'e dokunulmaz. Buraya gercek bir
# kimlik yazma: dagitilan ikili o kurumun adina imzalanmis olur.
# ---------------------------------------------------------------------
codesign --force --sign - --identifier "$BUNDLE_ID" \
         --timestamp=none "$APP" >/dev/null 2>&1 \
  && echo "imzalandi (ad-hoc)" || echo "UYARI: codesign basarisiz, app yine de calisir"

# Guvenlik agi: imza gercekten ad-hoc mi? Degilse imzayi kaldir.
# NOT: `codesign ... | grep -q` KULLANMA. grep eslesince erken cikiyor,
# codesign SIGPIPE ile oluyor ve `set -o pipefail` yuzunden pipeline
# BASARISIZ sayiliyordu; imza dogruyken "yanlis" deyip siliyordu.
SIG="$(codesign -dv --verbose=4 "$APP" 2>&1 || true)"
case "$SIG" in
  *"Signature=adhoc"*)
    echo "imza dogrulandi: ad-hoc (kimlik kullanilmadi)" ;;
  *)
    echo "UYARI: imza ad-hoc DEGIL — kaldiriliyor (kimlik kullanilmamali)"
    codesign --remove-signature "$APP" >/dev/null 2>&1 || true ;;
esac

printf '%s' "$FINGERPRINT" > "$STAMP"
touch "$APP"          # Dock/Finder ikon onbellegini tazele

echo "hazir: $APP"
