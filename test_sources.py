#!/usr/bin/env python3
"""Target, mute and routine tests - no app window, no audio, no network.

What is covered, all of it caught in real use:

  * favourites are saved under the key of the SELECTED target (saving while
    Codex was selected used to overwrite the Claude list)
  * selecting a conversation by name searches the selected target's list
    (it always searched Claude's, so Codex threads were unreachable)
  * a muted conversation is not read out loud and does not become the reply
    target (the watcher follows every session, so nothing else filters)
  * a routine is recognised both when it starts its own session and when it
    runs inside an existing, long conversation (only the head used to be
    scanned, so a scheduled check-in in an old thread was read aloud)

The methods are called unbound on a stub object: that keeps the real logic
under test without building a menu bar app.
"""
from __future__ import annotations

import os
import sys
import tempfile

from claudevoice import app as app_mod
from claudevoice import codex as codex_src
from claudevoice import sessions as sessions_mod
from claudevoice.app import ClaudeVoice
from claudevoice.phrases import fold

CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


def eq(got, want, label):
    assert got == want, f"{label}: beklenen {want!r}, gelen {got!r}"


class FakeCfg:
    """config.json in memory, with the same get/set surface."""

    def __init__(self, data: dict):
        self.data = data

    def get(self, section, key, default=None):
        return self.data.get(section, {}).get(key, default)

    def set(self, section, key, value):
        self.data.setdefault(section, {})[key] = value

    def __getitem__(self, section):
        return self.data.get(section, {})


class FakeSpeaker:
    def __init__(self):
        self.spoken: list[str] = []
        self.enabled = True

    def say(self, text, meta=None, prefix=None):
        self.spoken.append(text)


class FakeRegistry:
    def __init__(self, rows):
        self.rows = rows

    def all(self, force=False):
        return self.rows


def session(name, routine=False, sid="s-1"):
    return sessions_mod.Session(
        name=name, session_id=sid, host_id=f"local_{sid}", cwd="/tmp",
        status="open", pid=1, updated=0.0, jsonl=None, routine=routine)


def thread(name, tid="11111111-2222-3333-4444-555555555555"):
    return codex_src.Thread(id=tid, name=name, thread_name=name,
                            project="", cwd="/tmp", jsonl=None, updated=0.0)


def stub(target="claude", claude_rows=(), codex_rows=(), cfg_extra=None,
         muted=(), patterns=()):
    """A ClaudeVoice stand-in carrying only what these methods touch."""
    data = {"inject": {"target": target},
            "ui": {"favorites": [], "favorites_codex": []},
            "tts": {}, "phrases": {"name": "mahmut"}}
    for sec, vals in (cfg_extra or {}).items():
        data.setdefault(sec, {}).update(vals)

    s = ClaudeVoice.__new__(ClaudeVoice)          # __init__ is not run
    s.cfg = FakeCfg(data)
    s.registry = FakeRegistry(list(claude_rows))
    s._codex_registry = FakeRegistry(list(codex_rows))
    s.favorites = []
    s.speaker = FakeSpeaker()
    s.muted = set(muted)
    s.mute_routines = True
    s.exclude_patterns = [fold(p) for p in patterns]
    s.status = ""
    s._last_received = None
    s._last_announced = None
    s._compile_favorites = lambda: None
    s._set_status = lambda text: setattr(s, "status", text)
    s._notify = lambda *a, **k: None
    s._say_tpl = lambda *a, **k: None
    s._announce_prefix = lambda name: ""
    return s


# --- favourites are stored per target -----------------------------------
@case("favori anahtari: claude seciliyken 'favorites'")
def _():
    s = stub("claude")
    eq(ClaudeVoice._fav_key(s), "favorites", "anahtar")


@case("favori anahtari: codex seciliyken 'favorites_codex'")
def _():
    s = stub("codex")
    eq(ClaudeVoice._fav_key(s), "favorites_codex", "anahtar")


@case("codex seciliyken kayit Claude listesini EZMEZ")
def _():
    s = stub("codex")
    s.cfg.set("ui", "favorites", [{"name": "Ana Panel", "id": "a"}])
    s.favorites = [{"name": "Kunaz Reklam", "id": "c1"}]
    ClaudeVoice._save_favorites(s)
    eq(s.cfg.get("ui", "favorites"), [{"name": "Ana Panel", "id": "a"}],
       "claude listesi")
    eq(s.cfg.get("ui", "favorites_codex"),
       [{"name": "Kunaz Reklam", "id": "c1"}], "codex listesi")


