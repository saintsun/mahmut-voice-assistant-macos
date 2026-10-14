"""Sirali seslendirme (macOS `say`).

Iki dilli okuma metni cok parcaya boluyor ve her `say` cagrisi ~1 saniye olu
zaman getiriyor. Bu yuzden:

  * ILK parca dogrudan `say` ile soylenir -> konusma hemen baslar,
  * kalan parcalar ARKA PLANDA paralel olarak sese basilip ffmpeg ile tek
    dosyada birlestirilir, `afplay` ile tek seferde calinir -> aradaki
    bosluklar kaybolur, olu zaman 1 parcaya iner.

Hazirlama suresi ilk parcanin calinmasi sirasinda gectigi icin kullaniciya
ek gecikme olarak yansimaz. ffmpeg/afplay yoksa sirali `say`e donulur.

Konusurken mikrofon susturulur (kendi sesini dinleyip geri gondermesin).
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
    """Sureci VE dogurdugu alt surecleri oldurur.

    `say` calmayi bir alt surece yaptiriyor; sadece ebeveyni oldurmek
    sesi kesmiyor. Surec grubu lideri oldugu icin killpg hepsini yakalar.
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
    """Onceki calismadan kalan `say`/`afplay` sureclerini oldurur.

    Uygulama SIGKILL ile olurse cocuklar hayatta kalip okumaya devam ediyor;
    ust uste binen sesler "patlak" duyuluyor. Acilista temizlenir.
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
            # Pid geri donusturulmus olabilir: sadece bizim calma sureclerimizi oldur
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
        # `say`in ses seviyesi secenegi YOK ([[volm]] gomulu komutu da yok
        # sayiliyor, olctum). Seviye ancak dosyaya basip `afplay -v` ile
        # calarak degistirilebiliyor; bu yuzden seviye 1.0 degilse okuma
        # her zaman render yolundan gecer.
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
        # Panelden ses yakalarken okuma kuyrugu bekler: aksi halde yeni
        # gelen mesaj okunmaya baslayip mikrofonu kisiyor (duck) ve
        # kullanicinin konusmasi hic duyulmuyor.
        self._hold = threading.Event()
        # O an okunan metin: mikrofon acik kalirsa kendi sesimizi
        # komut sanmayalim diye karsilastiriliyor.
        self.current_text = ""
        # Kullanici panelden cikis cihazi sectiyse o cihazdan calinir.
        # None: sistem varsayilani. Secili cihazda `say` yolu kullanilamaz
        # (surec sistem cikisina calar), bu yuzden render yolu zorunlu olur.
        self.output_device = None
        self._last_text = ""
        self._last_end = 0.0
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="tts-render")
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------ durum
    @property
    def busy(self) -> bool:
        return self._busy.is_set()

    def recent_text(self, grace: float = 8.0) -> str:
        """O an okunan metin + yeni bitmis okumanin metni.

        Transkripsiyon ~1 sn gecikmeli geldigi icin okuma biter bitmez
        koruma kalkarsa son cumlenin yankisi komut olarak isleniyor.
        """
        if self.current_text:
            return self.current_text
        if self._last_text and time.monotonic() - self._last_end < grace:
            return self._last_text
        return ""

    def set_hold(self, on: bool) -> None:
        """Okumayi beklet / devam ettir (kuyruk korunur)."""
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
        """meta  : bu metnin hangi oturumdan geldigi (okunurken geri bildirilir)
        prefix: icerikten once AYRI bir cumle olarak okunur (anons).

        prefix ayni kuyruk ogesinde tasinir; boylece araya baska bir
        oturumun mesaji giremez.
        """
        if self.enabled and text.strip():
            self._q.put({"text": text, "meta": meta, "prefix": prefix})

    def say_parts(self, parts: list[str], meta: object = None,
                  pause: float = 0.35) -> None:
        """Her parcayi ARALARINA sessizlik koyarak okur.

        Liste okumak icin: noktalama ile guvenilir duraklama elde
        edilemiyor (olctum — nokta cogu yerde hic duraklama uretmiyor,
        virgul ise yanlis yere koyuyor). Gercek sessizlik tek cozum.
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

    # ------------------------------------------------------------ parcalama
    def _runs(self, text: str) -> list[tuple[str, int, str]]:
        """Metni (ses, hiz, parca) listesine cevirir.

        Tek dil varsa tek parca dondurur; gereksiz `say` cagrisi olmaz.
        """
        if not (self.bilingual and self.voice_en):
            return [(self.voice, self.rate, text)]
        runs = split_runs(text)
        if len(runs) <= 1:
            return [(self.voice, self.rate, text)]
        return [((self.voice_en, self.rate_en, chunk) if lang == "en"
                 else (self.voice, self.rate, chunk)) for lang, chunk in runs]

    # ------------------------------------------------------------ calma
    def _spawn(self, cmd: list[str], data: bytes | None = None) -> None:
        # start_new_session: cocuk kendi surec grubunun lideri olur.
        # `say` sentezi/calmayi bir ALT surece yaptiriyor; sadece ebeveyni
        # terminate etmek sesi kesmiyordu (cocuk okumaya devam ediyordu).
        # Grup lideri yapinca killpg ile hepsi birden susturulabiliyor.
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        with self._lock:
            self._proc = proc
        # `say`/`afplay` ayri sureclerdir ve uygulama olse bile calmaya devam
        # ederler. Pid'i diske yaz: hem ./stop.sh hem de bir sonraki acilis
        # yetim kalanlari temizleyebilsin.
        _note_pid(proc.pid)
        try:
            proc.communicate(data)
        finally:
            _forget_pid(proc.pid)
            with self._lock:
                self._proc = None

    def _play_file(self, path: str) -> bool:
        """Sesi sounddevice ile calar, her blokta GUNCEL seviyeyi uygular.

        `afplay` calarken seviye degistirmeye izin vermiyor; kendimiz
        caldigimizda kaydiragi oynattigin an o anki okuma da degisiyor.
        Ayrica durdurma aninda kesiliyor (surec oldurmeye gerek yok).
        """
        try:
            import numpy as np
            import sounddevice as sd
            import wave
            with wave.open(path, "rb") as w:
                sr, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
                if width != 2:
                    return False                 # beklenmeyen bicim
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
                        gain = self.volume          # her blokta TAZE okunur
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
            print(f"[tts] çalma hatası ({exc!r}), afplay'e dönülüyor")
            return False

    def _say(self, voice: str, rate: int, text: str) -> None:
        if text.strip():          # bos metin `say`i kilitliyor
            self._spawn(["say", "-v", voice, "-r", str(rate), "-f", "-"],
                        text.encode("utf-8"))

    def _speak_parts(self, parts: list[str], pause: float) -> None:
        """Parcalari aralarinda sessizlikle, tek akis halinde calar."""
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
                    if not self._play_file(out):
                        self._spawn(["afplay", out])
                finally:
                    shutil.rmtree(workdir, ignore_errors=True)
                return
        for i, (v, rr, chunk) in enumerate(segments):     # yedek yol
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
        # Anonstan SONRA duraklama: tam listedeki indeks
        pause_at = len(pre) - 1 if pre else -1

        first, rest = None, segments           # tumu render'dan gecer
        # Tek parca kaldiysa birlestirmeye gerek yok; dogrudan soyle.
        # Render yolu HER ZAMAN tercih edilir: ses seviyesi canli
        # degistirilebiliyor, parcalar arasinda bosluk kalmiyor ve durdurma
        # aninda calisiyor. `say`in kendi ~1 sn gecikmesi zaten var, render
        # belirgin bir ek maliyet getirmiyor.
        if not self.seamless and self.output_device is None:
            for i, (v, r, part) in enumerate(segments):     # sade yol
                if self._abort.is_set():
                    return
                self._say(v, r, part)
                if i == pause_at and self.announce_pause > 0:
                    if self._abort.wait(self.announce_pause):
                        return
            return

        # Kalani arka planda hazirlat, bu arada ilk parcayi soyle.
        rest_pause_at = pause_at - 1          # `rest` icindeki indeks
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
                if not self._play_file(out):     # yedek yol
                    self._spawn(["afplay", out])
            finally:
                shutil.rmtree(workdir, ignore_errors=True)
        else:                                  # hazirlama basarisiz -> sade yol
            for i, (v, r, part) in enumerate(rest):
                if self._abort.is_set():
                    return
                self._say(v, r, part)
                if i == rest_pause_at and self.announce_pause > 0:
                    if self._abort.wait(self.announce_pause):
                        return

    # ------------------------------------------------------------ dongu
    def _run(self) -> None:
        while True:
            item = self._q.get()
            if item is None:
                return
            # Beklet aciksa mesaji kuyrukta tutuyormus gibi bekle.
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
