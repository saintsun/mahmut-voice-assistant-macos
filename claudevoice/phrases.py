"""Catches radio-style command words.

Transcription spells the wake name differently every time (Mahmud, Mamut,
Marmut) and accented characters shift as well. Matching therefore runs:
  1) over text folded to plain ASCII,
  2) word by word, tolerating one wrong letter (edit distance <= 1).
"""
from __future__ import annotations

import re
import unicodedata

_TR_MAP = str.maketrans({
    "ç": "c", "Ç": "c", "ğ": "g", "Ğ": "g", "ı": "i", "I": "i",
    "İ": "i", "i": "i", "ö": "o", "Ö": "o", "ş": "s", "Ş": "s",
    "ü": "u", "Ü": "u", "â": "a", "Â": "a", "î": "i", "Î": "i",
    "û": "u", "Û": "u", "é": "e", "É": "e",
})

# A period or apostrophe INSIDE a word does NOT split it: "6.yi" -> "6yi",
# "Mahmut'un" -> "mahmutun". Transcription writes ordinals that way, and
# splitting "6.yi sec mahmut" into 4 tokens never matched a 3-word pattern.
_W = r"[0-9A-Za-zÇĞİIÖŞÜçğıiöşü]"
_WORD_RE = re.compile(rf"{_W}+(?:['’.]{_W}+)*")


def fold(text: str) -> str:
    """Folds text to plain lowercase ASCII for matching."""
    text = text.replace("'", "").replace("’", "").replace(".", "")
    text = text.translate(_TR_MAP)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower()


def tokenize(text: str) -> list[tuple[str, int, int]]:
    """Returns a list of (normalized_word, start_index, end_index).

    The indices refer to the ORIGINAL text, so the raw message can be cut at
    the right place once the terminator is found.
    """
    out = []
    for m in _WORD_RE.finditer(text):
        w = fold(m.group(0))
        if w:
            out.append((w, m.start(), m.end()))
    return out


def _edit_distance_le1(a: str, b: str) -> bool:
    """Is the edit distance between a and b at most 1?"""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:                              # one letter replaced
        diff = sum(1 for x, y in zip(a, b) if x != y)
        return diff <= 1
    if la > lb:                               # one letter deleted from a
        a, b, la, lb = b, a, lb, la
    i = j = 0
    skipped = False
    while i < la and j < lb:
        if a[i] == b[j]:
            i += 1
            j += 1
        elif skipped:
            return False
        else:
            skipped = True
            j += 1
    return True


def _dedup(word: str) -> str:
    """Collapses repeated letters: 'kess' -> 'kes'."""
    out = []
    for ch in word:
        if not out or out[-1] != ch:
            out.append(ch)
    return "".join(out)


def word_eq_strict(spoken: str, target: str) -> bool:
    """Equality with NO letter tolerance (doubled letters still ignored).

    Used where a single word is the whole command. "over" is a send phrase on
    its own, and one letter of tolerance made the very common Turkish word
    "ver" match it: an entire conversation was sent to Claude without the
    send phrase ever being said. With no context around it, a one-word
    command has to be heard exactly.
    """
    return spoken == target or _dedup(spoken) == _dedup(target)


def word_eq(spoken: str, target: str) -> bool:
    """Exact for short words, one-letter tolerant from 4 letters up.

    Doubled letters are ignored either way: transcription usually writes "kes"
    as "kess", and three-letter commands do not qualify for fuzzy matching.
    """
    if spoken == target:
        return True
    if _dedup(spoken) == _dedup(target):
        return True
    # NO tolerance for spellings that contain DIGITS: "1inci" and "5inci"
    # differ by one letter, so fuzzy equality read the 5th item as the 1st.
    if any(ch.isdigit() for ch in spoken) or any(ch.isdigit() for ch in target):
        return False
    if len(target) >= 4:
        return _edit_distance_le1(spoken, target)
    return False


