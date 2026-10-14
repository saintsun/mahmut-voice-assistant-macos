"""Small Turkish suffix helpers so spoken announcements sound right."""
from __future__ import annotations

_BACK = set("aıou")
_FRONT = set("eiöü")
_VOWELS = _BACK | _FRONT


def tr_lower(s: str) -> str:
    """Turkish-aware lowercase (I->ı, İ->i)."""
    return s.replace("I", "ı").replace("İ", "i").lower()


def dative(name: str) -> str:
    """Dative case: 'Voice Control' -> "Voice Control'a",
    'Admin Panel' -> "Admin Panel'e".

    The vowel (a/e) follows the last vowel's backness; a buffer 'y' is
    inserted when the word ends in a vowel.
    """
    base = name.strip()
    if not base:
        return base
    low = tr_lower(base)
    last_vowel = next((ch for ch in reversed(low) if ch in _VOWELS), None)
    vowel = "a" if (last_vowel is None or last_vowel in _BACK) else "e"
    buffer_y = "y" if low[-1] in _VOWELS else ""
    return f"{base}'{buffer_y}{vowel}"
