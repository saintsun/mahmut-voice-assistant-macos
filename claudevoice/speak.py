"""Sequential speech output (macOS `say`).

Bilingual reading splits the text into many segments and every `say` call
costs about a second of dead time, so:

  * segments are rendered to files in PARALLEL in the background, joined into
    one file with ffmpeg and played once with `afplay` -> the gaps disappear
    and the dead time is paid once instead of per segment.

Preparation happens while the previous utterance is still playing, so the user
never waits for it. Without ffmpeg/afplay it falls back to sequential `say`.

The microphone can be muted while speaking so the app does not listen to its
own voice.
"""
from __future__ import annotations

import os
import queue
import shutil
import signal
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from . import render
from .bilingual import split_runs
from .config import TTS_PIDS_PATH


def _kill_group(proc, sig: int = signal.SIGTERM) -> None:
    """Kills the process AND the children it spawned.

    `say` hands playback to a child process, so killing only the parent does
    not stop the sound. The parent leads its own process group, so killpg
    catches all of them.
    """
    if proc is None or proc.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), sig)
        return
    except Exception:
        pass
    try:
        proc.terminate() if sig == signal.SIGTERM else proc.kill()
    except Exception:
        pass


def _note_pid(pid: int) -> None:
    try:
        with open(TTS_PIDS_PATH, "a", encoding="utf-8") as fh:
            fh.write(f"{pid}\n")
    except Exception:
        pass


def _forget_pid(pid: int) -> None:
    try:
        with open(TTS_PIDS_PATH, encoding="utf-8") as fh:
            keep = [ln for ln in fh.read().split() if ln.strip() and ln.strip() != str(pid)]
        with open(TTS_PIDS_PATH, "w", encoding="utf-8") as fh:
            fh.write("\n".join(keep) + ("\n" if keep else ""))
    except Exception:
        pass


def kill_orphans() -> int:
    """Kills `say`/`afplay` processes left over from a previous run.

    If the app dies by SIGKILL its children survive and keep reading; the
    overlapping voices sound broken. They are cleaned up at start-up.
    """
    killed = 0
    try:
        with open(TTS_PIDS_PATH, encoding="utf-8") as fh:
            pids = [int(x) for x in fh.read().split() if x.strip().isdigit()]
    except Exception:
        return 0
    for pid in pids:
        try:
            name = subprocess.run(["ps", "-p", str(pid), "-o", "comm="],
                                  capture_output=True, text=True, timeout=5).stdout.strip()
            # The pid may have been recycled: only kill our playback processes
            if name.endswith("say") or name.endswith("afplay"):
                try:
                    os.killpg(os.getpgid(pid), signal.SIGTERM)
                except Exception:
                    os.kill(pid, signal.SIGTERM)
                killed += 1
        except Exception:
            pass
    try:
        os.remove(TTS_PIDS_PATH)
    except Exception:
        pass
    return killed


