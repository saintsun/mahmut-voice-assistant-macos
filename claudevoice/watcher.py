"""Follows every live Claude Code session at once.

Each session's transcript is written line by line to
~/.claude/projects/<project>/<session>.jsonl. All live sessions are watched in
parallel; new assistant TEXT blocks (thinking and tool calls excluded) are
handed out together with the session name.

Messages that arrive in parallel enter the speech queue in order; since the
queue speaks one item at a time they never overlap.
"""
from __future__ import annotations

import json
import os
import threading

from .sessions import Registry, Session


class _Tail:
    """Follows the unread tail of a single jsonl file."""

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
        if size < self.offset:          # the file was truncated
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
    """Reports new assistant texts through `callback(session_name, text)`."""

    def __init__(self, callback, registry: Registry | None = None,
                 poll_sec: float = 0.4, rescan_sec: float = 3.0):
        self.callback = callback
        self.registry = registry or Registry()
        self.poll_sec = poll_sec
        self.rescan_sec = rescan_sec
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._tails: dict[str, _Tail] = {}      # jsonl path -> tail
        self._names: dict[str, str] = {}        # jsonl path -> session name
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
        """Restarts the thread if it died. True means it was restarted."""
        if self._stop.is_set() or self.alive():
            return False
        print("[watch] takip durmus, yeniden baslatiliyor")
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="claudevoice-watch")
        self._thread.start()
        return True

    # --- keep the tails in sync with the session list ---
    def _sync(self) -> None:
        sessions: list[Session] = self.registry.all(force=True)
        alive_paths = set()
        for s in sessions:
            if not s.jsonl:
                continue
            alive_paths.add(s.jsonl)
            self._names[s.jsonl] = s.name
            if s.jsonl not in self._tails:
                # Attach to a newly seen file at its END so history is not
                # read out loud.
                self._tails[s.jsonl] = _Tail(s.jsonl, start_at_end=True)
        for gone in set(self._tails) - alive_paths:
            self._tails.pop(gone, None)
            self._names.pop(gone, None)
        self.watched = sorted(self._names.values())

    # --- line handling ---
    @staticmethod
    def _assistant_texts(row: dict) -> list[str]:
        """Assistant text blocks, in either transcript format.

        Claude Code:
          {"type": "assistant", "message": {"content": [{"type": "text", ...}]}}
        Codex:
          {"type": "response_item",
           "payload": {"type": "message", "role": "assistant",
                       "content": [{"type": "output_text", "text": ...}]}}
        """
        if row.get("type") == "assistant" and not row.get("isSidechain"):
            blocks = (row.get("message", {}) or {}).get("content", []) or []
            return [b.get("text", "") for b in blocks
                    if isinstance(b, dict) and b.get("type") == "text"]
        if row.get("type") == "response_item":
            p = row.get("payload") or {}
            if p.get("type") == "message" and p.get("role") == "assistant":
                return [b.get("text", "") for b in (p.get("content") or [])
                        if isinstance(b, dict)
                        and b.get("type") in ("output_text", "text")]
        return []

    def _handle(self, raw: bytes, session_name: str) -> None:
        try:
            row = json.loads(raw.decode("utf-8", "replace"))
        except Exception:
            return
        texts = self._assistant_texts(row)
        if not texts:
            return
        uid = row.get("uuid") or row.get("id") or (row.get("payload") or {}).get("id")
        if uid:
            if uid in self._seen:
                return
            self._seen.add(uid)
            if len(self._seen) > 6000:
                self._seen = set(list(self._seen)[-3000:])
        for block in texts:
            text = (block or "").strip()
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
            # A single exception here used to KILL the thread: watching
            # stopped silently, messages were never read and nothing was
            # logged anywhere. Now the error is logged and the loop goes on.
            try:
                for path, tail in list(self._tails.items()):
                    name = self._names.get(path, "Claude")
                    for raw in tail.read_new():
                        self._handle(raw, name)
            except Exception as exc:
                print(f"[watch] okuma hatasi: {exc!r}")
            self._stop.wait(self.poll_sec)
