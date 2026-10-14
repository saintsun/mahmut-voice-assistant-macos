"""Finds Claude Code sessions, matches them by name and switches between them.

Two sources:
  ~/.claude/sessions/<pid>.json   -> live sessions: name, hostSessionId, cwd
  ~/.claude/projects/*/<id>.jsonl -> that session's transcript (for reading aloud)

Switching uses Claude.app's own deep link:
  claude://code/continue?session=local_xxxxxxxx
This is the same path the app's own menu uses and needs no Accessibility
permission.
"""
from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field

from .phrases import fold

SESSIONS_DIR = os.path.expanduser("~/.claude/sessions")
PROJECTS_DIR = os.path.expanduser("~/.claude/projects")
HOST_ID_RE = re.compile(r"^local_[A-Za-z0-9-]{1,64}$")


# Scheduled-task (routine) sessions carry this marker in their transcript:
#   "origin": {"kind":"task-notification","subkind":"scheduled-trigger", ...}
# and the triggering message starts with <scheduled-task name="...">.
# Session metadata (kind/nameSource/cwd) does NOT distinguish routines from
# normal conversations, so detection reads the transcript instead.
_ROUTINE_MARKERS = (b'"scheduled-trigger"', b"<scheduled-task ")
_routine_cache: dict[str, tuple[float, bool]] = {}


def is_routine_transcript(jsonl: str, probe_bytes: int = 262144) -> bool:
    """Was this transcript started by a scheduled task?

    The triggering message sits at the top of the file, so only the head is
    read; no JSON parsing, just a raw byte scan (fast).
    """
    try:
        mtime = os.path.getmtime(jsonl)
    except OSError:
        return False
    hit = _routine_cache.get(jsonl)
    if hit is not None and hit[0] == mtime:
        return hit[1]
    try:
        with open(jsonl, "rb") as fh:
            head = fh.read(probe_bytes)
        found = any(m in head for m in _ROUTINE_MARKERS)
    except OSError:
        found = False
    _routine_cache[jsonl] = (mtime, found)
    return found


@dataclass
class Session:
    name: str
    session_id: str
    host_id: str | None
    cwd: str
    status: str
    pid: int
    updated: float
    jsonl: str | None = field(default=None)
    routine: bool = field(default=False)   # is this a scheduled task

    @property
    def switchable(self) -> bool:
        return bool(self.host_id and HOST_ID_RE.match(self.host_id))


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, TypeError):
        return False


def _find_jsonl(session_id: str) -> str | None:
    hits = glob.glob(os.path.join(PROJECTS_DIR, "*", f"{session_id}.jsonl"))
    return hits[0] if hits else None