@case("claude seciliyken kayit kendi anahtarina gider")
def _():
    s = stub("claude")
    s.favorites = [{"name": "Ana Panel", "id": "a"}]
    ClaudeVoice._save_favorites(s)
    eq(s.cfg.get("ui", "favorites"), [{"name": "Ana Panel", "id": "a"}],
       "claude listesi")
    eq(s.cfg.get("ui", "favorites_codex"), [], "codex listesi bos kalir")


@case("codex seciliyken liste kendi anahtarindan okunur")
def _():
    s = stub("codex")
    s.cfg.set("ui", "favorites", [{"name": "Ana Panel", "id": "a"}])
    s.cfg.set("ui", "favorites_codex", [{"name": "Kunaz Reklam", "id": "c1"}])
    eq([f["name"] for f in ClaudeVoice._load_favorites(s)], ["Kunaz Reklam"],
       "okunan liste")


# --- selecting a conversation by name -----------------------------------
def _patched_switch():
    """Records which backend a switch went to, restores the originals."""
    calls = []
    orig_c, orig_x = app_mod.switch_to, codex_src.switch_to
    app_mod.switch_to = lambda s: (calls.append(("claude", s.name)) or (True, s.name))
    codex_src.switch_to = lambda t: (calls.append(("codex", t.name)) or (True, t.name))
    return calls, (orig_c, orig_x)


def _restore(orig):
    app_mod.switch_to, codex_src.switch_to = orig


@case("codex seciliyken isimle secim CODEX listesinde aranir")
def _():
    s = stub("codex", claude_rows=[session("Ana Panel")],
             codex_rows=[thread("Kunaz Reklam")])
    calls, orig = _patched_switch()
    try:
        ClaudeVoice._do_switch(s, "Kunaz Reklam")
    finally:
        _restore(orig)
    eq(calls, [("codex", "Kunaz Reklam")], "gecis")


@case("claude seciliyken isimle secim CLAUDE listesinde aranir")
def _():
    s = stub("claude", claude_rows=[session("Ana Panel")],
             codex_rows=[thread("Kunaz Reklam")])
    calls, orig = _patched_switch()
    try:
        ClaudeVoice._do_switch(s, "Ana Panel")
    finally:
        _restore(orig)
    eq(calls, [("claude", "Ana Panel")], "gecis")


@case("tutmayan ad hicbir konusmaya GECMEZ (esik 0.62)")
def _():
    s = stub("codex", claude_rows=[session("Ana Panel")],
             codex_rows=[thread("Kunaz Reklam")])
    s.titles = type("T", (), {"find": staticmethod(lambda n: None)})()
    calls, orig = _patched_switch()
    try:
        ClaudeVoice._do_switch(s, "Ana Panel")
    finally:
        _restore(orig)
    eq(calls, [], "hic gecis olmamali")
    assert "bulunamadı" in s.status, f"durum: {s.status!r}"


# --- muting -------------------------------------------------------------
@case("rutin oturum okunmaz")
def _():
    s = stub("claude", claude_rows=[session("Gunluk rapor", routine=True)])
    eq(ClaudeVoice.is_muted(s, "Gunluk rapor"), True, "rutin")


@case("kalibi tutan ad okunmaz")
def _():
    s = stub("claude", claude_rows=[session("Rapor (her sabah 09:10)")],
             patterns=["her sabah"])
    eq(ClaudeVoice.is_muted(s, "Rapor (her sabah 09:10)"), True, "kalip")


@case("elle susturulan okunmaz")
def _():
    s = stub("claude", claude_rows=[session("Ana Panel")], muted=["Ana Panel"])
    eq(ClaudeVoice.is_muted(s, "Ana Panel"), True, "elle")


@case("normal konusma okunur")
def _():
    s = stub("claude", claude_rows=[session("Ana Panel")],
             patterns=["her sabah"])
    eq(ClaudeVoice.is_muted(s, "Ana Panel"), False, "normal")


@case("susturulan konusmanin mesaji seslendirilmez")
def _():
    s = stub("claude", claude_rows=[session("Gunluk rapor", routine=True)])
    ClaudeVoice._on_assistant_text(s, "Gunluk rapor", "merhaba")
    eq(s.speaker.spoken, [], "okunanlar")
    eq(s._last_received, None, "cevap hedefi de degismemeli")


