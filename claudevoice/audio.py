"""Microphone capture plus energy-based voice activity detection.

Listens continuously, cuts out speech segments and drops them on a queue. The
noise floor adapts, so a quiet room and a room with a fan do not share one
threshold.
"""
from __future__ import annotations

import collections
import queue
import threading
import time

import numpy as np
import sounddevice as sd


class Segmenter:
    """Takes audio frame by frame and emits finished speech segments."""

    def __init__(self, cfg: dict, out_queue: "queue.Queue[np.ndarray]"):
        self.sr = int(cfg["sample_rate"])
        self.frame = int(self.sr * cfg["frame_ms"] / 1000)
        self.ratio = float(cfg["vad_ratio"])
        self.min_rms = float(cfg["vad_min_rms"])
        self.start_frames = int(cfg["start_frames"])
        self.end_frames = max(1, int(cfg["silence_ms"] / cfg["frame_ms"]))
        self.max_frames = int(cfg["max_segment_sec"] * 1000 / cfg["frame_ms"])
        preroll = max(1, int(cfg["preroll_ms"] / cfg["frame_ms"]))

        self.out = out_queue
        self._pre = collections.deque(maxlen=preroll)
        self._buf: list[np.ndarray] = []
        self._floor = 0.01
        self.min_voiced = int(cfg.get("min_voiced_frames", 8))
        self._voiced = 0     # TOTAL frames above threshold in this segment
        self._hot = 0        # consecutive frames above threshold
        self._cold = 0       # consecutive frames below threshold
        self._active = False
        self.last_rms = 0.0
        self.speaking = False   # read from outside (for the UI)

    def reset(self) -> None:
        self._buf.clear()
        self._pre.clear()
        self._hot = self._cold = 0
        self._voiced = 0
        self._active = False
        self.speaking = False

    def feed(self, frame: np.ndarray) -> None:
        rms = float(np.sqrt(np.mean(np.square(frame))) + 1e-9)
        self.last_rms = rms

        # Noise floor: updated fast during silence, very slowly during speech.
        if rms < self._floor:
            self._floor = 0.90 * self._floor + 0.10 * rms
        else:
            self._floor = 0.999 * self._floor + 0.001 * rms
        self._floor = max(self._floor, 1e-5)

        threshold = max(self._floor * self.ratio, self.min_rms)
        loud = rms > threshold

        if not self._active:
            self._pre.append(frame)
            self._hot = self._hot + 1 if loud else 0
            if self._hot >= self.start_frames:
                self._active = True
                self.speaking = True
                self._buf = list(self._pre)      # keep the start of the word
                self._pre.clear()
                self._cold = 0
                self._voiced = self._hot
            return

        self._buf.append(frame)
        if loud:
            self._voiced += 1
        self._cold = 0 if loud else self._cold + 1
        if self._cold >= self.end_frames or len(self._buf) >= self.max_frames:
            self._flush()

    def _flush(self) -> None:
        # Short noise bursts (a click, a breath, a door) push Whisper into
        # hallucinating. If a segment holds too few SPEECH frames, drop it.
        if self._voiced < self.min_voiced:
            self.reset()
            return
        if self._buf:
            audio = np.concatenate(self._buf)
            try:
                self.out.put_nowait(audio)
            except queue.Full:
                pass
        self.reset()


# Used to recognise the built-in microphone (its name follows the UI language)
_BUILTIN_HINTS = ("macbook", "built-in", "builtin", "dahili", "internal")

# Headset and headphone microphones
_HEADSET_HINTS = (
    "airpods", "beats", "headset", "headphone", "kulaklik", "kulaklık",
    "buds", "bose", "jabra", "sony", "sennheiser", "soundcore", "jbl",
    "earphone", "earbud", "wh-", "wf-", "qc", "bluetooth",
)


def _inputs():
    import sounddevice as sd
    try:
        devices = sd.query_devices()
    except Exception:
        return []
    return [(i, d) for i, d in enumerate(devices) if d["max_input_channels"] > 0]


