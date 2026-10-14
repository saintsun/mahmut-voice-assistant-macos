"""Metni Turkce / Ingilizce parcalara bolup her birini kendi sesiyle okutur.

macOS `say` gomulu [[voic ...]] komutunu desteklemiyor (parantezleri sesli
okuyor), bu yuzden her dil parcasi ayri bir `say` cagrisiyla seslendirilir.

"Backend'deki endpoint'i refactor ettim"
  -> [EN "Backend"] [TR "'deki"] [EN "endpoint"] [TR "'i"] [EN "refactor"]
     [TR "ettim"]
Yan yana ayni dildeki kelimeler tek parcada birlestirilir, boylece gereksiz
ses degisimi olmaz.
"""
from __future__ import annotations

import re

from .glossary import TERMS
from .phrases import fold

# Sozlukteki tum terimlerin kelimeleri (cok kelimeli terimler de parcalanir)
_EN_WORDS: set[str] = set()
for _t in TERMS:
    for _w in _t.split():
        _EN_WORDS.add(fold(_w))

# Yazilim disinda da sik gecen Ingilizce kelimeler
_EN_WORDS |= {
    "ok", "okay", "fix", "bug", "issue", "update", "upgrade", "install",
    "setup", "run", "start", "stop", "restart", "check", "clean", "clear",
    "default", "custom", "enable", "disable", "error", "warning", "success",
    "failed", "done", "ready", "pending", "active", "status", "version",
    "file", "folder", "path", "input", "output", "value", "key", "name",
    "true", "false", "null", "undefined", "void", "static", "public",
    "private", "return", "export", "const", "let", "var", "new", "delete",
    # oturum adlarinda ve gunluk konusmada gecen Ingilizce kelimeler
    "voice", "control", "dashboard", "admin", "user", "client", "mobile",
    "desktop", "web", "app", "core", "main", "dev", "prod", "staging",
    "legacy", "modern", "light", "dark", "theme", "layout", "header",
    "footer", "sidebar", "modal", "button", "form", "field", "label",
    "search", "filter", "sort", "list", "detail", "summary", "report",
}

# Turkce'de de aynen kullanilan, Turkce telaffuz edilmesi gereken kelimeler
_TR_OVERRIDE = {
    "test", "format", "normal", "video", "problem", "sistem", "proje",
    "data", "server", "port", "link", "mail", "stil", "kontrol", "method",
}
_EN_WORDS -= _TR_OVERRIDE

# Buyuk harfli kisaltmalar (API, JSON, SQL...) Ingilizce okunur
_ACRONYM = re.compile(r"^[A-Z]{2,6}$")
_TOKEN = re.compile(r"[0-9A-Za-zÇĞİIÖŞÜçğıiöşü]+(?:['’][0-9A-Za-zÇĞİIÖŞÜçğıiöşü]+)*")


def _classify(word: str) -> str:
    """Tek kelime: 'en' mi 'tr' mi?"""
    f = fold(word)
    if not f or f.isdigit():
        return "tr"
    if f in _TR_OVERRIDE:
        return "tr"
    if _ACRONYM.match(word):
        return "en"
    return "en" if f in _EN_WORDS else "tr"


def _split_token(word: str, start: int) -> list[tuple[str, int, int]]:
    """Kesme isaretli kelimeyi govde + Turkce ek olarak ayirir.

    "endpoint'i" -> [("en", govde), ("tr", "'i")]
    Govde Turkce ise bolmeye gerek yok.
    """
    m = re.search(r"['’]", word)
    if not m:
        return [(_classify(word), start, start + len(word))]
    stem = word[: m.start()]
    lang = _classify(stem)
    if lang == "tr":
        return [("tr", start, start + len(word))]
    return [("en", start, start + m.start()),
            ("tr", start + m.start(), start + len(word))]


def split_runs(text: str) -> list[tuple[str, str]]:
    """[(dil, metin), ...] — metnin tamami, sirayla, bosluk/noktalama dahil."""
    if not text.strip():
        return []
    marks: list[tuple[str, int, int]] = []
    for m in _TOKEN.finditer(text):
        marks.extend(_split_token(m.group(0), m.start()))
    if not marks:
        return [("tr", text)]

    runs: list[tuple[str, str]] = []
    cursor = 0
    cur_lang = marks[0][0]
    for lang, s, e in marks:
        if lang != cur_lang:
            # Dil degisiyor: buraya kadarki her seyi onceki dile ver.
            chunk = text[cursor:s]
            if chunk.strip():
                runs.append((cur_lang, chunk))
                cursor = s
            cur_lang = lang
    tail = text[cursor:]
    if tail.strip():
        runs.append((cur_lang, tail))

    # Ayni dildeki komsu parcalari birlestir
    merged: list[tuple[str, str]] = []
    for lang, chunk in runs:
        if merged and merged[-1][0] == lang:
            merged[-1] = (lang, merged[-1][1] + chunk)
        else:
            merged.append((lang, chunk))
    return merged