class Speaker:
    def __init__(self, cfg: dict, on_start=None, on_end=None):
        self.cfg = cfg
        self.voice = cfg.get("voice", "Yelda")
        self.rate = int(cfg.get("rate", 210))
        self.bilingual = bool(cfg.get("bilingual", True))
        self.voice_en = cfg.get("voice_en") or ""
        self.rate_en = int(cfg.get("rate_en", cfg.get("rate", 210)))
        self.volume = float(cfg.get("volume", 1.0))
        # `say` has NO volume option (the embedded [[volm]] command is
        # ignored too, measured). Volume can only be changed by rendering to a
        # file and playing it, so anything other than 1.0 forces the render
        # path.
        self.seamless = bool(cfg.get("seamless", True)) and render.have_ffmpeg()
        self.announce_pause = float(cfg.get("announce_pause_ms", 500)) / 1000.0
        self.enabled = bool(cfg.get("enabled", True))

        self.on_start = on_start
        self.on_end = on_end
        self._q: "queue.Queue[dict | None]" = queue.Queue()
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._abort = threading.Event()
        self._busy = threading.Event()
        # While capturing audio from the panel the queue waits: otherwise a
        # newly arrived message starts reading, ducks the microphone and the
        # user's speech is never heard.
        self._hold = threading.Event()
        # The text being read right now: compared against what we hear so an
        # open microphone does not turn our own voice into a command.
        self.current_text = ""
        # When the user picks an output device in the panel, playback goes
        # there. None means the system default. The plain `say` path cannot
        # honour a device (the process plays to the system output), so an
        # explicit device forces the render path.
        self.output_device = None
        self._play_broken = False     # our own playback path failed on this device
        self._last_text = ""
        self._last_end = 0.0
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="tts-render")
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------ state
    @property
    def busy(self) -> bool:
        return self._busy.is_set()

    def recent_text(self, grace: float = 8.0) -> str:
        """The text being read plus the text of a reading that just ended.

        Transcription arrives about a second late, so dropping the guard the
        moment playback ends lets the echo of the last sentence be processed
        as a command.
        """
        if self.current_text:
            return self.current_text
        if self._last_text and time.monotonic() - self._last_end < grace:
            return self._last_text
        return ""

    def set_hold(self, on: bool) -> None:
        """Holds or resumes reading; the queue is kept intact."""
        if on:
            self._hold.set()
        else:
            self._hold.clear()

    @property
    def pending(self) -> int:
        return self._q.qsize()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="claudevoice-tts")
        self._thread.start()

    def say(self, text: str, meta: object = None, prefix: str = "") -> None:
        """meta  : which session this text came from (reported while reading)
        prefix: spoken as a SEPARATE sentence before the content (the
                announcement).

        The prefix travels in the same queue item, so another session's
        message cannot slip in between.
        """
        if self.enabled and text.strip():
            self._q.put({"text": text, "meta": meta, "prefix": prefix})

    def say_parts(self, parts: list[str], meta: object = None,
                  pause: float = 0.35) -> None:
        """Reads each part with real silence BETWEEN them.

        For reading lists: punctuation does not produce reliable pauses
        (measured - a period often yields no pause at all, and a comma puts
        one in the wrong place). Real silence is the only way.
        """
        parts = [p for p in parts if p and p.strip()]
        if self.enabled and parts:
            self._q.put({"parts": parts, "meta": meta, "pause": pause})

    def set_enabled(self, on: bool) -> None:
        self.enabled = on
        if not on:
            self.stop_current(clear_queue=True)

    def stop_current(self, clear_queue: bool = False) -> None:
        if clear_queue:
            while True:
                try:
                    self._q.get_nowait()
                except queue.Empty:
                    break
        self._abort.set()
        with self._lock:
            proc = self._proc
        _kill_group(proc)

    def shutdown(self) -> None:
        self.stop_current(clear_queue=True)
        with self._lock:
            proc = self._proc
        _kill_group(proc, signal.SIGKILL)
        self._q.put(None)
        self._pool.shutdown(wait=False)

    # ------------------------------------------------------------ splitting
    def _runs(self, text: str) -> list[tuple[str, int, str]]:
        """Turns text into a list of (voice, rate, part).

        A single-language text yields one part, so no `say` call is wasted.
        """
        if not (self.bilingual and self.voice_en):
            return [(self.voice, self.rate, text)]
        runs = split_runs(text)
        if len(runs) <= 1:
            return [(self.voice, self.rate, text)]
        return [((self.voice_en, self.rate_en, chunk) if lang == "en"
                 else (self.voice, self.rate, chunk)) for lang, chunk in runs]

    # ------------------------------------------------------------ playback
    def _spawn(self, cmd: list[str], data: bytes | None = None) -> None:
        # start_new_session: the child leads its own process group.
        # `say` hands synthesis/playback to a CHILD process, so terminating
        # only the parent did not stop the sound (the child kept reading).
        # As a group leader, killpg silences all of them at once.
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        with self._lock:
            self._proc = proc
        # `say`/`afplay` are separate processes and keep playing even if the
        # app dies. Write the pid to disk so both ./stop.sh and the next
        # start-up can clean up orphans.
        _note_pid(proc.pid)
        try:
            proc.communicate(data)
        finally:
            _forget_pid(proc.pid)
            with self._lock:
                self._proc = None

    def _is_default_output(self) -> bool:
        """Is the selected output already the system default?

        If so our own playback path is unnecessary - `afplay` reaches the same
        device. Opening one Bluetooth device as both input and output makes
        PortAudio raise -9986 (paInternalError); this check avoids that.
        """
        if self.output_device is None:
            return True
        try:
            import sounddevice as sd
            want = self.output_device
            cur = sd.query_devices(kind="output")
            if isinstance(want, int):
                return int(cur["index"]) == want
            return str(cur["name"]).strip().lower() == str(want).strip().lower()
        except Exception:
            return False

    def _play_file(self, path: str) -> bool:
        """Plays audio through sounddevice, applying the CURRENT volume per
        block.

        `afplay` does not allow volume changes while playing; doing it
        ourselves means moving the slider changes the reading in progress.
        Stopping is also instant (no process to kill).
        """
        try:
            import numpy as np
            import sounddevice as sd
            import wave
            with wave.open(path, "rb") as w:
                sr, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
                if width != 2:
                    return False                 # unexpected format
                block = 1024
                stream = sd.OutputStream(samplerate=sr, channels=ch,
                                         dtype="float32", blocksize=block,
                                         device=self.output_device)
                stream.start()
                try:
                    while not self._abort.is_set():
                        raw = w.readframes(block)
                        if not raw:
                            break
                        a = (np.frombuffer(raw, dtype=np.int16)
                             .astype(np.float32) / 32768.0)
                        gain = self.volume          # read FRESH on every block
                        if abs(gain - 1.0) > 0.001:
                            a = a * gain
                            np.clip(a, -1.0, 1.0, out=a)
                        stream.write(a.reshape(-1, ch))
                finally:
                    try:
                        stream.stop(); stream.close()
                    except Exception:
                        pass
            return True
        except Exception as exc:
            # Once it has failed there is no point retrying on every message.
            if not self._play_broken:
                print(f"[tts] çalma hatası ({exc!r}), bundan sonra afplay")
            self._play_broken = True
            return False

    def _say(self, voice: str, rate: int, text: str) -> None:
        if text.strip():          # empty text makes `say` hang
            self._spawn(["say", "-v", voice, "-r", str(rate), "-f", "-"],
                        text.encode("utf-8"))

    def _speak_parts(self, parts: list[str], pause: float) -> None:
        """Plays the parts as one stream with silence between them."""
        segments: list[tuple[str, int, str]] = []
        marks: list[int] = []
        for part in parts:
            runs = [s for s in self._runs(part) if s[2].strip()]
            segments.extend(runs)
            if runs:
                marks.append(len(segments) - 1)
        if not segments:
            return
        if self.seamless and len(segments) > 1:
            out, workdir = render.build(segments, pause_between=pause)
            if out:
                try:
                    # At full volume with no explicit output device, play with
                    # `afplay`. Our block-by-block path starves while Whisper
                    # runs and produces crackle; afplay is a separate process
                    # that manages the CoreAudio buffer itself and plays clean.
                    # The block path is only needed for live volume changes,
                    # since afplay cannot change volume mid-playback.
                    plain = (abs(self.volume - 1.0) < 0.001
                             and self._is_default_output())
                    if self._play_broken:
                        plain = True
                    if plain or not self._play_file(out):
                        self._spawn(["afplay", out])
                finally:
                    shutil.rmtree(workdir, ignore_errors=True)
                return
        for i, (v, rr, chunk) in enumerate(segments):     # fallback path
            if self._abort.is_set():
                return
            self._say(v, rr, chunk)
            if i in marks and self._abort.wait(pause):
                return

    def _speak(self, text: str, prefix: str) -> None:
        pre = self._runs(prefix) if prefix.strip() else []
        segments = [s for s in (pre + self._runs(text)) if s[2].strip()]
        if not segments:
            return
        # Pause AFTER the announcement: index within the full list
        pause_at = len(pre) - 1 if pre else -1

        first, rest = None, segments           # everything goes through the render path
        # A single part needs no concatenation, but the render path is still
        # preferred: volume can change live, no gap is left between parts and
        # stopping is instant. `say` already costs about a second, so
        # rendering adds no noticeable overhead.
        if not self.seamless and self.output_device is None:
            for i, (v, r, part) in enumerate(segments):     # plain path
                if self._abort.is_set():
                    return
                self._say(v, r, part)
                if i == pause_at and self.announce_pause > 0:
                    if self._abort.wait(self.announce_pause):
                        return
            return

        # Kalani arka planda hazirlat, bu arada ilk parcayi soyle.
        rest_pause_at = pause_at - 1          # index within `rest`
        rest_pause_at = pause_at             # tumu render'da
        future = self._pool.submit(render.build, rest, rest_pause_at,
                                   self.announce_pause)
        if first is not None:
            self._say(*first)
        if first is not None and pause_at == 0 and self.announce_pause > 0:
            if self._abort.wait(self.announce_pause):
                future.cancel()
                return
        try:
            out, workdir = future.result(timeout=90)
        except Exception:
            out, workdir = None, None
        if self._abort.is_set():
            if workdir:
                shutil.rmtree(workdir, ignore_errors=True)
            return
        if out:
            try:
                if not self._play_file(out):     # fallback path
                    self._spawn(["afplay", out])
            finally:
                shutil.rmtree(workdir, ignore_errors=True)
        else:                                  # preparation failed -> plain path
            for i, (v, r, part) in enumerate(rest):
                if self._abort.is_set():
                    return
                self._say(v, r, part)
                if i == rest_pause_at and self.announce_pause > 0:
                    if self._abort.wait(self.announce_pause):
                        return

    # ------------------------------------------------------------ loop
    def _run(self) -> None:
        while True:
            item = self._q.get()
            if item is None:
                return
            # While held, wait as if the message were still in the queue.
            while self._hold.is_set():
                time.sleep(0.1)
            meta = item.get("meta")
            if not self.enabled:
                continue
            self._busy.set()
            self._abort.clear()
            self.current_text = " ".join(
                [str(item.get("prefix") or ""), str(item.get("text") or "")]
                + [str(x) for x in (item.get("parts") or [])])
            if self.on_start:
                try:
                    self.on_start(meta)
                except Exception:
                    pass
            try:
                if item.get("parts"):
                    self._speak_parts(item["parts"], item.get("pause", 0.35))
                else:
                    self._speak(item.get("text", ""), item.get("prefix", ""))
            except Exception as exc:
                print(f"[tts] okunamadi: {exc}")
            finally:
                with self._lock:
                    self._proc = None
                self._busy.clear()
                self._last_text = self.current_text
                self._last_end = time.monotonic()
                self.current_text = ""
                if self.on_end:
                    try:
                        self.on_end()
                    except Exception:
                        pass
