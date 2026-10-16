#!/usr/bin/env python3
"""Device selection tests - NO audio hardware required (fake device list).

The rules:
  * nothing picked: headset when present, built-in otherwise
  * BUILT-IN picked: stays built-in even when a headset is connected
  * HEADSET picked: the headset while present, built-in once it is gone
  * invalid choice: falls back to automatic (the system is never left deaf)
"""
import sys

from claudevoice.audio import pick_device, resolve_device, resolve_output

BUILTIN = {"name": "MacBook Air Microphone", "max_input_channels": 1}
AIRPODS = {"name": "Eren’s AirPods Pro 3", "max_input_channels": 1}
PHONE = {"name": "SaintsPhone Microphone", "max_input_channels": 1}

WITH_HEADSET = [(0, PHONE), (1, BUILTIN), (2, AIRPODS)]
NO_HEADSET = [(0, PHONE), (1, BUILTIN)]

OUT_BOTH = [(0, {"name": "MacBook Air Speakers", "max_output_channels": 2}),
            (1, {"name": "Eren’s AirPods Pro 3", "max_output_channels": 2})]
OUT_ONLY_MAC = [(0, {"name": "MacBook Air Speakers", "max_output_channels": 2})]

CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


def eq(got, want, label):
    assert got == want, f"{label}: beklenen {want!r}, gelen {got!r}"


# --- automatic (nothing picked by the user) ---
@case("otomatik + kulaklık var  -> kulaklık")
def _():
    cfg = {"prefer": "headset", "device": None}
    eq(resolve_device(cfg, WITH_HEADSET)[1], AIRPODS["name"], "oto/headset")


@case("otomatik + kulaklık yok  -> dahili")
def _():
    cfg = {"prefer": "headset", "device": None}
    eq(resolve_device(cfg, NO_HEADSET)[1], BUILTIN["name"], "oto/builtin")


@case("otomatik + prefer=builtin -> kulaklık varken bile dahili")
def _():
    cfg = {"prefer": "builtin", "device": None}
    eq(resolve_device(cfg, WITH_HEADSET)[1], BUILTIN["name"], "oto/prefer")


# --- when the user picked a device EXPLICITLY ---
@case("dahili seçili + kulaklık takılı -> yine dahili")
def _():
    cfg = {"prefer": "headset", "device": "MacBook Air Microphone"}
    eq(resolve_device(cfg, WITH_HEADSET)[1], BUILTIN["name"], "secim/builtin")


@case("kulaklık seçili + takılı      -> kulaklık")
def _():
    cfg = {"prefer": "builtin", "device": "AirPods"}
    eq(resolve_device(cfg, WITH_HEADSET)[1], AIRPODS["name"], "secim/headset")


@case("kulaklık seçili + çıkarılmış  -> dahiliye düşer")
def _():
    cfg = {"prefer": "headset", "device": "AirPods"}
    eq(resolve_device(cfg, NO_HEADSET)[1], BUILTIN["name"], "secim/dusme")


@case("indeksle seçim")
def _():
    cfg = {"prefer": "headset", "device": 1}
    eq(resolve_device(cfg, WITH_HEADSET), (1, BUILTIN["name"]), "secim/indeks")


@case("geçersiz seçim -> otomatiğe düşer")
def _():
    cfg = {"prefer": "headset", "device": "Olmayan Cihaz"}
    eq(resolve_device(cfg, WITH_HEADSET)[1], AIRPODS["name"], "secim/gecersiz")


@case("tam ad, parça addan önce gelir")
def _():
    items = [(0, {"name": "Mikrofon Pro", "max_input_channels": 1}),
             (1, {"name": "Mikrofon", "max_input_channels": 1})]
    eq(pick_device("Mikrofon", items), (1, "Mikrofon"), "tam-ad")


# --- output (speaker) ---
@case("çıkış seçilmemiş -> sistem varsayılanı")
def _():
    eq(resolve_output({"output_device": None}, OUT_BOTH)[0], None, "cikis/oto")


@case("çıkış seçili + var -> o cihaz")
def _():
    got = resolve_output({"output_device": "AirPods"}, OUT_BOTH)
    eq(got, (1, "Eren’s AirPods Pro 3"), "cikis/secim")


@case("çıkış seçili + yok -> sistem varsayılanına düşer")
def _():
    eq(resolve_output({"output_device": "AirPods"}, OUT_ONLY_MAC)[0], None,
       "cikis/dusme")


# --- microphone watchdog: how often does it rescan PortAudio? -----------
# A rescan re-enumerates every device and wakes Continuity devices (the
# iPhone microphone), so a rescan that fixes nothing has to back off.
class _FakeMic:
    def __init__(self):
        self.device_name = "MacBook Air Microphone"
        self.enabled = True
        self.rescans = 0
        self.seg = type("S", (), {"speaking": False})()

    def silent_for(self):
        return 10.0                      # hep sessiz: cihaz geri gelmiyor

    def refresh_device(self, rescan=False):
        self.rescans += 1
        return None


def _watchdog_stub():
    import threading
    from claudevoice.app import ClaudeVoice, LIVE
    s = ClaudeVoice.__new__(ClaudeVoice)
    s.mic = _FakeMic()
    s.speaker = type("S", (), {"busy": False})()
    s.lock = threading.RLock()
    s.state = LIVE
    s._capture = None
    s.buffer = ""
    s._set_status = lambda *a, **k: None
    return s


def _run_minutes(stub, minutes, step=4.0):
    """Runs the watchdog for N minutes of fake time, 4 s per tick."""
    from claudevoice.app import ClaudeVoice
    import claudevoice.app as app_mod
    real_time = app_mod.time
    clock = {"t": 1000.0}
    app_mod.time = type("T", (), {"monotonic": staticmethod(lambda: clock["t"]),
                                  "strftime": real_time.strftime,
                                  "time": real_time.time})()
    try:
        for _ in range(int(minutes * 60 / step)):
            ClaudeVoice._check_mic(stub)
            clock["t"] += step
    finally:
        app_mod.time = real_time


@case("sürekli sessizlikte tarama sayısı geri adımla düşer")
def _():
    stub = _watchdog_stub()
    _run_minutes(stub, 10)
    # geri adim: 5, 15, 45, 135, 300, 300... -> 10 dakikada en fazla 8 tarama
    assert stub.mic.rescans <= 8, f"10 dakikada {stub.mic.rescans} tarama (çok)"
    assert stub.mic.rescans >= 4, f"hiç denemiyor: {stub.mic.rescans}"


@case("geri adım olmasa 10 dakikada 150 tarama olurdu")
def _():
    stub = _watchdog_stub()
    from claudevoice.app import ClaudeVoice
    eq(ClaudeVoice.RESCAN_MAX, 300.0, "üst sınır")
    eq(ClaudeVoice.RESCAN_MIN, 5.0, "alt sınır")


def main() -> int:
    bad = 0
    for name, fn in CASES:
        try:
            fn()
            print(f"  ✅ {name}")
        except AssertionError as exc:
            bad += 1
            print(f"  ❌ {name}\n     {exc}")
    print(f"\n{len(CASES) - bad}/{len(CASES)} test geçti")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
