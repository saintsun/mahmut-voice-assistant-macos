"""Finds GPT Codex conversations, matches them by name and switches between them.

The Codex desktop app keeps its state locally, in two places:

  ~/.codex/state_5.sqlite            -> threads: id, name/title, cwd, rollout_path
  ~/.codex/.codex-global-state.json  -> local-projects: id, name, rootPaths[]

A thread belongs to a project when its `cwd` sits under one of that project's
rootPaths; the database's own project_id column is always empty. Threads listed
in projectless-thread-ids are the loose ones shown under "Recents".

Switching uses the app's own deep link:
  codex://threads/<thread-id>

Replies are read from the thread's rollout file (the same JSONL tailing used
for Claude Code), so nothing here needs the Accessibility permission.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import time
from dataclasses import dataclass, field

HOME = os.path.expanduser("~")
CODEX_DIR = os.path.join(HOME, ".codex")
STATE_DB = os.path.join(CODEX_DIR, "state_5.sqlite")
GLOBAL_STATE = os.path.join(CODEX_DIR, ".codex-global-state.json")

_ID_OK = 36          # uuid length; deep links take nothing else


@dataclass
class Thread:
    """One Codex conversation, in the same shape the app uses for Claude."""

    id: str
    name: str                      # "Kunaz Reklam" - project + thread
    thread_name: str = ""          # "Reklam"
    project: str = ""              # "Kunaz"
    cwd: str = ""
    jsonl: str | None = None       # rollout file, for reading replies
    updated: float = 0.0
    archived: bool = False
    routine: bool = field(default=False)   # kept for API symmetry

    @property
    def switchable(self) -> bool:
        return len(self.id) == _ID_OK

    @property
    def session_id(self) -> str:   # symmetry with sessions.Session
        return self.id

    @property
    def host_id(self) -> str:
        return self.id

    @property
    def status(self) -> str:
        return "archived" if self.archived else "open"


def available() -> bool:
    """Is a local Codex installation present?"""
    return os.path.exists(STATE_DB)


def projectless_ids() -> set[str]:
    """Threads the user keeps out of any project (the "Recents" list).

    Such a thread can still sit inside a project's rootPath, so the path match
    alone would wrongly file it under that project.
    """
    try:
        with open(GLOBAL_STATE, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return set()
    return {str(x) for x in (data.get("projectless-thread-ids") or [])}


def projects() -> dict[str, dict]:
    """{project_id: {"name": ..., "roots": [...]}} from the global state."""
    try:
        with open(GLOBAL_STATE, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return {}
    out = {}
    for pid, p in (data.get("local-projects") or {}).items():
        name = str(p.get("name") or "").strip()
        roots = [str(r) for r in (p.get("rootPaths") or []) if r]
        if name:
            out[pid] = {"name": name, "roots": roots}
    return out


def _project_of(cwd: str, projs: dict[str, dict]) -> str:
    """Which project owns this working directory?

    The database does not record it, so the path is matched against each
    project's rootPaths. The longest matching root wins, so nested roots do
    not steal a thread from the more specific project.
    """
    path = (cwd or "").rstrip("/")
    best, best_len = "", -1
    for p in projs.values():
        for root in p["roots"]:
            r = root.rstrip("/")
            if (path == r or path.startswith(r + "/")) and len(r) > best_len:
                best, best_len = p["name"], len(r)
    return best


def threads(include_projectless: bool = True) -> list[Thread]:
    """All local Codex conversations, most recently updated first."""
    if not available():
        return []
    projs = projects()
    loose = projectless_ids()
    rows: list[Thread] = []
    try:
        con = sqlite3.connect(f"file:{STATE_DB}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        q = ("select id, name, title, cwd, rollout_path, updated_at_ms, archived "
             "from threads order by coalesce(updated_at_ms, 0) desc")
        for r in con.execute(q):
            name = (r["name"] or "").strip() or (r["title"] or "").strip()
            if not name:
                continue
            name = name.splitlines()[0][:60]
            project = "" if str(r["id"]) in loose else _project_of(r["cwd"] or "", projs)
            if not project and not include_projectless:
                continue
            rows.append(Thread(
                id=str(r["id"]),
                name=f"{project} {name}".strip() if project else name,
                thread_name=name,
                project=project,
                cwd=r["cwd"] or "",
                jsonl=r["rollout_path"] or None,
                updated=(r["updated_at_ms"] or 0) / 1000.0,
                archived=bool(r["archived"]),
            ))
        con.close()
    except Exception as exc:
        print(f"[codex] oturumlar okunamadi: {exc}")
    return rows


def live_threads() -> list[Thread]:
    """Conversations that are not archived - the sidebar list."""
    return [t for t in threads() if not t.archived]


def project_threads() -> list[Thread]:
    """Only the conversations that belong to a project.

    These are the default favourites: the panel starts with the project tree
    the user already organised, and loose "Recents" can be added by hand.
    """
    return [t for t in threads(include_projectless=False) if not t.archived]


class Registry:
    """Same shape as sessions.Registry, so the watcher can take either one."""

    def __init__(self, ttl: float = 2.0):
        self.ttl = ttl
        self._rows: list[Thread] = []
        self._at = 0.0

    def all(self, force: bool = False) -> list[Thread]:
        now = time.monotonic()
        if force or now - self._at > self.ttl:
            self._rows = live_threads()
            self._at = now
        return self._rows


def switch_to(thread: Thread) -> tuple[bool, str]:
    """Brings the Codex app to that conversation (deep link, no AX needed)."""
    if not thread.switchable:
        return False, f"{thread.name}: geçersiz oturum kimliği"
    url = f"codex://threads/{thread.id}"
    try:
        r = subprocess.run(["open", url], capture_output=True, text=True,
                           timeout=10)
    except Exception as exc:
        return False, f"açılamadı: {exc}"
    if r.returncode != 0:
        return False, (r.stderr or "").strip() or "açılamadı"
    return True, thread.name


def find_exact(spoken: str, items: list[Thread] | None = None) -> Thread | None:
    """Returns the thread whose name matches exactly (case and accents aside)."""
    from .phrases import fold
    want = fold(spoken).strip()
    if not want:
        return None
    for t in (items if items is not None else live_threads()):
        if fold(t.name).strip() == want:
            return t
    return None


def match(spoken: str, items: list[Thread] | None = None,
          threshold: float = 0.62):
    """Best fuzzy match: (thread, score, all_scores) - mirrors sessions.match.

    The threshold is the same as the one for Claude sessions: without it the
    best row always won, so a name that matches nothing switched to whatever
    happened to rank first.
    """
    from .sessions import score as _score
    rows = items if items is not None else live_threads()
    scored = [(t, _score(spoken, t.name)) for t in rows]
    scored.sort(key=lambda x: x[1], reverse=True)
    if not scored or scored[0][1] < threshold:
        return None, (scored[0][1] if scored else 0.0), scored
    return scored[0][0], scored[0][1], scored


def wait_for_thread(thread_id: str, timeout: float = 10.0) -> Thread | None:
    """Waits until a thread id shows up in the local database."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for t in threads():
            if t.id == thread_id:
                return t
        time.sleep(0.5)
    return None