def _outputs():
    import sounddevice as sd
    try:
        devices = sd.query_devices()
    except Exception:
        return []
    return [(i, d) for i, d in enumerate(devices) if d["max_output_channels"] > 0]


def list_devices() -> dict:
    """Input and output devices to show in the panel."""
    def rows(items):
        seen, out = set(), []
        for i, d in items:
            name = str(d["name"]).strip()
            if name and name not in seen:
                seen.add(name)
                out.append({"index": i, "name": name})
        return out
    return {"inputs": rows(_inputs()), "outputs": rows(_outputs())}


def pick_device(want, items) -> tuple[int | None, str] | None:
    """Finds the device the user PICKED (by index or name fragment).

    Returns None when it is missing, and the caller falls back to automatic
    selection. That way, picking "the headset microphone" and then unplugging
    the headset does not leave the system deaf: it drops back to the built-in
    microphone.
    """
    if isinstance(want, bool) or want is None:
        return None
    if isinstance(want, int):
        for i, d in items:
            if i == want:
                return i, str(d["name"])
        return None
    text = str(want).strip().lower()
    if not text:
        return None
    for i, d in items:                       # exact name first
        if str(d["name"]).strip().lower() == text:
            return i, str(d["name"])
    for i, d in items:                       # then a fragment match
        if text in str(d["name"]).lower():
            return i, str(d["name"])
    return None


def resolve_output(cfg: dict, outputs=None) -> tuple[int | None, str]:
    """Returns (device_index, name); with no audio.output_device set, the
    system default is used (None)."""
    items = _outputs() if outputs is None else outputs
    hit = pick_device(cfg.get("output_device"), items)
    if hit:
        return hit
    if cfg.get("output_device"):
        print(f"[audio] çıkış {cfg.get('output_device')!r} yok, "
              f"sistem varsayılanına dönülüyor")
    return None, "sistem varsayılanı"


def shares_bluetooth_device(input_name: str) -> bool:
    """Are the microphone and the speaker the SAME wireless device?

    When they are, macOS can drop the device into the HFP profile while a
    microphone stream is open, which makes PLAYBACK crackle (Shazam shows the
    same behaviour while listening). Closing the microphone restores A2DP.
    """
    name = (input_name or "").strip().lower()
    if not name or any(h in name for h in _BUILTIN_HINTS):
        return False
    try:
        out = str(sd.query_devices(kind="output")["name"]).strip().lower()
    except Exception:
        return False
    return name == out


def output_is_loud(input_name: str = "") -> bool:
    """Is the reading playing through an output the microphone can HEAR?

    With headphones the sound never reaches the microphone; through speakers it
    does, and the app transcribes its own voice. When the same device serves as
    both input and output (AirPods) it counts as a headset.
    """
    try:
        out = str(sd.query_devices(kind="output")["name"])
    except Exception:
        return True                      # when unsure, assume speakers (the safe side)
    if input_name and out.strip().lower() == input_name.strip().lower():
        return False
    low = out.lower()
    if any(h in low for h in _HEADSET_HINTS):
        return False
    return True


def resolve_device(cfg: dict, inputs=None) -> tuple[int | None, str]:
    """Returns (device_index, device_name).

    config.json > audio.prefer:
      "headset" -> the headset microphone first (DEFAULT). Away from the desk
                   the built-in microphone cannot hear you; a headset can.
                   The cost: opening the microphone on a Bluetooth headset can
                   drop macOS into the HFP profile and degrade PLAYBACK.
      "builtin" -> the MacBook's own microphone first (playback stays clean)
      "system"  -> the system default

    An explicit audio.device (name fragment or index) overrides all of this.
    """
    want = cfg.get("device")
    inputs = _inputs() if inputs is None else inputs
    hit = pick_device(want, inputs)
    if hit:
        return hit
    if want:
        print(f"[audio] {want!r} bulunamadi, otomatik secime dönülüyor")

    prefer = cfg.get("prefer", "headset")
    order = {"headset": (_HEADSET_HINTS, _BUILTIN_HINTS),
             "builtin": (_BUILTIN_HINTS, _HEADSET_HINTS)}.get(prefer)
    if order:
        for hints in order:
            for i, d in inputs:
                if any(h in d["name"].lower() for h in hints):
                    return i, d["name"]
    return None, "sistem varsayılanı"


