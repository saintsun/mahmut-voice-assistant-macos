"""Claude'un markdown cevabini sesli okunabilir duz metne cevirir.

Kod bloklari, tablolar, dosya yollari, URL'ler ve isaretleme karakterleri
atilir; geriye sadece konusulacak cumleler kalir.
"""
from __future__ import annotations

import re

_FENCE = re.compile(r"```.*?(?:```|\Z)", re.DOTALL)
_FENCE_TILDE = re.compile(r"~~~.*?(?:~~~|\Z)", re.DOTALL)
_HTML = re.compile(r"<[^>\n]{1,200}>")
_LINK = re.compile(r"\[([^\]\n]*)\]\(([^)\n]*)\)")
_IMAGE = re.compile(r"!\[([^\]\n]*)\]\([^)\n]*\)")
_URL = re.compile(r"\b(?:https?://|www\.)\S+")
_INLINE = re.compile(r"`([^`\n]+)`")
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEP = re.compile(r"^\s*\|?[\s:\-|]+\|[\s:\-|]*$")
_HR = re.compile(r"^\s*([-*_])\s*(\1\s*){2,}$")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*")
_QUOTE = re.compile(r"^\s{0,3}>+\s?")
_BULLET = re.compile(r"^\s*(?:[-*+]|\d{1,3}[.)])\s+")
_EMPH = re.compile(r"(\*\*\*|\*\*|\*|___|__|_|~~)")
_PATH = re.compile(r"(?:(?:\.{0,2}/)|(?:[A-Za-z]:\\))[\w.\-/\\]{2,}(?::\d+(?::\d+)?)?")
_CHECKBOX = re.compile(r"^\s*\[[ xX]\]\s*")
_HEXY = re.compile(r"\b[0-9a-fA-F]{8,}\b")
_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
    "\U00002190-\U000021FF\U00002B00-\U00002BFF\uFE0F\u200d]+"
)
# Sesli okunurken anlami olmayan isaretler. Tireler virgule cevrilir
# (dogal duraklama), geri kalani atilir — "--" diye okunmasin.
_LONG_DASH = re.compile(r"\s*(?:-{2,}|[—–―])\s*")
_LONE_DASH = re.compile(r"(?<=[\s,.;:])-(?=[\s,.;:])|\s-\s")
_ARROW = re.compile(r"\s*(?:->|=>|<-|<=>)\s*")
_UNSPOKEN = re.compile(r"[*_#`|~^<>{}\[\]\\/+=•·●▪◦“”„«»]")
_MULTI_PUNCT = re.compile(r"([,.;:!?])\s*(?:[,.;:]\s*)+")
_WS = re.compile(r"[ \t]+")
_NL = re.compile(r"\n{2,}")


def _inline_repl(m: re.Match) -> str:
    """Kisa inline kod okunur ('null', 'async'), uzun olan atilir."""
    inner = m.group(1).strip()
    if len(inner) <= 20 and re.fullmatch(r"[\w\s.'-]+", inner) and "/" not in inner:
        return inner
    return ""


def to_speech(markdown: str, code_placeholder: str = "kod bloğu",
              max_chars: int = 1200) -> str:
    if not markdown:
        return ""
    t = markdown

    ph = f" {code_placeholder}. " if code_placeholder else " "
    t = _FENCE.sub(ph, t)
    t = _FENCE_TILDE.sub(ph, t)
    t = _IMAGE.sub(r" \1 ", t)
    t = _LINK.sub(r"\1", t)
    t = _INLINE.sub(_inline_repl, t)
    t = _URL.sub(" bir bağlantı ", t)
    t = _HTML.sub(" ", t)

    lines_out: list[str] = []
    table_seen = False
    for line in t.split("\n"):
        if _TABLE_SEP.match(line) or _TABLE_ROW.match(line):
            if not table_seen:
                lines_out.append("Bir tablo.")
                table_seen = True
            continue
        table_seen = False
        if _HR.match(line):
            continue
        line = _HEADING.sub("", line)
        line = _QUOTE.sub("", line)
        line = _CHECKBOX.sub("", line)
        line = _BULLET.sub("", line)
        lines_out.append(line)

    t = "\n".join(lines_out)
    t = _EMPH.sub("", t)
    t = _PATH.sub(" ", t)
    t = _HEXY.sub(" ", t)
    t = _EMOJI.sub(" ", t)
    t = t.replace("|", " ")

    # Ard arda tekrarlayan yer tutuculari tek'e indir
    if code_placeholder:
        t = re.sub(rf"(?:\s*{re.escape(code_placeholder)}\.\s*){{2,}}",
                   f" {code_placeholder}. ", t)

    # Okunmayacak isaretleri temizle
    t = _ARROW.sub(", ", t)
    t = _LONG_DASH.sub(", ", t)
    t = _LONE_DASH.sub(", ", t)
    t = _UNSPOKEN.sub(" ", t)

    t = _WS.sub(" ", t)
    t = _NL.sub("\n", t)
    t = "\n".join(ln.strip() for ln in t.split("\n"))
    t = re.sub(r"\n+", ". ", t)
    t = re.sub(r"\.\s*\.(\s*\.)*", ". ", t)
    t = re.sub(r"\s*([:;,])\s*\.", r"\1 ", t)      # "düzelttim:." -> "düzelttim:"
    t = re.sub(r"\s+([.,:;!?])", r"\1", t)
    t = _MULTI_PUNCT.sub(r"\1 ", t)
    t = _WS.sub(" ", t).strip(" .,:;-—–\n\t")

    if not t:
        return ""
    if len(t) > max_chars:
        cut = t.rfind(" ", 0, max_chars)
        t = t[: cut if cut > 0 else max_chars] + ". Devamı ekranda."
    return t
