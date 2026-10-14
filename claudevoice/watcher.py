"""Tum canli Claude Code oturumlarini ayni anda takip eder.

Her oturumun transcript'i ~/.claude/projects/<proje>/<oturum>.jsonl dosyasina
satir satir yaziliyor. Butun canli oturumlar paralel izlenir; yeni gelen
asistan METIN bloklari (dusunme ve arac cagrilari haric) oturum adiyla
birlikte disari verilir.

Paralel gelen mesajlar seslendirme kuyruguna sirayla girer; kuyruk zaten
tek tek okudugu icin ust uste binmez.
"""
from __future__ import annotations

import json
import os
import threading

from .sessions import Registry, Session


class _Tail:
    """Tek bir jsonl dosyasinin okunmamis kismini takip eder."""

    def __init__(self, path: str, start_at_end: bool = True):
        self.path = path
        self.partial = b""
        try:
            self.offset = os.path.getsize(path) if start_at_end else 0
        except OSError:
            self.offset = 0

    def read_new(self) -> list[bytes]:
        try:
            size = os.path.getsize(self.path)
        except OSError:
            return []
        if size < self.offset:          # dosya kirpilmis
            self.offset, self.partial = 0, b""
        if size == self.offset:
            return []
        try:
            with open(self.path, "rb") as fh:
                fh.seek(self.offset)
                chunk = fh.read(size - self.offset)
                self.offset = fh.tell()
        except OSError:
            return []
        data = self.partial + chunk
        lines = data.split(b"\n")
        self.partial = lines.pop()
        return [ln.strip() for ln in lines if ln.strip()]


class TranscriptWatcher:
    """Yeni asistan metinlerini `callback(oturum_adi, metin)` ile bildirir."""

    def __init__(self, callback, registry: Registry | None = None,
                 poll_sec: float = 0.4, rescan_sec: float = 3.0):
        self.callback = callback
        self.registry = registry or Registry()
        self.poll_sec = poll_sec
        self.rescan_sec = rescan_sec
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._tails: dict[str, _Tail] = {}      # jsonl yolu -> takipci
        self._names: dict[str, str] = {}        # jsonl yolu -> oturum adi
        self._seen: set[str] = set()
        self._since_rescan = 0.0
        self.watched: list[str] = []

    def start(self) -> None:
        self._sync()
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="claudevoice-watch")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def ensure_alive(self) -> bool:
        """Is parcacigi olmusse yeniden baslatir. True: yeniden baslatildi."""
        if self._stop.is_set() or self.alive():
            return False
        print("[watch] takip durmus, yeniden baslatiliyor")
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="claudevoice-watch")
        self._thread.start()
        return True

    # --- oturum listesini takiple esitle ---
    def _sync(self) -> None:
        sessions: list[Session] = self.registry.all(force=True)
        alive_paths = set()
        for s in sessions:
            if not s.jsonl:
                continue
            alive_paths.add(s.jsonl)
            self._names[s.jsonl] = s.name
            if s.jsonl not in self._tails:
                # Yeni gorulen dosyaya SONUNDAN baglan; gecmis okunmasin.
                self._tails[s.jsonl] = _Tail(s.jsonl, start_at_end=True)
        for gone in set(self._tails) - alive_paths:
            self._tails.pop(gone, None)
            self._names.pop(gone, None)
        self.watched = sorted(self._names.values())

    # --- satir isleme ---
    def _handle(self, raw: bytes, session_name: str) -> None:
        try:
            row = json.loads(raw.decode("utf-8", "replace"))
        except Exception:
            return
        if row.get("type") != "assistant" or row.get("isSidechain"):
            return
        uid = row.get("uuid")
        if uid:
            if uid in self._seen:
                return
            self._seen.add(uid)
            if len(self._seen) > 6000:
                self._seen = set(list(self._seen)[-3000:])
        for block in (row.get("message", {}) or {}).get("content", []) or []:
            if isinstance(block, dict) and block.get("type") == "text":
                text = (block.get("text") or "").strip()
                if text:
                    try:
                        self.callback(session_name, text)
                    except Exception as exc:
                        print(f"[watch] callback hatasi: {exc}")

    def _run(self) -> None:
        while not self._stop.is_set():
            self._since_rescan += self.poll_sec
            if self._since_rescan >= self.rescan_sec:
                self._since_rescan = 0.0
                try:
                    self._sync()
                except Exception as exc:
                    print(f"[watch] oturum taramasi: {exc}")
            # Buradaki tek bir istisna is parcacigini OLDURUYORDU: takip
            # sessizce duruyor, mesajlar hic okunmuyor ve hicbir yerde iz
            # kalmiyordu. Artik hata loglanip dongu devam ediyor.
            try:
                for path, tail in list(self._tails.items()):
                    name = self._names.get(path, "Claude")
                    for raw in tail.read_new():
                        self._handle(raw, name)
            except Exception as exc:
                print(f"[watch] okuma hatasi: {exc!r}")
            self._stop.wait(self.poll_sec)
