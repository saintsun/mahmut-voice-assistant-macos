"""Splits text into Turkish / English runs so each is read in its own voice.

macOS `say` ignores the embedded [[voic ...]] command (it reads the brackets
aloud), so every language run is spoken by a separate `say` call.

"Backend'deki endpoint'i refactor ettim"
  -> [EN "Backend"] [TR "'deki"] [EN "endpoint"] [TR "'i"] [EN "refactor"]
     [TR "ettim"]
Adjacent runs in the same language are merged into one, so the voice does not
switch more often than it has to.
"""
from __future__ import annotations

import re

from .glossary import TERMS
from .phrases import fold

# Every word from the glossary terms (multi-word terms are split too)
_EN_WORDS: set[str] = set()
for _t in TERMS:
    for _w in _t.split():
        _EN_WORDS.add(fold(_w))

# Common English words that show up outside software talk as well
_EN_WORDS |= {
    "ok", "okay", "fix", "bug", "issue", "update", "upgrade", "install",
    "setup", "run", "start", "stop", "restart", "check", "clean", "clear",
    "default", "custom", "enable", "disable", "error", "warning", "success",
    "failed", "done", "ready", "pending", "active", "status", "version",
    "file", "folder", "path", "input", "output", "value", "key", "name",
    "true", "false", "null", "undefined", "void", "static", "public",
    "private", "return", "export", "const", "let", "var", "new", "delete",
    # English words that appear in session names and everyday speech
    "voice", "control", "dashboard", "admin", "user", "client", "mobile",
    "desktop", "web", "app", "core", "main", "dev", "prod", "staging",
    "legacy", "modern", "light", "dark", "theme", "layout", "header",
    "footer", "sidebar", "modal", "button", "form", "field", "label",
    "search", "filter", "sort", "list", "detail", "summary", "report",
}

# Words borrowed into Turkish that must be pronounced the Turkish way
_TR_OVERRIDE = {
    "test", "format", "normal", "video", "problem", "sistem", "proje",
    "data", "server", "port", "link", "mail", "stil", "kontrol", "method",
}
_EN_WORDS -= _TR_OVERRIDE

# Upper-case acronyms (API, JSON, SQL...) are read in English
_ACRONYM = re.compile(r"^[A-Z]{2,6}$")
_TOKEN = re.compile(r"[0-9A-Za-zÇĞİIÖŞÜçğıiöşü]+(?:['’][0-9A-Za-zÇĞİIÖŞÜçğıiöşü]+)*")


def _classify(word: str) -> str:
    """One word: is it 'en' or 'tr'?"""
    f = fold(word)
    if not f or f.isdigit():
        return "tr"
    if f in _TR_OVERRIDE:
        return "tr"
    if _ACRONYM.match(word):
        return "en"
    return "en" if f in _EN_WORDS else "tr"


def _split_token(word: str, start: int) -> list[tuple[str, int, int]]:
    """Splits an apostrophised word into stem + Turkish suffix.

    "endpoint'i" -> [("en", stem), ("tr", "'i")]
    No split is needed when the stem is Turkish.
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
    """[(lang, text), ...] - the whole text in order, spacing and punctuation
    included."""
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
            # The language changes here: everything so far belongs to the
            # previous one.
            chunk = text[cursor:s]
            if chunk.strip():
                runs.append((cur_lang, chunk))
                cursor = s
            cur_lang = lang
    tail = text[cursor:]
    if tail.strip():
        runs.append((cur_lang, tail))

    # Merge neighbouring runs that share a language
    merged: list[tuple[str, str]] = []
    for lang, chunk in runs:
        if merged and merged[-1][0] == lang:
            merged[-1] = (lang, merged[-1][1] + chunk)
        else:
            merged.append((lang, chunk))
    return merged
