"""Repairs technical terms that transcription mangles into local phonetics.

"bajkenddeki" -> "backend'deki", "dojker" -> "docker", "stagginge" -> "staging'e".

Deliberately conservative for safety: it only touches words of 5+ letters that
share the first two letters and sit within a small edit distance, so ordinary
words are never rewritten into technical terms by accident.
"""
from __future__ import annotations

import re

from .phrases import fold

TERMS = [
    # infrastructure / devops
    "docker", "kubernetes", "container", "image", "registry", "cluster",
    "deploy", "deployment", "staging", "production", "rollback", "pipeline",
    "build", "release", "runner", "nginx", "server", "proxy", "load balancer",
    "terraform", "ansible", "jenkins", "github", "gitlab", "webhook",
    # git
    "commit", "merge", "rebase", "branch", "checkout", "pull request",
    "repository", "repo", "conflict", "stash", "revert", "diff", "patch",
    # backend
    "backend", "frontend", "endpoint", "request", "response", "payload",
    "middleware", "controller", "service", "handler", "router", "session",
    "authentication", "authorization", "token", "refresh token", "cookie",
    "database", "query", "migration", "schema", "index", "transaction",
    "postgres", "mysql", "redis", "mongodb", "cache", "queue", "worker",
    "microservice", "monolith", "serverless", "lambda", "websocket",
    # languages / tools
    "python", "javascript", "typescript", "swift", "kotlin", "golang",
    "react", "angular", "django", "flask", "fastapi", "express", "spring",
    "component", "hook", "state", "props", "render", "bundle", "webpack",
    "package", "dependency", "library", "framework", "module", "import",
    # quality
    "refactor", "debug", "breakpoint", "exception", "stack trace", "log",
    "test", "unit test", "integration test", "coverage", "mock", "fixture",
    "lint", "format", "review", "benchmark", "profiling", "regression",
    # concepts
    "function", "variable", "array", "object", "string", "boolean", "integer",
    "interface", "class", "method", "property", "callback", "promise",
    "async", "await", "thread", "process", "memory leak", "race condition",
    "timeout", "retry", "latency", "throughput", "scalability", "config",
    "environment", "variable", "secret", "credential", "permission", "scope",
]

# Suffixes that follow a term: "backend'deki" -> stem "backend", suffix "deki"
_SUFFIXES = [
    "larindaki", "lerindeki", "larimizi", "lerimizi", "lariniz", "leriniz",
    "indeki", "indaki", "larini", "lerini", "larina", "lerine", "lardan",
    "lerden", "larda", "lerde", "lari", "leri", "lara", "lere", "lar", "ler",
    "ndeki", "ndaki", "deki", "daki", "nin", "nin", "nun", "nun", "ini",
    "ini", "unu", "unu", "ina", "ine", "una", "une", "den", "dan", "ten",
    "tan", "de", "da", "te", "ta", "in", "in", "un", "un", "ne", "na",
    "yi", "yi", "yu", "yu", "le", "la", "i", "i", "u", "u", "e", "a",
]

_WORD_RE = re.compile(r"[0-9A-Za-zÇĞİIÖŞÜçğıiöşü']+")


def _dist(a: str, b: str) -> int:
    """Levenshtein distance (fast enough for short words)."""
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


class Glossary:
    def __init__(self, extra_terms: list[str] | None = None, enabled: bool = True):
        self.enabled = enabled
        terms = list(TERMS) + list(extra_terms or [])
        # Only single-word terms can be corrected token by token.
        self._single = {}
        for t in terms:
            if " " in t:
                continue
            self._single.setdefault(fold(t), t)
        self._keys = list(self._single.keys())

    def _best(self, stem: str) -> str | None:
        """Returns the closest term to the stem, or None."""
        if len(stem) < 5:
            return None
        if stem in self._single:
            return None                       # already spelled correctly
        budget = max(1, len(stem) // 4)
        best, best_d = None, budget + 1
        for key in self._keys:
            if abs(len(key) - len(stem)) > budget:
                continue
            if key[:2] != stem[:2]:           # the first two letters must match
                continue
            d = _dist(stem, key)
            if d < best_d:
                best, best_d = key, d
        return self._single[best] if best else None

    def _fix_word(self, word: str) -> str:
        folded = fold(word).replace("'", "")
        if len(folded) < 5 or folded.isdigit():
            return word
        # 1) A term that is already correct: leave it alone.
        if folded in self._single:
            return word
        suffixes = sorted(_SUFFIXES, key=len, reverse=True)
        # 2) Stripping the suffix yields an exact term ("endpointini"): leave it.
        for suf in suffixes:
            if len(folded) - len(suf) < 5 or not folded.endswith(suf):
                continue
            if folded[: -len(suf)] in self._single:
                return word
        # 3) Suffix stripped and the stem is close to a term: correct it
        #    ("stagginge" -> "staging'e", "bajkenddeki" -> "backend'deki").
        for suf in suffixes:
            if len(folded) - len(suf) < 5 or not folded.endswith(suf):
                continue
            hit = self._best(folded[: -len(suf)])
            if hit:
                return f"{hit}'{suf}"
        # 4) Close as a whole word with no suffix ("kubernetis" -> "kubernetes").
        hit = self._best(folded)
        return hit if hit else word

    def correct(self, text: str) -> str:
        if not self.enabled or not text:
            return text
        out, last = [], 0
        for m in _WORD_RE.finditer(text):
            fixed = self._fix_word(m.group(0))
            if fixed != m.group(0):
                out.append(text[last:m.start()])
                out.append(fixed)
                last = m.end()
        out.append(text[last:])
        return "".join(out)