class Matcher:
    """Compiles the command patterns from the config and finds them in text."""

    def __init__(self, phrases_cfg: dict):
        self.name = fold(phrases_cfg.get("name", "mahmut"))
        variants = [fold(v) for v in (phrases_cfg.get("name_variants")
                                      or phrases_cfg.get("claude_variants")
                                      or [self.name])]
        if self.name not in variants:
            variants.insert(0, self.name)
        self._variants = set(variants)
        # Spelling sets: transcription writes the same command in wildly
        # different ways ("kes" -> ces / kec / kiss / chris). The accepted
        # spellings for each canonical word are collected here.
        self._wordsets: dict[str, set[str]] = {}
        for canon, alts in (phrases_cfg.get("word_variants") or {}).items():
            c = fold(canon)
            self._wordsets[c] = {fold(a) for a in alts} | {c}
        self._wordsets.setdefault(self.name, set(self._variants))
        self._wordsets[self.name] |= set(self._variants)
        self.send = self._compile(phrases_cfg.get("send", []), variants, self.name)
        self.cancel = self._compile(phrases_cfg.get("cancel", []), variants, self.name)
        self.wake = self._compile(phrases_cfg.get("wake", []), variants, self.name)
        self.switch = self._compile(phrases_cfg.get("switch", []), variants, self.name)
        self.reply = self._compile(phrases_cfg.get("reply", []), variants, self.name)
        self.listen = self._compile(phrases_cfg.get("listen", []), variants, self.name)
        self.sleep = self._compile(phrases_cfg.get("sleep", []), variants, self.name)
        self.cut = self._compile(phrases_cfg.get("cut", []), variants, self.name)
        self.list = self._compile(phrases_cfg.get("list", []), variants, self.name)
        self._list_loose_max = int(phrases_cfg.get("list_loose_max_tokens", 3) or 0)
        self._list_words = self._wordsets.get("liste", {"liste", "listeyi"})

    def _compile(self, items: list[str], variants: list[str] | None = None,
                 name: str | None = None) -> list[list[str]]:
        """Turns every pattern into a list of words.

        Each word that has a spelling set is expanded into all of its variants
        ("mahmut kes" -> mahmut/mamut/... x kes/ces/kec/...).
        """
        out: list[list[str]] = []
        seen: set[tuple[str, ...]] = set()
        for raw in items:
            words = [w for w, _, _ in tokenize(raw)]
            if not words:
                continue
            expansions: list[list[str]] = [[]]
            for w in words:
                alts = sorted(self._wordsets.get(w, {w}))
                expansions = [e + [a] for e in expansions for a in alts]
                if len(expansions) > 4000:      # keep the expansion from exploding
                    expansions = expansions[:4000]
            for e in expansions:
                key = tuple(e)
                if key not in seen:
                    seen.add(key)
                    out.append(e)
        out.sort(key=len, reverse=True)
        return out

    def _claude_like(self, word: str) -> bool:
        return any(word_eq(word, v) for v in self._variants)

    def _split_merged(self, toks: list[tuple[str, int, int]]
                      ) -> list[tuple[str, int, int]]:
        """Splits a wake name that got glued to the command.

        Transcription sometimes writes "Mahmutçes" as one word; matching
        expects two separate words, so the command used to slip through.
        """
        out: list[tuple[str, int, int]] = []
        for w, a, b in toks:
            split = None
            for v in self._variants:
                if len(w) > len(v) + 1 and w.startswith(v):
                    split = (v, w[len(v):])
                    break
            if split:
                cut = a + len(split[0])
                out.append((split[0], a, cut))
                out.append((split[1], cut, b))
            else:
                out.append((w, a, b))
        return out

    def _match_tail(self, toks: list[tuple[str, int, int]],
                    patterns: list[list[str]]) -> int | None:
        """If one of the patterns occurs at the END of the token sequence,
        returns where the match starts in the original text."""
        for pat in patterns:
            n = len(pat)
            if n > len(toks):
                continue
            tail = toks[-n:]
            ok = True
            # A one-word pattern carries no context, so it must match exactly.
            eq = word_eq_strict if n == 1 else word_eq
            for (spoken, _, _), target in zip(tail, pat):
                hit = (self._claude_like(spoken) if target in self._variants
                       else eq(spoken, target))
                if not hit:
                    ok = False
                    break
            if ok:
                return tail[0][1]
        return None

    def find_send(self, text: str) -> tuple[bool, str]:
        """Does the text end with a send phrase?
        (If so: True plus the text with the command words removed.)"""
        toks = self._split_merged(tokenize(text))
        idx = self._match_tail(toks, self.send)
        if idx is None:
            return False, text
        return True, text[:idx].strip(" \t\n,.;:-—–")

    def compile_extra(self, items: list[str]) -> list[list[str]]:
        """Compiles an extra pattern list from the config (shortcut commands)."""
        return self._compile(items, sorted(self._variants), self.name)

    def find_tail(self, text: str,
                  patterns: list[list[str]]) -> tuple[bool, str]:
        """Is a pattern at the end of the text? (If so: the text before it.)"""
        idx = self._match_tail(self._split_merged(tokenize(text)), patterns)
        if idx is None:
            return False, text
        return True, text[:idx].strip(" \t\n,.;:-—–")

    def is_list(self, text: str) -> bool:
        """"listeyi getir mahmut" - reads the numbered list aloud.

        Extra rule: a short sentence that STARTS with "liste" is accepted even
        when the wake name was not recognised. Transcription mangles this
        command often ("listeyi getir mahmut" -> "Listeyi yatırmamışım.") and
        reading a list is harmless, so being lenient here is safe.
        """
        toks = self._split_merged(tokenize(text))
        if self._match_tail(toks, self.list) is not None:
            return True
        if not toks or len(toks) > self._list_loose_max:
            return False
        words = [w for w, _, _ in toks]
        # (a) when it STARTS with "liste"
        if any(word_eq(words[0], v) for v in self._list_words):
            return True
        # (b) a short sentence containing both the WAKE NAME and a verb like
        #     "getir/oku/say". Why: "listeyi getir mahmut" comes out as
        #     "Mahmut'u getirdim." Word order and suffixes break, so the mere
        #     PRESENCE of both is enough.
        has_name = any(self._claude_like(w) for w in words)
        verbs = (self._wordsets.get("getir", {"getir"})
                 | {"oku", "okur", "say", "sayar", "soyle"})
        has_verb = any(any(word_eq(w, v) for v in verbs) for w in words)
        return has_name and has_verb

    def is_cut(self, text: str) -> bool:
        """"mahmut kes" - stops the current reading only; listening goes on."""
        return self._match_tail(self._split_merged(tokenize(text)), self.cut) is not None

    def is_listen(self, text: str) -> bool:
        """"mahmut start" - wakes up even from a paused state."""
        return self._match_tail(self._split_merged(tokenize(text)), self.listen) is not None

    def is_sleep(self, text: str) -> bool:
        """"mahmut stop" - puts it into deep sleep."""
        return self._match_tail(self._split_merged(tokenize(text)), self.sleep) is not None

    def find_reply(self, text: str) -> tuple[bool, str]:
        """Does the text end with "cevap mahmut"?
        (If so: True plus the text before it, so dictation continues.)"""
        toks = self._split_merged(tokenize(text))
        idx = self._match_tail(toks, self.reply)
        if idx is None:
            return False, text
        return True, text[:idx].strip(" \t\n,.;:-—–")

    def find_switch(self, text: str) -> tuple[bool, str]:
        """Does the text end with a session-select phrase?
        (If so: True plus the session name in front of it.)"""
        toks = self._split_merged(tokenize(text))
        idx = self._match_tail(toks, self.switch)
        if idx is None:
            return False, ""
        return True, text[:idx].strip(" \t\n,.;:-—–'\u2019")

    def is_cancel(self, text: str) -> bool:
        return self._match_tail(self._split_merged(tokenize(text)), self.cancel) is not None

    def find_wake(self, text: str) -> str | None:
        """Returns the text AFTER the wake phrase when it occurs
        (None otherwise). 'hey mahmut sunu yap' -> 'sunu yap'."""
        toks = self._split_merged(tokenize(text))
        for pat in self.wake:
            n = len(pat)
            for start in range(0, len(toks) - n + 1):
                window = toks[start:start + n]
                ok = True
                for (spoken, _, _), target in zip(window, pat):
                    hit = (self._claude_like(spoken) if target in self._variants
                           else word_eq(spoken, target))
                    if not hit:
                        ok = False
                        break
                if ok:
                    return text[window[-1][2]:].strip(" \t\n,.;:-—–")
        return None
