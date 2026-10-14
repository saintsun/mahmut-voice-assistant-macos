"""Mikrofon yakalama + enerji tabanli konusma algilama (VAD).

Surekli dinler, konusma parcalarini kesip kuyruga birakir. Gurultu tabani
uyarlanir, boylece sessiz oda ile fanli oda ayni esikle calismaz.
"""
from __future__ import annotations

import collections
import queue
import threading
import time

import numpy as np
import sounddevice as sd


class Segmenter:
    """Cerceve cerceve ses alir, tamamlanmis konusma parcalari uretir."""

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
        self._voiced = 0     # segment boyunca esik ustu TOPLAM cerceve
        self._hot = 0        # ust uste esik ustu cerceve
        self._cold = 0       # ust uste esik alti cerceve
        self._active = False
        self.last_rms = 0.0
        self.speaking = False   # disaridan okunur (UI icin)

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

        # Gurultu tabani: sessizlikte hizli, konusmada cok yavas guncellenir.
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
                self._buf = list(self._pre)      # kelime basi kirpilmasin
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
        # Kisa gurultu patlamalari (tiklama, nefes, kapi) Whisper'i
        # halusinasyona sokuyor. Segmentte yeterince KONUSMA cercevesi
        # yoksa hic gonderme.
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


# Dahili mikrofonu tanimak icin (dil ayarina gore degisebiliyor)
_BUILTIN_HINTS = ("macbook", "built-in", "builtin", "dahili", "internal")

# Kulaklik/kulaklik seti mikrofonlari
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


def shares_bluetooth_device(input_name: str) -> bool:
    """Mikrofon ve hoparlor AYNI kablosuz cihaz mi?

    Boyleyse mikrofon akisi acik oldugu surece macOS cihazi HFP profiline
    dusuruyor ve OYNATMA cizirtili oluyor (Shazam dinlerken de ayni sey
    olur). Mikrofonu kapatmak profili A2DP'ye geri dondurur.
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
    """Okuma, mikrofonun DUYABILECEGI bir cikistan mi caliyor?

    Kulaklikta ses mikrofona gitmez; hoparlorde gider ve uygulama kendi
    okudugunu yaziya cevirir ("Mahmut test" satirlari aslinda kendi sesiydi).
    Ayni cihaz hem giris hem cikis ise (AirPods) kulaklik sayilir.
    """
    try:
        out = str(sd.query_devices(kind="output")["name"])
    except Exception:
        return True                      # bilmiyorsak guvenli taraf: hoparlor
    if input_name and out.strip().lower() == input_name.strip().lower():
        return False
    low = out.lower()
    if any(h in low for h in _HEADSET_HINTS):
        return False
    return True


def resolve_device(cfg: dict) -> tuple[int | None, str]:
    """(cihaz_indeksi, cihaz_adi) dondurur.

    config.json > audio.prefer:
      "headset" -> once kulaklik mikrofonu (VARSAYILAN). Masadan uzaktayken
                   dahili mikrofon seni duymaz; kulaklik duyar.
                   Bedeli: Bluetooth kulaklikta mikrofon acilinca macOS HFP
                   profiline duser ve OYNATMA kalitesi dusebilir.
      "builtin" -> once MacBook'un dahili mikrofonu (oynatma kalitesi bozulmaz)
      "system"  -> sistem varsayilani

    audio.device verilmisse (isim parcasi ya da indeks) o her seyin onunde.
    """
    want = cfg.get("device")
    inputs = _inputs()
    if isinstance(want, int):
        name = dict(inputs).get(want, {}).get("name", f"#{want}")
        return want, name
    if isinstance(want, str) and want.strip():
        for i, d in inputs:
            if want.lower() in d["name"].lower():
                return i, d["name"]
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
    """sounddevice akisini yonetir; mute edildiginde cerceveleri atar."""

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

    # --- durum ---
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
        """TTS calarken kendi sesimizi dinlememek icin."""
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

    # --- akis ---
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
        """Tercih edilen giris cihazi degistiyse akisi yeniden kurar.

        DIKKAT: PortAudio cihaz listesini baslangicta onbellege aliyor.
        Kulaklik takilip cikarildiginda liste kendiliginden guncellenmiyor;
        uygulama artik var olmayan cihazi dinlemeye devam edip sessizlik
        okuyor. Bu yuzden rescan=True ile PortAudio yeniden baslatilir.
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
        """Mikrofon acikken kac saniyedir TAM sessizlik geliyor.

        Cihaz ortadan kalktiginda PortAudio hata vermiyor, sadece sifir
        gonderiyor; bunu cihaz kaybi sinyali olarak kullaniyoruz.
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
