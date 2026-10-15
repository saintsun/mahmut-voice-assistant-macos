#!/usr/bin/env python3
"""Command matching tests - what must fire, and what must NOT.

The false positives here are the expensive kind: a sentence that was never
meant as a command sends the buffer to Claude. One of them really happened,
a whole conversation went out because "ver" matched the send phrase "over".
"""
import sys

from claudevoice.phrases import Matcher, word_eq, word_eq_strict

CFG = {
    "name": "mahmut",
    "send": ["tamam {name}", "{name} tamam", "tamam gonder", "gonder {name}",
             "tamam over", "yolla {name}"],
    "cut": ["{name} kes", "kes {name}", "{name} sus", "sus {name}"],
    "listen": ["{name} basla", "basla {name}"],
    "sleep": ["{name} dur", "dur {name}"],
    "list": ["listeyi getir {name}", "liste {name}"],
    "cancel": ["iptal {name}", "{name} iptal"],
    "reply": ["cevap {name}", "{name} cevap"],
    "switch": ["sec {name}", "{name} sec"],
    "wake": ["hey {name}", "uyan {name}"],
    "word_variants": {
        "mahmut": ["mahmut", "mahmud", "mamut", "marmut"],
        "kes": ["kes", "kess", "kec", "ces"],
        "gonder": ["gonder", "gondere", "gonda"],
        "tamam": ["tamam", "taman", "tamamm"],
    },
}

# The phrases are written with {name}; the Matcher is given them expanded.
CFG = {k: ([v.replace("{name}", "mahmut") for v in val] if isinstance(val, list)
           else val) for k, val in CFG.items()}

M = Matcher(CFG)
CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


def eq(got, want, label):
    assert got == want, f"{label}: beklenen {want!r}, gelen {got!r}"


# --- the send phrase fires ----------------------------------------------
@case("'tamam mahmut' gonderir")
def _():
    ok, payload = M.find_send("migration dosyasını güncelledim tamam mahmut")
    eq(ok, True, "gonder")
    eq(payload, "migration dosyasını güncelledim", "kalan metin")


@case("yanlis duyulan 'taman mamut' da gonderir")
def _():
    eq(M.find_send("bunu yap taman mamut")[0], True, "gonder")


@case("'tamam over' gonderir")
def _():
    eq(M.find_send("hazırım tamam over")[0], True, "gonder")


# --- and does NOT fire where it must not --------------------------------
@case("'al bunu çözümle ver' GONDERMEZ (gercek olay)")
def _():
    eq(M.find_send("al bunu çözümle ver")[0], False, "gonder")


@case("'şunu bana ver' GONDERMEZ")
def _():
    eq(M.find_send("şunu bana ver")[0], False, "gonder")


@case("tek basina 'ver' GONDERMEZ")
def _():
    eq(M.find_send("ver")[0], False, "gonder")


@case("adi gecmeyen cumle GONDERMEZ")
def _():
    eq(M.find_send("tamam o zaman devam edelim")[0], False, "gonder")


# --- the other commands keep working ------------------------------------
@case("'mahmut kes' okumayi keser")
def _():
    eq(M.is_cut("mahmut kes"), True, "kes")


@case("'ces mahmut' de keser (yazim seti)")
def _():
    eq(M.is_cut("ces mahmut"), True, "kes")


@case("'kesinlikle haklısın' KESMEZ")
def _():
    eq(M.is_cut("kesinlikle haklısın"), False, "kes")


@case("'mahmut başla' dinlemeyi acar")
def _():
    eq(M.is_listen("mahmut basla"), True, "basla")


@case("'mahmut dur' dinlemeyi durdurur")
def _():
    eq(M.is_sleep("mahmut dur"), True, "dur")


# --- the rule behind it -------------------------------------------------
@case("word_eq 4 harfte bir harf tolere eder")
def _():
    eq(word_eq("ver", "over"), True, "toleransli")


@case("word_eq_strict tolere ETMEZ")
def _():
    eq(word_eq_strict("ver", "over"), False, "katı")


@case("word_eq_strict cift harfi yine yok sayar")
def _():
    eq(word_eq_strict("kess", "kes"), True, "cift harf")


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
