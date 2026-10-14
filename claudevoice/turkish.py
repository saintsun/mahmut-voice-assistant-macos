"""Kucuk Turkce ek yardimcilari — sesli bildirimler dogru duyulsun diye."""
from __future__ import annotations

_BACK = set("aıou")
_FRONT = set("eiöü")
_VOWELS = _BACK | _FRONT


def tr_lower(s: str) -> str:
    """Turkce'ye uygun kucuk harf (I->ı, İ->i)."""
    return s.replace("I", "ı").replace("İ", "i").lower()


def dative(name: str) -> str:
    """Yonelme hali: 'Voice Control' -> "Voice Control'a",
    'Kunaz Geliştirme' -> "Kunaz Geliştirme'ye".

    Son unlunun kalin/ince olusuna gore a/e secilir; kelime unluyle
    bitiyorsa araya kaynastirma 'y'si girer.
    """
    base = name.strip()
    if not base:
        return base
    low = tr_lower(base)
    last_vowel = next((ch for ch in reversed(low) if ch in _VOWELS), None)
    vowel = "a" if (last_vowel is None or last_vowel in _BACK) else "e"
    buffer_y = "y" if low[-1] in _VOWELS else ""
    return f"{base}'{buffer_y}{vowel}"
