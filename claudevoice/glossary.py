"""Yazilim terimlerini Whisper'in Turkce fonetige kacirdigi yerlerde toparlar.

"bajkenddeki" -> "backend'deki", "dojker" -> "docker", "stagginge" -> "staging'e".

Guvenlik icin kasitli olarak muhafazakar: sadece 5+ harfli, ilk iki harfi tutan
ve kucuk bir edit mesafesindeki kelimelere dokunur. Boylece normal Turkce
kelimeler yanlislikla terime cevrilmez.
"""
from __future__ import annotations

import re

from .phrases import fold

TERMS = [
    # altyapi / devops
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
    # diller / araclar
    "python", "javascript", "typescript", "swift", "kotlin", "golang",
    "react", "angular", "django", "flask", "fastapi", "express", "spring",
    "component", "hook", "state", "props", "render", "bundle", "webpack",
    "package", "dependency", "library", "framework", "module", "import",
    # kalite
    "refactor", "debug", "breakpoint", "exception", "stack trace", "log",
    "test", "unit test", "integration test", "coverage", "mock", "fixture",
    "lint", "format", "review", "benchmark", "profiling", "regression",
    # kavramlar
    "function", "variable", "array", "object", "string", "boolean", "integer",
    "interface", "class", "method", "property", "callback", "promise",
    "async", "await", "thread", "process", "memory leak", "race condition",
    "timeout", "retry", "latency", "throughput", "scalability", "config",
    "environment", "variable", "secret", "credential", "permission", "scope",
]

# Terimin ardina gelen Turkce ekler: "backend'deki" -> stem "backend", ek "deki"
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
    """Levenshtein mesafesi (kucuk kelimeler icin yeterince hizli)."""
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
        # Sadece tek kelimelik terimler token bazinda duzeltilebilir.
        self._single = {}
        for t in terms:
            if " " in t:
                continue
            self._single.setdefault(fold(t), t)
        self._keys = list(self._single.keys())

    def _best(self, stem: str) -> str | None:
        """Stem'e en yakin terimi bulur, yoksa None."""
        if len(stem) < 5:
            return None
        if stem in self._single:
            return None                       # zaten dogru yazilmis
        budget = max(1, len(stem) // 4)
        best, best_d = None, budget + 1
        for key in self._keys:
            if abs(len(key) - len(stem)) > budget:
                continue
            if key[:2] != stem[:2]:           # ilk iki harf tutmali
                continue
            d = _dist(stem, key)
            if d < best_d:
                best, best_d = key, d
        return self._single[best] if best else None

    def _fix_word(self, word: str) -> str:
        folded = fold(word).replace("'", "")
        if len(folded) < 5 or folded.isdigit():
            return word
        # 1) Zaten dogru yazilmis bir terim: dokunma.
        if folded in self._single:
            return word
        suffixes = sorted(_SUFFIXES, key=len, reverse=True)
        # 2) Ek soyuldugunda tam terim cikiyorsa ("endpointini"): dokunma.
        for suf in suffixes:
            if len(folded) - len(suf) < 5 or not folded.endswith(suf):
                continue
            if folded[: -len(suf)] in self._single:
                return word
        # 3) Ek soyulup govde yakin bir terime denk geliyorsa duzelt
        #    ("stagginge" -> "staging'e", "bajkenddeki" -> "backend'deki").
        for suf in suffixes:
            if len(folded) - len(suf) < 5 or not folded.endswith(suf):
                continue
            hit = self._best(folded[: -len(suf)])
            if hit:
                return f"{hit}'{suf}"
        # 4) Eksiz, komple kelime olarak yakin mi ("kubernetis" -> "kubernetes").
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
