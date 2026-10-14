"""Plays multi-segment speech as one continuous utterance.

The problem: every `say` call costs about a second of dead time. A bilingual
sentence split into 7 segments wastes 7 seconds and sounds chopped up.

The fix: segments are rendered to files in PARALLEL (`say -o`, far faster than
real time), concatenated into one file with ffmpeg and played once with
`afplay`. Dead time is paid once instead of 7 times and no gap is left between
segments. A silence of any length can be inserted between them.

Without ffmpeg the caller falls back to sequential `say` calls.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor

SAMPLE_RATE = 24000


def have_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("afplay") is not None


def _render_one(args) -> str | None:
    idx, voice, rate, text, workdir = args
    out = os.path.join(workdir, f"seg{idx:03d}.aiff")
    try:
        p = subprocess.run(
            ["say", "-v", voice, "-r", str(rate), "-o", out, "-f", "-"],
            input=text.encode("utf-8"),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60,
        )
        return out if p.returncode == 0 and os.path.exists(out) else None
    except Exception:
        return None


def render_all(segments: list[tuple[str, int, str]], workdir: str) -> list[str]:
    """Renders segments to audio in parallel, preserving their order."""
    jobs = [(i, v, r, t, workdir) for i, (v, r, t) in enumerate(segments)]
    with ThreadPoolExecutor(max_workers=min(8, len(jobs) or 1)) as pool:
        return [p for p in pool.map(_render_one, jobs) if p]


def concat(paths: list[str], out: str, pause_after: int = -1,
           pause_sec: float = 0.0, pause_between: float = 0.0) -> bool:
    """Concatenates audio files into one.

    pause_after: insert silence AFTER the segment at this index (-1 = none).
    Segments may have different sample rates, so everything is resampled to a
    single rate (Turkish and English voices do not render at the same rate).
    """
    if not paths:
        return False
    inputs: list[str] = []
    filters: list[str] = []
    labels: list[str] = []
    n = 0
    for i, p in enumerate(paths):
        inputs += ["-i", p]
        filters.append(f"[{n}:a]aresample={SAMPLE_RATE},"
                       f"aformat=channel_layouts=mono[a{n}]")
        labels.append(f"[a{n}]")
        n += 1
        gap = pause_sec if i == pause_after and pause_sec > 0 else (
            pause_between if (pause_between > 0 and i < len(paths) - 1) else 0.0)
        if gap > 0:
            inputs += ["-f", "lavfi", "-t", f"{gap:.3f}",
                       "-i", f"anullsrc=r={SAMPLE_RATE}:cl=mono"]
            filters.append(f"[{n}:a]aformat=channel_layouts=mono[a{n}]")
            labels.append(f"[a{n}]")
            n += 1
    graph = ";".join(filters) + ";" + "".join(labels) + f"concat=n={n}:v=0:a=1[out]"
    cmd = (["ffmpeg", "-nostdin", "-loglevel", "error", "-y"] + inputs +
           ["-filter_complex", graph, "-map", "[out]", out])
    try:
        return subprocess.run(cmd, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=60).returncode == 0
    except Exception:
        return False


def build(segments: list[tuple[str, int, str]], pause_after: int = -1,
          pause_sec: float = 0.0,
          pause_between: float = 0.0) -> tuple[str | None, str | None]:
    """Returns (file_to_play, temp_dir); delete the directory when done."""
    workdir = tempfile.mkdtemp(prefix="claudevoice-tts-")
    paths = render_all(segments, workdir)
    if not paths:
        shutil.rmtree(workdir, ignore_errors=True)
        return None, None
    out = os.path.join(workdir, "out.wav")
    if not concat(paths, out, pause_after, pause_sec, pause_between):
        shutil.rmtree(workdir, ignore_errors=True)
        return None, None
    return out, workdir