class Microphone:
    """Manages the sounddevice stream and drops frames while muted."""

    def __init__(self, cfg: dict, out_queue: "queue.Queue[np.ndarray]"):
        self.cfg = cfg
        self.seg = Segmenter(cfg, out_queue)
        self.sr = self.seg.sr
        self.frame = self.seg.frame
        self.device, self.device_name = resolve_device(cfg)
        self._zero_since: float | None = None
        self._stream: sd.InputStream | None = None
        self._enabled = threading.Event()
        self._muted_until = 0.0
        self._lock = threading.Lock()
        self.error: str | None = None

    # --- state ---
    @property
    def enabled(self) -> bool:
        return self._enabled.is_set()

    def set_enabled(self, on: bool) -> None:
        if on:
            self._enabled.set()
        else:
            self._enabled.clear()
            self.seg.reset()

    def mute_for(self, seconds: float) -> None:
        """Keeps us from listening to our own voice while TTS plays."""
        with self._lock:
            self._muted_until = max(self._muted_until, time.monotonic() + seconds)
        self.seg.reset()

    def unmute_after(self, seconds: float) -> None:
        with self._lock:
            self._muted_until = time.monotonic() + seconds
        self.seg.reset()

    def output_is_loud(self) -> bool:
        return output_is_loud(self.device_name)

    def shares_output(self) -> bool:
        return shares_bluetooth_device(self.device_name)

    @property
    def open(self) -> bool:
        return self._stream is not None

    def _muted(self) -> bool:
        with self._lock:
            return time.monotonic() < self._muted_until

    # --- stream ---
    def _callback(self, indata, frames, time_info, status):  # noqa: ARG002
        if not self._enabled.is_set() or self._muted():
            return
        mono = indata[:, 0] if indata.ndim > 1 else indata
        self.seg.feed(np.asarray(mono, dtype=np.float32).copy())

    def start(self) -> bool:
        try:
            self._stream = sd.InputStream(
                samplerate=self.sr,
                blocksize=self.frame,
                dtype="float32",
                channels=1,
                device=self.device,
                callback=self._callback,
            )
            self._stream.start()
            self.error = None
            return True
        except Exception as exc:
            self.error = str(exc)
            print(f"[audio] mikrofon acilamadi: {exc}")
            return False

    def refresh_device(self, rescan: bool = False) -> str | None:
        """Rebuilds the stream when the preferred input device changed.

        CAREFUL: PortAudio caches the device list at start-up. Plugging or
        unplugging a headset does not refresh it, so the app keeps listening to
        a device that no longer exists and reads silence. rescan=True
        re-initializes PortAudio to work around this.
        """
        import sounddevice as sd
        if rescan:
            was_on = self.enabled
            self.stop()
            try:
                sd._terminate()
                sd._initialize()
            except Exception as exc:
                print(f"[audio] cihaz listesi tazelenemedi: {exc}")
            idx, name = resolve_device(self.cfg)
            changed = name != self.device_name
            self.device, self.device_name = idx, name
            if self.start():
                self.set_enabled(was_on)
            else:
                print(f"[audio] {name!r} açılamadı: {self.error}")
            return name if changed else None

        try:
            idx, name = resolve_device(self.cfg)
        except Exception:
            return None
        if name == self.device_name:
            return None
        was_on = self.enabled
        self.stop()
        self.device, self.device_name = idx, name
        if self.start():
            self.set_enabled(was_on)
            return name
        return None

    def silent_for(self) -> float:
        """How many seconds of EXACT silence have arrived with the mic open.

        When a device disappears PortAudio raises no error, it just delivers
        zeros, so this is used as the signal that the device is gone.
        """
        if not self.enabled or self._stream is None:
            self._zero_since = None
            return 0.0
        if self.seg.last_rms > 1e-9:
            self._zero_since = None
            return 0.0
        now = time.monotonic()
        if self._zero_since is None:
            self._zero_since = now
            return 0.0
        return now - self._zero_since

    def stop(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
