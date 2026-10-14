"""Telsiz usulu komut kelimelerini yakalar.

Cagri adi Whisper tarafindan farkli yazilabilir (Mahmud, Mamut, Marmut),
Turkce karakterleri de degisebilir. Bu yuzden eslesme:
  1) ASCII'ye katlanmis normalize metin uzerinde,
  2) kelime bazinda, 1 harf hataya toleransli (edit distance <= 1)
yapilir.
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

# Kelime ICINDEKI nokta/kesme isareti kelimeyi BOLMEZ: "6.yi" -> "6yi",
# "Mahmut'un" -> "mahmutun". Whisper sira sayilarini boyle yaziyor ve
# "6.yi sec mahmut" 4 parcaya bolununce 3 kelimelik kalip hic tutmuyordu.
_W = r"[0-9A-Za-zÇĞİIÖŞÜçğıiöşü]"
_WORD_RE = re.compile(rf"{_W}+(?:['’.]{_W}+)*")


def fold(text: str) -> str:
    """Turkce metni eslesme icin sade ASCII kucuk harfe indirger."""
    text = text.replace("'", "").replace("’", "").replace(".", "")
    text = text.translate(_TR_MAP)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower()


def tokenize(text: str) -> list[tuple[str, int, int]]:
    """(normalize_kelime, baslangic_index, bitis_index) listesi dondurur.

    Index'ler ORIJINAL metne aittir; boylece terminator yakalandiginda
    ham metni dogru yerden kesebiliriz.
    """
    out = []
    for m in _WORD_RE.finditer(text):
        w = fold(m.group(0))
        if w:
            out.append((w, m.start(), m.end()))
    return out


def _edit_distance_le1(a: str, b: str) -> bool:
    """a ile b arasindaki edit distance 1 veya daha az mi?"""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:                              # tek harf degisimi
        diff = sum(1 for x, y in zip(a, b) if x != y)
        return diff <= 1
    if la > lb:                               # a'dan bir harf silinmis
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
    """Ard arda tekrar eden harfleri teke indirir: 'kess' -> 'kes'."""
    out = []
    for ch in word:
        if not out or out[-1] != ch:
            out.append(ch)
    return "".join(out)


def word_eq(spoken: str, target: str) -> bool:
    """Kisa kelimelerde tam, 4+ harfli kelimelerde 1 hata toleransli esitlik.

    Her iki durumda da cift harf farki yok sayilir: Whisper "kes"i cogu zaman
    "kess" diye yaziyor ve 3 harfli komutlar bulanik toleransa girmiyor.
    """
    if spoken == target:
        return True
    if _dedup(spoken) == _dedup(target):
        return True
    # RAKAM iceren yazimlarda tolerans YOK: "1inci" ile "5inci" arasinda tek
    # harf fark var, bulanik esitlik 5. sirayi 1. sira sanıyordu.
    if any(ch.isdigit() for ch in spoken) or any(ch.isdigit() for ch in target):
        return False
    if len(target) >= 4:
        return _edit_distance_le1(spoken, target)
    return False


class Matcher:
    """Konfigurasyondaki komut kaliplarini derleyip metinde arar."""

    def __init__(self, phrases_cfg: dict):
        self.name = fold(phrases_cfg.get("name", "mahmut"))
        variants = [fold(v) for v in (phrases_cfg.get("name_variants")
                                      or phrases_cfg.get("claude_variants")
                                      or [self.name])]
        if self.name not in variants:
            variants.insert(0, self.name)
        self._variants = set(variants)
        # Kelime setleri: Whisper ayni komutu cok farkli yazabiliyor
        # ("kes" -> ces / kec / kiss / chris). Her kanonik kelime icin
        # kabul edilen yazimlar burada toplanir.
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
        """Her kalibi kelime listesine cevirir.

        Kelime setlerinde karsiligi olan her kelime tum yazim varyantlari
        icin cogaltilir ("mahmut kes" -> mahmut/mamut/... x kes/ces/kec/...).
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
                if len(expansions) > 4000:      # patlamayi onle
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
        """Cagri adiyla komutun birlesik yazildigi durumu ayirir.

        Whisper bazen "Mahmutçes" diye tek kelime yaziyor; eslestirme iki
        ayri kelime bekledigi icin komut kaciyordu.
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
        """Kaliplardan biri token dizisinin SONUNDA geciyorsa, eslesmenin
        orijinal metindeki baslangic index'ini dondurur."""
        for pat in patterns:
            n = len(pat)
            if n > len(toks):
                continue
            tail = toks[-n:]
            ok = True
            for (spoken, _, _), target in zip(tail, pat):
                hit = (self._claude_like(spoken) if target in self._variants
                       else word_eq(spoken, target))
                if not hit:
                    ok = False
                    break
            if ok:
                return tail[0][1]
        return None

    def find_send(self, text: str) -> tuple[bool, str]:
        """Metin bir gonderme kelimesiyle bitiyor mu?
        (bitiyorsa True + komut kelimesi atilmis hali)."""
        toks = self._split_merged(tokenize(text))
        idx = self._match_tail(toks, self.send)
        if idx is None:
            return False, text
        return True, text[:idx].strip(" \t\n,.;:-—–")

    def compile_extra(self, items: list[str]) -> list[list[str]]:
        """Config'den gelen ozel kalip listesini derler (kisayol komutlari)."""
        return self._compile(items, sorted(self._variants), self.name)

    def find_tail(self, text: str,
                  patterns: list[list[str]]) -> tuple[bool, str]:
        """Kaliplardan biri metnin sonunda mi? (evetse komuttan onceki metin)."""
        idx = self._match_tail(self._split_merged(tokenize(text)), patterns)
        if idx is None:
            return False, text
        return True, text[:idx].strip(" \t\n,.;:-—–")

    def is_list(self, text: str) -> bool:
        """"listeyi getir mahmut" — numarali listeyi sesli okur.

        Ek olarak: kisa bir cumle "liste" ile BASLIYORSA cagri adi
        taninmasa da kabul edilir. Whisper bu komutu sikca bozuyor
        ("listeyi getir mahmut" -> "Listeyi yatırmamışım.") ve liste
        okumak zararsiz oldugu icin gevsek davranmak guvenli.
        """
        toks = self._split_merged(tokenize(text))
        if self._match_tail(toks, self.list) is not None:
            return True
        if not toks or len(toks) > self._list_loose_max:
            return False
        words = [w for w, _, _ in toks]
        # (a) "liste" ile BASLIYORSA
        if any(word_eq(words[0], v) for v in self._list_words):
            return True
        # (b) kisa cumlede hem CAGRI ADI hem "getir/oku/say" varsa.
        #     Gerekcesi: "listeyi getir mahmut" -> "Mahmut'u getirdim."
        #     Sira ve ekler bozulabiliyor, ikisinin VARLIGI yeterli.
        has_name = any(self._claude_like(w) for w in words)
        verbs = (self._wordsets.get("getir", {"getir"})
                 | {"oku", "okur", "say", "sayar", "soyle"})
        has_verb = any(any(word_eq(w, v) for v in verbs) for w in words)
        return has_name and has_verb

    def is_cut(self, text: str) -> bool:
        """"mahmut kes" — sadece o anki okumayi keser, dinleme surer."""
        return self._match_tail(self._split_merged(tokenize(text)), self.cut) is not None

    def is_listen(self, text: str) -> bool:
        """"mahmut start" — duraklatilmissa bile uyandirir."""
        return self._match_tail(self._split_merged(tokenize(text)), self.listen) is not None

    def is_sleep(self, text: str) -> bool:
        """"mahmut stop" — derin uykuya alir."""
        return self._match_tail(self._split_merged(tokenize(text)), self.sleep) is not None

    def find_reply(self, text: str) -> tuple[bool, str]:
        """Metin "cevap mahmut" ile bitiyor mu?
        (bitiyorsa True + komuttan onceki metin — dikteye devam edilir)."""
        toks = self._split_merged(tokenize(text))
        idx = self._match_tail(toks, self.reply)
        if idx is None:
            return False, text
        return True, text[:idx].strip(" \t\n,.;:-—–")

    def find_switch(self, text: str) -> tuple[bool, str]:
        """Metin bir oturum-secme kelimesiyle bitiyor mu?
        (bitiyorsa True + onundeki oturum adi)."""
        toks = self._split_merged(tokenize(text))
        idx = self._match_tail(toks, self.switch)
        if idx is None:
            return False, ""
        return True, text[:idx].strip(" \t\n,.;:-—–'\u2019")

    def is_cancel(self, text: str) -> bool:
        return self._match_tail(self._split_merged(tokenize(text)), self.cancel) is not None

    def find_wake(self, text: str) -> str | None:
        """Uyandirma kelimesi gecerse SONRASINDAKI metni dondurur
        (gecmiyorsa None). 'hey mahmut sunu yap' -> 'sunu yap'."""
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
