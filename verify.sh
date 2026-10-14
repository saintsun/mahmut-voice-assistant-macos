#!/bin/bash
# Uygulamayi yeniden baslatir, izinleri kontrol eder ve yazma yolunu dener.
# Enter'a BASMAZ: test metni Claude'un yazma alaninda belirir, sen silersin.
cd "$(dirname "$0")"
APP="$PWD/Mahmut.app"
PY=/opt/homebrew/bin/python3.13

echo "==> uygulama yeniden baslatiliyor"
pkill -f "Mahmut.app/Contents/MacOS/Mahmut" 2>/dev/null
pkill -f "claudevoice.app" 2>/dev/null
sleep 2
rm -f .state.json .inject_test.json
open "$APP"

# Model yuklenmesi 30 sn'yi bulabiliyor; sadece dosyanin VARLIGINA bakmak
# "mikrofon/whisper yok" diye yanlis alarm veriyordu.
printf "==> hazir olmasi bekleniyor "
for i in $(seq 1 90); do
  if [ -f .state.json ] && [ "$("$PY" -c "
import json
try: print(json.load(open('.state.json'))['stt_ready'])
except Exception: print(False)" 2>/dev/null)" = "True" ]; then break; fi
  printf "."; sleep 1
done
echo

[ -f .state.json ] || { echo "❌ Uygulama baslamadi. ./run.sh ile hatayi gor."; exit 1; }

AX=$("$PY" -c "import json;print(json.load(open('.state.json'))['ax_trusted'])")
"$PY" - <<'P'
import json
d = json.load(open(".state.json"))
m = {True: "✅", False: "❌"}
print(f"  {m[bool(d['ax_trusted'])]} Erisilebilirlik izni")
print(f"  {m[bool(d['mic_running'])]} Mikrofon")
print(f"  {m[bool(d['stt_ready'])]} Whisper modeli")
ses = d.get("watched_sessions") or []
print(f"  {m[bool(ses)]} Claude oturumu: {', '.join(ses) if ses else 'yok'}")
P

if [ "$AX" != "True" ]; then
  cat <<'EOF'

❌ Erisilebilirlik izni taninmadi.

   Sistem Ayarlari > Gizlilik ve Guvenlik > Erisilebilirlik
     1. Listedeki "Mahmut" girisini sec ve "−" ile SIL
        (eski "ClaudeVoice" girisi kaldiysa onu da sil
         Mahmut gorunur)
     2. "+" ile bu klasordeki Mahmut.app'i tekrar EKLE
     3. Anahtari ACIK konuma getir
     4. Bu scripti tekrar calistir: ./verify.sh

   (Sadece kapatip acmak yetmez — girisi silip yeniden eklemek gerekir.)
EOF
  exit 1
fi

echo
echo "==> yazma testi (Enter'a BASILMAYACAK)"
rm -f .inject_test.json
open -n -a "$APP" --args --test-inject
for i in $(seq 1 20); do [ -f .inject_test.json ] && break; sleep 1; done

"$PY" - <<'P'
import json, sys
try:
    d = json.load(open(".inject_test.json"))
except Exception:
    print("  ❌ test sonucu olusmadi"); sys.exit(1)
if d.get("injected"):
    print("  ✅ Claude'un yazma alanina YAZILDI")
    if d.get("note"):
        print(f"     not: {d['note']}")
        print("     -> Metin baska yere gittiyse Claude'da composer'a bir kez tikla")
    print("\n  Claude'un yazma alanina bak: test metni orada olmali (gonderilmedi).")
    print("  Sil ve kullanmaya basla:  menubar > Dinleme: Acik  ya da  \"hey claude\"")
else:
    print(f"  ❌ yazilamadi: {d.get('note') or d.get('error')}")
    sys.exit(1)
P
