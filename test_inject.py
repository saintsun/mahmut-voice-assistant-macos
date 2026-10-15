"""Claude.app'e yazma testi. GUVENLI: Enter'a BASMAZ.

Metin Claude'un yazma alaninda belirir, gonderilmez. Gorup silersin.

    ./.venv/bin/python test_inject.py
"""
from __future__ import annotations

import sys
import time

from claudevoice.config import Config
from claudevoice.inject import Injector, ax_trusted

TEXT = "Mahmut testi, bu mesaj gonderilmedi, silebilirsin."


def main() -> int:
    if not ax_trusted():
        print("❌ Erisilebilirlik izni yok.\n")
        print("   Sistem Ayarlari > Gizlilik ve Guvenlik > Erisilebilirlik")
        print("   Listeye Mahmut.app ekle ve ACIK konuma getir.\n")
        print("   Paneli acmak icin:")
        print('   open "x-apple.systempreferences:'
              'com.apple.preference.security?Privacy_Accessibility"')
        return 1

    cfg = Config()["inject"]
    cfg = dict(cfg)
    cfg["press_enter"] = False          # <-- gonderme, sadece yaz

    inj = Injector(cfg)
    if inj.find_app() is None:
        print("❌ Claude.app calismiyor. Once Claude'u ac.")
        return 1

    print("3 saniye içinde Claude penceresine yazılacak (Enter'a BASILMAYACAK)…")
    time.sleep(3)
    ok, note = inj.send(TEXT)
    if ok:
        print("✅ Yazildi. Claude'un yazma alanina bak.")
        if note:
            print(f"   Not: {note}")
            print("   -> Metin baska yere gittiyse Claude'da bir kez composer'a tikla.")
    else:
        print(f"❌ Basarisiz: {note}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