def live_sessions() -> list[Session]:
    """Sessions that are running right now (the ones in the sidebar)."""
    out: list[Session] = []
    for path in glob.glob(os.path.join(SESSIONS_DIR, "*.json")):
        try:
            with open(path, encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception:
            continue
        sid = d.get("sessionId")
        pid = d.get("pid")
        if not sid or not _alive(pid):
            continue
        jsonl = _find_jsonl(sid)
        name = (d.get("name") or "").strip()
        if not name:
            name = os.path.basename(d.get("cwd") or "") or sid[:8]
        out.append(Session(
            name=name,
            session_id=sid,
            host_id=d.get("hostSessionId"),
            cwd=d.get("cwd") or "",
            status=d.get("status") or "",
            pid=int(pid),
            updated=float(d.get("updatedAt") or 0) / 1000.0,
            jsonl=jsonl,
            routine=bool(jsonl and is_routine_transcript(jsonl)),
        ))
    out.sort(key=lambda s: -s.updated)
    return out


# ----------------------------------------------------------- name matching
def _dist(a: str, b: str) -> int:
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _token_sim(a: str, b: str) -> float:
    """Similarity between 0 and 1. 'kontrol' ~ 'control' -> 0.71"""
    if a == b:
        return 1.0
    m = max(len(a), len(b))
    return 0.0 if m == 0 else max(0.0, 1.0 - _dist(a, b) / m)


def score(spoken: str, name: str) -> float:
    """How well the spoken name fits a session name (0-1).

    For every spoken word the best counterpart in the session name is found and
    the score is their average, so "admin paneli" scores full against
    "Admin Panel" and only half against "Admin Rapor".
    """
    sp = [t for t in fold(spoken).split() if t]
    nm = [t for t in fold(name).split() if t]
    if not sp or not nm:
        return 0.0
    total = 0.0
    for s in sp:
        total += max(_token_sim(s, n) for n in nm)
    base = total / len(sp)
    # Small bonus when the spoken text covers the whole name (penalises
    # partial names)
    coverage = min(len(sp), len(nm)) / max(len(sp), len(nm))
    return base * (0.75 + 0.25 * coverage)


def find_exact(name: str, candidates: list[Session]) -> Session | None:
    """Returns the session whose name matches EXACTLY (case and accents are
    ignored).

    Names in the favourites list are written out in full, so this is tried
    first: fuzzy matching can confuse two names that share a word (a common
    second word alone pushes the score to 0.67).
    """
    f = " ".join(fold(name).split())
    for c in candidates:
        if " ".join(fold(c.name).split()) == f:
            return c
    return None


def match(spoken: str, candidates: list[Session],
          threshold: float = 0.62) -> tuple[Session | None, float, list[tuple[Session, float]]]:
    """Returns the best matching session: (session, score, all_scores)."""
    scored = sorted(((c, score(spoken, c.name)) for c in candidates),
                    key=lambda t: -t[1])
    if not scored or scored[0][1] < threshold:
        return None, (scored[0][1] if scored else 0.0), scored
    return scored[0][0], scored[0][1], scored


_ID_OK = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _safe_id(value: str) -> str:
    """Only let an id of the expected shape into a deep link.

    host_id / session_id come from Claude's own files under ~/.claude. A
    malformed value written there could make `open` launch an unexpected URL
    scheme, so the format is validated.
    """
    v = str(value or "").strip()
    return v if _ID_OK.match(v) else ""


# ---------------------------------------------------------------- switching
def switch_to(session: Session) -> tuple[bool, str]:
    """Switches Claude.app to that session (deep link, no AX permission)."""
    if not session.switchable:
        return False, f"{session.name}: geçiş kimliği yok"
    sid = _safe_id(session.host_id)
    if not sid:
        return False, f"{session.name}: geçersiz oturum kimliği"
    url = f"claude://code/continue?session={sid}"
    try:
        r = subprocess.run(["open", url], capture_output=True, text=True, timeout=10)
    except Exception as exc:
        return False, f"açılamadı: {exc}"
    if r.returncode != 0:
        return False, (r.stderr or "open başarısız").strip()
    return True, session.name


class Registry:
    """Refreshes the session list at short intervals so every call does not
    hit the disk."""

    def __init__(self, ttl: float = 3.0):
        self.ttl = ttl
        self._cache: list[Session] = []
        self._at = 0.0

    def all(self, force: bool = False) -> list[Session]:
        now = time.monotonic()
        if force or now - self._at > self.ttl:
            self._cache = live_sessions()
            self._at = now
        return self._cache

    def find(self, spoken: str):
        return match(spoken, self.all(force=True))


# ------------------------------------------------------------ closed sessions
def _title_of(path: str) -> str | None:
    """Returns the LAST custom-title value in a transcript file.

    To avoid reading the whole file only the final 1 MB is scanned; title lines
    repeat throughout a session, so that is usually enough.
    """
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            if size > 1_048_576:
                fh.seek(size - 1_048_576)
            data = fh.read()
    except OSError:
        return None
    i = data.rfind(b'"custom-title"')
    if i < 0:
        return None
    start = data.rfind(b"\n", 0, i) + 1
    end = data.find(b"\n", i)
    line = data[start:end if end > 0 else len(data)]
    try:
        return json.loads(line.decode("utf-8", "replace")).get("customTitle")
    except Exception:
        return None


class TitleIndex:
    """Maps a conversation TITLE to a session id, closed sessions included.

    Running sessions live under ~/.claude/sessions, but CLOSED ones exist only
    as transcript files. Reopening a closed conversation needs its session id,
    which this index provides.

    Scanning is expensive, so it runs in the background and only over files
    that CHANGED.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._mtimes: dict[str, float] = {}
        self._titles: dict[str, tuple[str, float]] = {}   # title -> (sid, mtime)
        self.ready = False

    def refresh(self) -> int:
        changed = 0
        for path in glob.glob(os.path.join(PROJECTS_DIR, "*", "*.jsonl")):
            try:
                m = os.path.getmtime(path)
            except OSError:
                continue
            if self._mtimes.get(path) == m:
                continue
            self._mtimes[path] = m
            title = _title_of(path)
            if not title:
                continue
            sid = os.path.basename(path)[:-6]
            with self._lock:
                cur = self._titles.get(title)
                if cur is None or m > cur[1]:
                    self._titles[title] = (sid, m)
            changed += 1
        self.ready = True
        return changed

    def start(self, interval: float = 300.0) -> None:
        def loop():
            while True:
                try:
                    self.refresh()
                except Exception as exc:
                    print(f"[index] tarama hatası: {exc!r}")
                time.sleep(interval)
        threading.Thread(target=loop, daemon=True,
                         name="claudevoice-index").start()

    def find(self, spoken: str, threshold: float = 0.72) -> str | None:
        """Returns the id of the CLOSED session that best fits the name."""
        with self._lock:
            items = list(self._titles.items())
        best, best_s = None, 0.0
        for title, (sid, _) in items:
            sc = score(spoken, title)
            if sc > best_s:
                best, best_s = sid, sc
        return best if best_s >= threshold else None


def resume_session(session_id: str) -> tuple[bool, str]:
    """Opens a closed session through Claude's resume deep link."""
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", session_id or ""):
        return False, "geçersiz oturum kimliği"
    try:
        r = subprocess.run(["open", f"claude://code/resume?session={session_id}"],
                           capture_output=True, text=True, timeout=10)
    except Exception as exc:
        return False, f"açılamadı: {exc}"
    if r.returncode != 0:
        return False, (r.stderr or "open başarısız").strip()
    return True, ""


def wait_for_session_id(session_id: str, timeout: float = 45.0):
    """Waits until the session with this ID appears in the list.

    Waiting by name is unreliable: a freshly opened session does not get its
    name immediately and shows up under the folder name for a while. The id is
    correct from the start.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        for s in live_sessions():
            if s.session_id == session_id:
                return s
        time.sleep(0.6)
    return None


def wait_for_session(name: str, timeout: float = 30.0,
                     threshold: float = 0.85):
    """Waits until the session appears (opening takes a few seconds).

    An EXACT name is tried first, and the fuzzy threshold is kept high so it
    never jumps to a different session with a similar name.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        sessions = live_sessions()
        exact = find_exact(name, sessions)
        if exact is not None:
            return exact
        sess, _, _ = match(name, sessions, threshold)
        if sess is not None:
            return sess
        time.sleep(0.8)
    return None
