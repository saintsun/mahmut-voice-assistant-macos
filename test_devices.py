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
