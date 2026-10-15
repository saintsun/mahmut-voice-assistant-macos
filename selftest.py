"""Kurulum dogrulama: her parcayi tek tek dener ve ne eksikse soyler.

    ./.venv/bin/python selftest.py          # hizli kontroller
    ./.venv/bin/python selftest.py --mic    # 6 saniye konus, ne anladigini yazsin
"""
from __future__ import annotations

import platform
import subprocess
import sys

OK, BAD, WARN = "  ✅", "  ❌", "  ⚠️ "
problems: list[str] = []


def fail(msg: str, fix: str) -> None:
    print(f"{BAD} {msg}")
    problems.append(fix)


def main() -> int:
    print("\n=== Mahmut kendi kendini test ===\n")

    print("Sistem")
    if platform.machine() == "arm64":
        print(f"{OK} Apple Silicon ({platform.mac_ver()[0]})")
    else:
        fail(f"Mimari {platform.machine()}, arm64 degil", "Apple Silicon Mac gerekli.")
    print(f"{OK} Python {sys.version.split()[0]}")

    print("\nPaketler")
    for mod in ("numpy", "sounddevice", "mlx_whisper", "rumps", "AppKit", "Quartz"):
        try:
            __import__(mod)
            print(f"{OK} {mod}")
        except Exception as exc:
            fail(f"{mod} yuklenemedi: {exc}", "./setup.sh calistir.")

    # The AX permission is PER PROCESS: this script is not Mahmut.app, so
    # burada "yok" cikmasi normaldir. Belirleyici olan calisan uygulamanin
    # the state the app itself reports (.state.json).
    print("\nİzinler (çalışan uygulamanın bildirdiği)")
    import json as _json
    import os as _os
    import time as _time
    from claudevoice.config import STATE_PATH
    try:
        age = _time.time() - _os.path.getmtime(STATE_PATH)
        state = _json.load(open(STATE_PATH, encoding="utf-8"))
        if age > 15:
            print(f"{WARN} Mahmut.app calismiyor gibi "
                  f"(durum {int(age)} sn once guncellendi)")
            print("      `open Mahmut.app` ile baslat, sonra tekrar dene")
        elif state.get("ax_trusted"):
            print(f"{OK} Erisilebilirlik izni TANINDI")
        else:
            fail("Erisilebilirlik izni YOK: mesaj gonderilemez",
                 "Sistem Ayarlari > Gizlilik ve Guvenlik > Erisilebilirlik: "
                 "Mahmut girisini '-' ile SIL, '+' ile tekrar ekle, "
                 "sonra uygulamayi kapatip ac.")
        if age <= 15:
            print(f"{OK} Mikrofon akiyor" if state.get("mic_running")
                  else f"{BAD} Mikrofon acilamadi: {state.get('mic_error')}")
            print(f"{OK} Whisper hazir" if state.get("stt_ready")
                  else f"{BAD} Model hatasi: {state.get('stt_error')}")
    except FileNotFoundError:
        print(f"{WARN} Mahmut.app hic calismamis "
              "(`open Mahmut.app` ile baslat)")
    except Exception as exc:
        fail(f"Durum okunamadi: {exc}", "./run.sh ile calistirip hatayi gor.")

    print("\nMikrofon")
    try:
        import numpy as np
        import sounddevice as sd
        dev = sd.query_devices(kind="input")
        print(f"{OK} Giris cihazi: {dev['name']}")
        import queue as _q
        import threading as _th
        box: "_q.Queue" = _q.Queue()

        def _grab():
            try:
                with sd.InputStream(samplerate=16000, channels=1,
                                    dtype="float32", blocksize=1600) as st:
                    frames, _ = st.read(8000)          # ~0.5 sn
                box.put(float(np.sqrt(np.mean(np.square(frames)))))
            except Exception as e:
                box.put(e)

        _th.Thread(target=_grab, daemon=True).start()
        try:
            res = box.get(timeout=6)
        except _q.Empty:
            res = None
        if isinstance(res, Exception):
            fail(f"Mikrofon acilamadi: {res}",
                 "Sistem Ayarlari > Gizlilik ve Guvenlik > Mikrofon > Mahmut.app ac.")
        elif res is None:
            fail("Mikrofon 6 sn icinde cevap vermedi (izin bekliyor olabilir)",
                 "Once `open Mahmut.app` calistirip mikrofon iznini ver, "
                 "sonra bu testi tekrarla.")
        elif res > 1e-6:
            print(f"{OK} Ses akiyor (RMS {res:.5f})")
        else:
            print(f"{WARN} Sinyal geliyor ama tamamen sessiz: mikrofon kapali olabilir")
    except Exception as exc:
        fail(f"Mikrofon acilamadi: {exc}",
             "Sistem Ayarlari > Gizlilik ve Guvenlik > Mikrofon > Mahmut.app ac.")

    print("\nClaude")
    try:
        from claudevoice.config import Config
        from claudevoice.inject import Injector
        app = Injector(Config()["inject"]).find_app()
        if app:
            print(f"{OK} Claude.app calisiyor (pid {app.processIdentifier()})")
        else:
            print(f"{WARN} Claude.app acik degil: mesaj gonderilemez, once ac")
    except Exception as exc:
        fail(f"Claude aranamadi: {exc}", "./setup.sh calistir.")

    try:
        # All LIVE sessions are watched instead of a single transcript.
        from claudevoice.sessions import live_sessions
        ses = [x for x in live_sessions() if not x.routine]
        if ses:
            print(f"{OK} {len(ses)} canli oturum: "
                  + ", ".join(x.name for x in ses[:4])
                  + (" …" if len(ses) > 4 else ""))
        else:
            print(f"{WARN} Canli oturum yok: Claude Code'da bir konusma ac")
    except Exception as exc:
        fail(f"Oturumlar okunamadi: {exc}", "./setup.sh calistir.")

    print("\nSes (TTS)")
    try:
        from claudevoice.config import Config
        voice = Config().get("tts", "voice", "Yelda")
        out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
        if any(line.startswith(voice) for line in out.splitlines()):
            print(f"{OK} '{voice}' sesi kurulu")
        else:
            fail(f"'{voice}' sesi yok",
                 "Sistem Ayarlari > Erisilebilirlik > Konusulan Icerik > Sistem Sesi "
                 "> Turkce (Yelda) indir; ya da config.json'da baska bir ses yaz.")
    except Exception as exc:
        fail(f"Ses kontrolu basarisiz: {exc}", "say komutunu kontrol et.")

    if "--mic" in sys.argv:
        print("\nCanli test: 6 saniye konus (ornek: "
              "\"backend'deki endpoint'i refactor et tamam mahmut\")")
        try:
            import numpy as np
            import sounddevice as sd
            from claudevoice.config import Config
            from claudevoice.glossary import Glossary
            from claudevoice.phrases import Matcher
            from claudevoice.stt import Transcriber
            cfg = Config()
            t = Transcriber(cfg["stt"])
            print("     model yukleniyor…")
            t.warmup()
            print("     ▶ KONUS")
            rec = sd.rec(int(6 * 16000), samplerate=16000, channels=1, dtype="float32")
            sd.wait()
            print("     ⏳ cozumleniyor…")
            text = Glossary().correct(t.transcribe(rec[:, 0]))
            print(f"\n     ANLADIGI: {text!r}")
            done, payload = Matcher(cfg["phrases"]).find_send(text)
            print(f"     Gonderme kelimesi yakalandi mi: {'EVET' if done else 'hayir'}")
            if done:
                print(f"     Gonderilecek metin: {payload!r}")
        except Exception as exc:
            fail(f"Canli test basarisiz: {exc}", "Mikrofon iznini kontrol et.")

    print("\n" + "=" * 60)
    if problems:
        print(f"{len(problems)} sorun var:\n")
        for i, p in enumerate(problems, 1):
            print(f"  {i}. {p}")
        return 1
    print("Her sey hazir. `open Mahmut.app` ile baslat.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