@case("normal konusmanin mesaji seslendirilir")
def _():
    s = stub("claude", claude_rows=[session("Ana Panel")])
    ClaudeVoice._on_assistant_text(s, "Ana Panel", "merhaba")
    eq(len(s.speaker.spoken), 1, "okunanlar")
    eq(s._last_received, "Ana Panel", "cevap hedefi")


# --- speaker echo -------------------------------------------------------
class FakeSpeakerEcho(FakeSpeaker):
    """A speaker that is reading a known text right now."""

    def __init__(self, reading=""):
        super().__init__()
        self.reading = reading

    def recent_text(self, grace=8.0):
        return self.reading


LIST_READ = ("Listeyi okuyorum. 1 kunaz reklam, 2 kunaz geliştirme, "
             "3 ana panel, 4 ses kontrolü, 5 pam geliştirme, kapalı, "
             "6 portal geliştirme.")


def echo_stub(reading):
    s = stub("claude")
    s.speaker = FakeSpeakerEcho(reading)
    return s


@case("hoparlor yankisi ayiklanir, kullanicinin cumlesi kalir")
def _():
    s = echo_stub(LIST_READ)
    heard = LIST_READ + " Test gönderimi"
    eq(ClaudeVoice._strip_own_voice(s, heard), "Test gönderimi", "kalan")


@case("yanki Whisper'da biraz farkli yazilsa da ayiklanir")
def _():
    s = echo_stub(LIST_READ)
    heard = ("Listeyi okuyorum. 1 kunaz reklam, 2 kunaz geliştirme, "
             "3 ana panel, 4 ses kontrolü, 5 pan geliştirme, kapalı, "
             "6 portal geliştirme. Test gönderimi")
    eq(ClaudeVoice._strip_own_voice(s, heard), "Test gönderimi", "kalan")


@case("sadece yanki duyulduysa geriye bir sey kalmaz")
def _():
    s = echo_stub(LIST_READ)
    eq(ClaudeVoice._strip_own_voice(s, LIST_READ), "", "kalan")


@case("okuma yokken metne dokunulmaz")
def _():
    s = echo_stub("")
    eq(ClaudeVoice._strip_own_voice(s, "tamam mahmut"), "tamam mahmut", "kalan")


@case("okuma sirasinda soylenen kisa komut korunur")
def _():
    s = echo_stub("Kunaz Reklam mesajını okuyorum. Migration dosyasını "
                  "güncelledim, testleri de ekledim.")
    eq(ClaudeVoice._strip_own_voice(s, "mahmut kes"), "mahmut kes", "komut")


@case("yankinin ortasindaki kullanici cumlesi de kurtarilir")
def _():
    s = echo_stub(LIST_READ)
    heard = ("Listeyi okuyorum. 1 kunaz reklam, 2 kunaz geliştirme, "
             "bunu gönder mahmut, 3 ana panel, 4 ses kontrolü, "
             "5 pam geliştirme, kapalı, 6 portal geliştirme.")
    eq(ClaudeVoice._strip_own_voice(s, heard), "bunu gönder mahmut", "kalan")


# --- recognising a routine transcript -----------------------------------
def _transcript(body: bytes) -> str:
    fh = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
    fh.write(body)
    fh.close()
    return fh.name


MARKER = b'{"origin":{"kind":"task-notification","subkind":"scheduled-trigger"}}\n'
FILLER = b'{"type":"assistant","message":{"content":[]}}\n'


@case("rutin isareti dosyanin basinda -> rutin")
def _():
    path = _transcript(MARKER + FILLER * 50)
    try:
        eq(sessions_mod.is_routine_transcript(path), True, "bas")
    finally:
        os.unlink(path)


@case("rutin isareti yalnizca SONDA -> yine rutin (uzun konusma)")
def _():
    path = _transcript(FILLER * 20000 + MARKER)
    try:
        assert os.path.getsize(path) > 262144, "dosya tarama penceresinden buyuk olmali"
        eq(sessions_mod.is_routine_transcript(path), True, "son")
    finally:
        os.unlink(path)


@case("isaret yok -> rutin degil")
def _():
    path = _transcript(FILLER * 20000)
    try:
        eq(sessions_mod.is_routine_transcript(path), False, "isaretsiz")
    finally:
        os.unlink(path)


@case("sonradan rutine baglanan konusma onbellekte takili kalmaz")
def _():
    path = _transcript(FILLER * 20000)
    try:
        eq(sessions_mod.is_routine_transcript(path), False, "once")
        with open(path, "ab") as fh:
            fh.write(MARKER)
        eq(sessions_mod.is_routine_transcript(path), True, "sonra")
    finally:
        os.unlink(path)


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
