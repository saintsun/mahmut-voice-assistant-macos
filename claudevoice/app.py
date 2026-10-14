"""ClaudeVoice - menubar uygulamasi.

Giris:  mikrofon -> VAD -> Whisper -> sozluk duzeltme -> tampon
        tamponun sonunda "tamam mahmut"        -> Claude'a yapistir + Enter
        tamponun sonunda "<ad> sec mahmut"     -> o konusmaya gec (deep link)

Cikis:  TUM canli oturumlarin transcript'leri izlenir; gelen asistan metni
        markdown'dan temizlenip "<oturum adi> mesaji: ..." diye okunur.
        Paralel gelen mesajlar tek kuyrukta sirayla seslendirilir.
"""
from __future__ import annotations

import atexit
import collections
import functools
import json
import os
import queue
import re
import resource
import signal
import subprocess
import sys
import threading
import time

import rumps

from .audio import Microphone
from .clean import to_speech
from .config import CONFIG_PATH, MUTED_PATH, STATE_PATH, Config
from .glossary import Glossary
from . import langpacks
from .inject import KEYCODES, Injector, ax_request, ax_trusted
from .panel import Panel
from .phrases import Matcher, fold, tokenize, word_eq
from .sessions import (Registry, TitleIndex, find_exact,
                       resume_session, switch_to, wait_for_session,
                       wait_for_session_id)

from .turkish import dative
from .speak import Speaker, kill_orphans
from .stt import Transcriber
from .watcher import TranscriptWatcher

# OFF    : mikrofon tamamen kapali (menubar dugmesi)
# SLEEP  : "mahmut dur" — mikrofon acik ama SADECE "mahmut başla" dinlenir
# ARMED  : "hey mahmut" bekleniyor
# LIVE   : konusulan her sey tamponlaniyor
# Numarali liste icin Turkce sayi ve sira sozcukleri
NUM_WORDS = ["", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz",
             "dokuz", "on", "on bir", "on iki"]
ORDINALS = ["", "birinci", "ikinci", "üçüncü", "dördüncü", "beşinci",
            "altıncı", "yedinci", "sekizinci", "dokuzuncu", "onuncu",
            "on birinci", "on ikinci"]
# Belirtme hali: "birinciyi seç" de deniyor ve "birinciyi" ile "birinci"
# arasinda IKI harf fark var — bulanik tolerans (1 harf) yakalamiyordu.
ORDINALS_ACC = ["", "birinciyi", "ikinciyi", "üçüncüyü", "dördüncüyü",
                "beşinciyi", "altıncıyı", "yedinciyi", "sekizinciyi",
                "dokuzuncuyu", "onuncuyu", "on birinciyi", "on ikinciyi"]
NUM_ACC = ["", "biri", "ikiyi", "üçü", "dördü", "beşi", "altıyı", "yediyi",
           "sekizi", "dokuzu", "onu", "on biri", "on ikiyi"]

OFF, SLEEP, ARMED, LIVE = "off", "sleep", "armed", "live"
ICON = {OFF: "⚪️", SLEEP: "😴", ARMED: "🎙", LIVE: "🔴"}


# Mesajin yazilacagi uygulama. Codex'in ayri bir masaustu uygulamasi yok:
# ChatGPT.app'in bundle id'si zaten com.openai.codex (eski uygulama
# "ChatGPT Classic" = com.openai.chat).
# enabled=False olan hedef listede gorunur ama SECILEMEZ (henuz denenmedi).
TARGETS = {
    "claude": {"label": "Claude Code", "enabled": True,
               "bundle_id": "com.anthropic.claudefordesktop"},
    "codex":  {"label": "GPT Codex (ChatGPT)", "enabled": False,
               "bundle_id": "com.openai.codex"},
}

APP_NAME = "Mahmut"                        # menu cubugu adi (kisa durmali)
APP_FULL_NAME = "Mahmut: Voice Assistant"  # Dock/Finder adi
ICON_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "assets", "icon.png")


def _brand() -> None:
    """Uygulama adini ve ikonunu calisma aninda ayarlar.

    Bundle'in icine ikon KOPYALANMAZ: imza bozulur ve Erisilebilirlik izni
    sifirlanir. Python alt surec olarak calistigi icin macOS aksi halde
    uygulamayi "Python" diye gosteriyor.
    """
    try:
        from Foundation import NSBundle
        b = NSBundle.mainBundle()
        info = b.localizedInfoDictionary() or b.infoDictionary()
        if info is not None:
            info["CFBundleName"] = APP_NAME
            info["CFBundleDisplayName"] = APP_FULL_NAME
    except Exception as exc:
        print(f"[marka] ad ayarlanamadi: {exc}")
    try:
        from AppKit import NSApplication, NSImage
        img = NSImage.alloc().initWithContentsOfFile_(ICON_PATH)
        if img is not None:
            NSApplication.sharedApplication().setApplicationIconImage_(img)
    except Exception as exc:
        print(f"[marka] ikon ayarlanamadi: {exc}")


def _uniq(items) -> list:
    """Sirayi koruyarak tekrarlari atar (ayni yazim iki kez gorunmesin)."""
    seen, out = set(), []
    for x in items or []:
        k = fold(str(x))
        if k and k not in seen:
            seen.add(k)
            out.append(x)
    return out


class ClaudeVoice(rumps.App):
    def __init__(self):
        _brand()
        super().__init__(APP_NAME, title="⚪️", quit_button=None)
        self.cfg = Config()
        self.lock = threading.Lock()

        self.state = OFF
        self.buffer = ""
        self.status = "başlatılıyor…"
        self.last_sent = ""
        self.wake_mode = bool(self.cfg.get("ui", "wake_word_mode", True))
        self._last_announced: str | None = None
        self._session_sig: tuple = ()
        self._last_received: str | None = None   # son GELEN mesajin oturumu
        self._last_heard: str | None = None      # son OKUNAN mesajin oturumu
        self.reply_to: str | None = None         # "cevap mahmut" hedefi
        self.explicit_listen = False             # "mahmut başla" dendi mi
        # Zamanlanmis gorevler (routines) ada gore sessize alinir;
        # menuden elle susturulanlar .muted.json'da saklanir.
        self.exclude_patterns = [fold(x) for x in
                                 self.cfg.get("watch", "exclude_patterns", [])]
        self.muted: set[str] = self._load_muted()
        self.mute_routines = bool(self.cfg.get("watch", "mute_routines", True))
        self._mute_sig: tuple = ()
        self.last_transcript = ""                # Whisper en son ne duydu
        # Son duyulanlarin arsivi: yanlis duymalari toplayip kelime
        # setlerine eklemek icin. Panelde gorunur ve kopyalanabilir.
        self.history: collections.deque = collections.deque(
            maxlen=int(self.cfg.get("ui", "history_size", 200)))
        self._last_action = ""      # son metnin hangi komutu tetikledigi
        self._buffer_at = 0.0       # tampona en son ne zaman ekleme yapildi
        self._cpu_prev: tuple[float, float] | None = None
        self._cpu_pct = 0.0
        self._rss_mb = 0.0
        self._cores = os.cpu_count() or 1
        self._voices_cache: list[dict] = []
        # Her baslangicta degisen kimlik: panel bunu gorup kendini yeniler,
        # boylece yeniden baslattigimda acik sekme guncel kodu alir.
        self._boot_id = f"{int(time.time())}-{os.getpid()}"
        # "Dinle ve ekle": bir komut icin bekleyen yakalama
        self._amsg = ""                       # son panel eyleminin sonucu
        self._capture: str | None = None      # komut anahtari
        self._capture_text = ""               # duyulan metin (onay bekler)
        # Panelde calisirken sistem arkada tepki vermesin: komutlar islenmez,
        # gelen mesajlar okunmaz. Yakalama acikken kendiliginden devreye girer.
        self.paused = False
        self.audio_q: "queue.Queue" = queue.Queue(maxsize=24)
        self.mic = Microphone(self.cfg["audio"], self.audio_q)
        self.stt = Transcriber(self.cfg["stt"])
        self.matcher = Matcher(self.cfg["phrases"])
        # Arayuz metinleri cagri adindan turetilir; config'de adi degistirince
        # menu ve durum satirlari kendiliginden guncellenir.
        self.call_name = self.cfg.get("phrases", "name", "mahmut").capitalize()
        # Sesle tetiklenen uygulama kisayollari. DIKKAT: self.matcher'dan
        # SONRA gelmeli — once gelirse AttributeError olusuyor, except onu
        # yutuyor ve kisayollar sessizce hic kaydedilmiyordu.
        # (kisayol, kaliplar, cevap) uclulerinden olusur. Bir kisayolun
        # birden cok eylem grubu olabilir ("aç" / "kapat" / duz anahtar);
        # her grup kendi sesli cevabini tasir.
        self.hotkeys = []
        self._hotkey_phrases: dict = {}
        self._hotkey_ref: list[tuple[int, int]] = []   # (kisayol, eylem grubu)
        for hk_i, hk in enumerate(self.cfg.raw("hotkeys", []) or []):
            groups = hk.get("actions")
            if not groups:                       # eski duz bicim
                groups = [{"phrases": hk.get("phrases", []),
                           "reply": hk.get("reply"),
                           "label": hk.get("name")}]
            for grp_i, grp in enumerate(groups):
                try:
                    pats = self.matcher.compile_extra(grp.get("phrases", []))
                    if pats:
                        label = (grp.get("label") or grp.get("reply")
                                 or hk.get("name", "kısayol"))
                        self.hotkeys.append((hk, pats, grp.get("reply"), label))
                        self._hotkey_phrases.setdefault(id(hk), {})[label] = \
                            grp.get("phrases", [])
                        self._hotkey_ref.append((hk_i, grp_i))
                except Exception as exc:
                    print(f"[hotkey] {hk.get('name')!r} derlenemedi: {exc!r}")
        print(f"[hotkey] {len(self.hotkeys)} kısayol eylemi yüklendi")
        self.favorites: list[dict] = self._load_favorites()
        self._compile_favorites()
        self.glossary = Glossary()
        self.injector = Injector(self.cfg["inject"])
        self.registry = Registry()
        self.titles = TitleIndex()        # kapali oturumlari bulmak icin
        self.speaker = Speaker(self.cfg["tts"],
                               on_start=self._tts_started, on_end=self._tts_ended)
        self.watcher = TranscriptWatcher(self._on_assistant_text, self.registry)
        self.panel = Panel(self, int(self.cfg.get("ui", "panel_port", 8765)))

        self.stop_hotkey = ""
        self._install_stop_hotkey()
        self._build_menu()
        self._boot()

    # ------------------------------------------------------------ menu
    def _build_menu(self) -> None:
        self.mi_listen = rumps.MenuItem("Dinleme: Kapalı", callback=self.toggle_listen)
        self.mi_wake = rumps.MenuItem("", callback=self.toggle_wake)
        self.mi_tts = rumps.MenuItem("", callback=self.toggle_tts)
        self.mi_sessions = rumps.MenuItem("Konuşmalar")
        self.mi_mute = rumps.MenuItem("Sesli okunacaklar")
        self.mi_buffer = rumps.MenuItem("Tampon: (boş)", callback=None)
        self.mi_send = rumps.MenuItem("Tamponu şimdi gönder", callback=self.send_now)
        self.mi_clear = rumps.MenuItem("Tamponu temizle", callback=self.clear_buffer)
        self.mi_hush = rumps.MenuItem("Okumayı kes", callback=self.hush)
        self.mi_status = rumps.MenuItem("", callback=None)
        self.menu = [
            self.mi_listen, self.mi_wake, self.mi_tts, None,
            self.mi_sessions, self.mi_mute, None,
            self.mi_buffer, self.mi_send, self.mi_clear, self.mi_hush, None,
            self.mi_status,
            rumps.MenuItem("Kontrol panelini aç", callback=self.open_panel),
            rumps.MenuItem("Ayarları aç (config.json)", callback=self.open_config),
            rumps.MenuItem("Çıkış", callback=self.quit_app),
        ]
        self._refresh_menu()

    def _refresh_sessions_menu(self) -> None:
        """Konusma listesi degistiyse alt menuyu yeniden kur."""
        try:
            sessions = self.registry.all()
        except Exception:
            return
        sig = tuple((s.name, s.host_id, s.status) for s in sessions)
        if sig == self._session_sig:
            return
        self._session_sig = sig
        # rumps alt menuyu ilk ogede olusturur; o ana kadar clear() patlar.
        try:
            self.mi_sessions.clear()
        except AttributeError:
            pass
        if not sessions:
            self.mi_sessions.add(rumps.MenuItem("(açık konuşma yok)"))
            return
        for s in sessions:
            mark = "●" if s.status == "busy" else "○"
            item = rumps.MenuItem(f"{mark} {s.name}",
                                  callback=functools.partial(self._menu_switch, s))
            self.mi_sessions.add(item)

    # ------------------------------------------------------- susturma
    def _load_muted(self) -> set[str]:
        try:
            with open(MUTED_PATH, encoding="utf-8") as fh:
                return set(json.load(fh))
        except Exception:
            return set()

    def _save_muted(self) -> None:
        try:
            with open(MUTED_PATH, "w", encoding="utf-8") as fh:
                json.dump(sorted(self.muted), fh, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def is_muted(self, name: str) -> bool:
        """Bu konusmanin mesajlari sesli okunmasin mi?

        Sirasiyla: menuden elle susturulmus mu -> zamanlanmis gorev mi
        (transcript'teki scheduled-trigger izinden) -> adi desenlere uyuyor mu.
        """
        if name in self.muted:
            return True
        if self.mute_routines:
            try:
                for s in self.registry.all():
                    if s.name == name:
                        return s.routine or self._name_excluded(name)
            except Exception:
                pass
        return self._name_excluded(name)

    def _name_excluded(self, name: str) -> bool:
        f = fold(name)
        return any(pat in f for pat in self.exclude_patterns)

    def _toggle_mute(self, name: str, _=None) -> None:
        # Desen yuzunden susturulmussa, elle acmak icin ada "izin" ver.
        if name in self.muted:
            self.muted.discard(name)
        elif self.is_muted(name):
            self.exclude_patterns = [p for p in self.exclude_patterns
                                     if p not in fold(name)]
        else:
            self.muted.add(name)
        self._save_muted()
        self._mute_sig = ()                      # menuyu yeniden ciz
        self._set_status(("okunmayacak: " if self.is_muted(name)
                          else "okunacak: ") + name)

    def _refresh_mute_menu(self) -> None:
        try:
            sessions = self.registry.all()
        except Exception:
            return
        sig = tuple((s.name, self.is_muted(s.name)) for s in sessions)
        if sig == self._mute_sig:
            return
        self._mute_sig = sig
        try:
            self.mi_mute.clear()
        except AttributeError:
            pass
        if not sessions:
            self.mi_mute.add(rumps.MenuItem("(açık konuşma yok)"))
            return
        for s in sessions:
            item = rumps.MenuItem(s.name,
                                  callback=functools.partial(self._toggle_mute, s.name))
            item.state = 0 if self.is_muted(s.name) else 1
            self.mi_mute.add(item)

    def _menu_switch(self, session, _=None) -> None:
        ok, msg = switch_to(session)
        self._set_status(f"geçildi: {msg}" if ok else f"geçilemedi: {msg}")

    def _refresh_menu(self) -> None:
        with self.lock:
            state, buf, status = self.state, self.buffer, self.status
        label = {OFF: "Kapalı", SLEEP: "Tatilde 😴"}.get(state, "Açık")
        self.mi_listen.title = f"Dinleme: {label}"
        self.mi_listen.state = 1 if state in (ARMED, LIVE) else 0
        self.mi_wake.title = (f'Mod: "hey {self.call_name}" bekle' if self.wake_mode
                              else "Mod: sürekli dinle")
        self.mi_wake.state = 1 if self.wake_mode else 0
        self.mi_tts.title = f"Sesli cevap: {'Açık' if self.speaker.enabled else 'Kapalı'}"
        self.mi_tts.state = 1 if self.speaker.enabled else 0
        short = buf if len(buf) <= 48 else "…" + buf[-47:]
        self.mi_buffer.title = f"Tampon: {short}" if buf else "Tampon: (boş)"
        self.mi_status.title = (f"Durum: {status}" if ax_trusted()
                                else "Durum: ⚠️ Erişilebilirlik izni YOK")
        self._refresh_sessions_menu()
        self._refresh_mute_menu()

        if self.speaker.busy:
            self.title = "🔊"
        elif state == SLEEP:
            self.title = ICON[SLEEP]
        elif state == LIVE and buf:
            self.title = f"🔴 {len(buf.split())}"
        else:
            self.title = ICON[state]

    @rumps.timer(0.4)
    def _tick(self, _) -> None:
        # Takipci olduyse geri getir: olmazsa mesajlar sessizce okunmaz.
        self._wd = getattr(self, "_wd", 0) + 1
        if self._wd % 25 == 0:                 # ~10 saniyede bir
            try:
                if self.watcher.ensure_alive():
                    self._set_status("transkript takibi yeniden başlatıldı")
            except Exception:
                pass
        self._refresh_menu()
        self._ticks = getattr(self, "_ticks", 0) + 1
        if self._ticks % 5 == 0:
            self._write_state()
        if self._ticks % 10 == 0:            # ~4 sn
            self._check_mic()
        if self._ticks % 7 == 0:             # ~3 sn
            self._sample_usage()
            self._expire_buffer()
        if self._ticks % 25 == 0:            # ~10 sn: ad degisti mi
            try:
                self._heal_favorites()
            except Exception as exc:
                print(f"[favori] güncelleme hatası: {exc!r}")

    def _expire_buffer(self) -> None:
        """Uzun suredir eklenmeyen tamponu bosaltir.

        Konusurken komut demeyi unutunca ortam konusmasi tamponda birikip
        duruyordu; sonradan "tamam mahmut" denince hepsi birden gidiyordu.
        """
        timeout = float(self.cfg.get("ui", "buffer_timeout_sec", 180) or 0)
        if timeout <= 0 or not self._buffer_at:
            return
        with self.lock:
            if not self.buffer:
                return
        if time.monotonic() - self._buffer_at < timeout:
            return
        with self.lock:
            n = len(self.buffer.split())
            self.buffer = ""
        self._buffer_at = 0.0
        self._set_status(f"tampon zaman aşımıyla temizlendi ({n} kelime)")
        print(f"[tampon] {timeout:.0f} sn eklenmedi, temizlendi ({n} kelime)")

    def _sample_usage(self) -> None:
        """Kendi CPU ve bellek kullanimimizi olcer.

        CPU: getrusage farkiyla hesaplanir (alt surecler dahil) — ek surec
        acmaya gerek yok. Bellek: macOS'ta guncel RSS icin `ps` gerekiyor,
        o yuzden seyrek ornekleniyor.
        """
        try:
            me = resource.getrusage(resource.RUSAGE_SELF)
            kids = resource.getrusage(resource.RUSAGE_CHILDREN)
            cpu = (me.ru_utime + me.ru_stime + kids.ru_utime + kids.ru_stime)
            now = time.monotonic()
            if self._cpu_prev is not None:
                dt = now - self._cpu_prev[0]
                if dt > 0:
                    self._cpu_pct = max(0.0, 100.0 * (cpu - self._cpu_prev[1]) / dt)
            self._cpu_prev = (now, cpu)
        except Exception:
            pass
        try:
            out = subprocess.run(["ps", "-o", "rss=", "-p", str(os.getpid())],
                                 capture_output=True, text=True, timeout=5).stdout
            self._rss_mb = int(out.strip() or 0) / 1024.0
        except Exception:
            pass

    def _check_mic(self) -> None:
        """Cihaz kaybini yakalar ve yeniden kurar.

        Iki tetikleyici:
          * mikrofon acik ama 5 sn'dir TAM sessizlik -> cihaz ortadan kalkmis
            (kulaklik cikarildi), PortAudio listesi tazelenip yeniden baglanir
          * her ~45 sn'de bir, bos anda -> yeni takilan cihazi fark etmek icin
        """
        try:
            silent = self.mic.silent_for()
            busy = self.speaker.busy or self.mic.seg.speaking
            with self.lock:
                buffering = bool(self.buffer)
            self._since_scan = getattr(self, "_since_scan", 0) + 1

            if silent > 5.0:
                name = self.mic.refresh_device(rescan=True)
                self._since_scan = 0
                self._set_status(f"mikrofon yeniden bağlandı: "
                                 f"{name or self.mic.device_name}")
                print(f"[audio] sessizlik algılandı, yeniden bağlanıldı: "
                      f"{self.mic.device_name!r}")
                return
            if self._since_scan >= 11 and not busy and not buffering:
                self._since_scan = 0
                changed = self.mic.refresh_device(rescan=True)
                if changed:
                    self._set_status(f"mikrofon değişti: {changed}")
                    print(f"[audio] cihaz değişti: {changed!r}")
        except Exception as exc:
            print(f"[audio] cihaz kontrolü hatası: {exc!r}")

    def _write_state(self) -> None:
        """Calisan uygulamanin gercek durumunu .state.json'a yazar.

        AX izni surec bazinda verildigi icin, iznin GERCEKTEN taninip
        taninmadigini sadece calisan uygulama bilir.
        """
        try:
            with self.lock:
                data = {"state": self.state, "buffer": self.buffer,
                        "status": self.status, "last_sent": self.last_sent}
            data.update({
                "ax_trusted": bool(ax_trusted()),
                "mic_running": self.mic._stream is not None,
                "mic_enabled": self.mic.enabled,
                "mic_error": self.mic.error,
                "mic_rms": round(self.mic.seg.last_rms, 6),
                "last_transcript": self.last_transcript,
            "boot": self._boot_id,
            "capture": {"key": self._capture, "text": self._capture_text},
            "target": self.cfg.get("inject", "target", "claude"),
            "stop_hotkey": self.stop_hotkey,
            "last_received": self._last_received,
            "recv_count": getattr(self, "_recv_count", 0),
            "watching": list(self.watcher.watched),
            "panel_port": self.panel.port,
            "targets": [{"code": k, "label": v["label"],
                         "enabled": bool(v.get("enabled"))}
                        for k, v in TARGETS.items()],
            "paused": self.paused,
            "history": list(self.history),
                "stt_ready": self.stt.ready,
                "stt_error": self.stt.load_error,
                "tts_enabled": self.speaker.enabled,
                "tts_speaking": self.speaker.busy,
                "tts_queue": self.speaker.pending,
            "volume": round(self.speaker.volume, 2),
            "cpu_pct": round(self._cpu_pct, 1),
            "cpu_total_pct": round(self._cpu_pct / self._cores, 2),
            "cores": self._cores,
            "rss_mb": round(self._rss_mb),
                "wake_mode": self.wake_mode,
                "explicit_listen": self.explicit_listen,
                "watched_sessions": self.watcher.watched,
                "muted_sessions": sorted(
                    n for n in self.watcher.watched if self.is_muted(n)),
                "pid": os.getpid(),
                "updated": time.strftime("%H:%M:%S"),
            })
            tmp = STATE_PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, STATE_PATH)
        except Exception:
            pass

    # ------------------------------------------------------------ boot
    def _install_signal_handlers(self) -> None:
        """pkill/kill ile kapatilinca okuyan sureci de oldur."""
        def handler(signum, _frame):
            try:
                self.speaker.shutdown()
            finally:
                os._exit(0)
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            try:
                signal.signal(sig, handler)
            except Exception:
                pass
        atexit.register(lambda: self.speaker.stop_current(clear_queue=True))

    def _boot(self) -> None:
        n = kill_orphans()                   # onceki calismadan kalan sesler
        if n:
            print(f"[tts] {n} yetim okuma süreci temizlendi")
        self._install_signal_handlers()
        if not ax_trusted():
            ax_request()
            self._set_status("Erişilebilirlik izni bekleniyor")
        self.speaker.start()
        self.watcher.start()
        self.titles.start()               # arka planda baslik indeksi
        threading.Thread(
            target=lambda: setattr(self, "_voices_cache", self.list_voices()),
            daemon=True, name="claudevoice-voices").start()
        if self.cfg.get("ui", "panel_enabled", True):
            if self.panel.start():
                print(f"[panel] {self.panel.url}")
        threading.Thread(target=self._warmup, daemon=True).start()
        threading.Thread(target=self._stt_loop, daemon=True,
                         name="claudevoice-stt").start()

    def _warmup(self) -> None:
        self._set_status("Whisper modeli yükleniyor…")
        if not self.stt.warmup():
            self._set_status(f"Model hatası: {self.stt.load_error}")
            return
        if not self.mic.start():
            self._set_status(f"Mikrofon hatası: {self.mic.error}")
            return
        mode = self.cfg.get("ui", "start_mode", "sleep")
        if mode == "off":
            self._set_state(OFF)
            self._set_status("kapalı — menüden aç")
            return
        # Mikrofonu ac: "mahmut başla" ancak mikrofon acikken duyulabilir.
        self.mic.set_enabled(True)
        if mode == "listen":
            self.explicit_listen = True
            self._set_state(LIVE)
            self._set_status(f'dinliyorum — bitince "tamam {self.call_name}" de')
        else:
            self._set_state(SLEEP)
            self._set_status(f'hazır — "{self.call_name} başla" de')

    # ------------------------------------------------------------ durum
    def _set_status(self, text: str) -> None:
        with self.lock:
            self.status = text

    def _set_state(self, state: str) -> None:
        with self.lock:
            self.state = state

    def _notify(self, title: str, text: str) -> None:
        # Tum macOS bildirimleri tek ayardan kapatilabilir.
        if not self.cfg.get("ui", "notifications", False):
            return
        try:
            rumps.notification(title, "", text)
        except Exception:
            pass

    # ------------------------------------------------------------ menu eylemleri
    def toggle_listen(self, _=None) -> None:
        with self.lock:
            state = self.state
        if state == SLEEP:
            self._wake_up()
            return
        if state == OFF:
            if not self.stt.ready:
                self._set_status("model henüz hazır değil")
                return
            if self.mic._stream is None and not self.mic.start():
                self._set_status(f"Mikrofon hatası: {self.mic.error}")
                return
            self.explicit_listen = False
            self._set_state(ARMED if self.wake_mode else LIVE)
            self.mic.set_enabled(True)
            self._set_status(f'dinliyorum — bitince "tamam {self.call_name}" de')
        else:
            self.mic.set_enabled(False)
            self.explicit_listen = False
            self._set_state(OFF)
            with self.lock:
                self.buffer = ""
            self._set_status("kapalı")

    def toggle_wake(self, _=None) -> None:
        self.wake_mode = not self.wake_mode
        with self.lock:
            if self.state != OFF:
                self.state = ARMED if self.wake_mode else LIVE

    def toggle_tts(self, _=None) -> None:
        """Okuma anahtari — secim KALICI.

        Eskiden yalnizca calisan surecteki bayragi ceviriyordu; uygulama her
        yeniden baslatildiginda config'teki "enabled: true" geri geliyor ve
        kapatilmis okuma kendiliginden aciliyordu.
        """
        on = not self.speaker.enabled
        self.speaker.set_enabled(on)
        self.cfg.set("tts", "enabled", on)
        self._set_status("okuma açık" if on else "okuma kapalı")

    def hush(self, _=None) -> None:
        """Menuden: o anki okumayi VE kuyrugu temizle."""
        self.speaker.stop_current(clear_queue=True)
        self._set_status("okuma kesildi (kuyruk temizlendi)")

    def clear_buffer(self, _=None) -> None:
        with self.lock:
            self.buffer = ""
        self._set_status("tampon temizlendi")

    def send_now(self, _=None) -> None:
        with self.lock:
            text, self.buffer = self.buffer.strip(), ""
        if text:
            self._deliver(text)

    def open_panel(self, _=None) -> None:
        if self.panel.server is None and not self.panel.start():
            self._set_status("panel açılamadı")
            return
        subprocess.Popen(["open", self.panel.url])

    # ------------------------------------------------------- panel API
    def panel_state(self) -> dict:
        """Panelin gosterdigi her sey."""
        with self.lock:
            state, buf, status = self.state, self.buffer, self.status
        sessions = []
        try:
            for sess in self.registry.all():
                sessions.append({"name": sess.name, "routine": sess.routine,
                                 "muted": self.is_muted(sess.name),
                                 "id": sess.session_id})
        except Exception:
            pass
        # Acik konusmalari FAVORI sirasina gore diz; listede olmayanlar sona.
        order = {f.get("id"): i for i, f in enumerate(self.favorites)
                 if f.get("id")}
        names = {f["name"]: i for i, f in enumerate(self.favorites)}
        sessions.sort(key=lambda x: order.get(x.get("id"),
                                              names.get(x["name"], 9999)))
        return {
            "state": state, "buffer": buf, "status": status,
            "speaking": self.speaker.busy, "tts_enabled": self.speaker.enabled,
            "tts_queue": self.speaker.pending,
            "volume": round(self.speaker.volume, 2),
            "cpu_pct": round(self._cpu_pct, 1),
            "cpu_total_pct": round(self._cpu_pct / self._cores, 2),
            "cores": self._cores,
            "rss_mb": round(self._rss_mb),
            "ax": bool(ax_trusted()), "mic_running": self.mic._stream is not None,
            "mic_device": getattr(self.mic, "device_name", ""),
            "mic_rms": round(self.mic.seg.last_rms, 5),
            "last_transcript": self.last_transcript,
            "boot": self._boot_id,
            "capture": {"key": self._capture, "text": self._capture_text},
            "target": self.cfg.get("inject", "target", "claude"),
            "stop_hotkey": self.stop_hotkey,
            "last_received": self._last_received,
            "recv_count": getattr(self, "_recv_count", 0),
            "watching": list(self.watcher.watched),
            "panel_port": self.panel.port,
            "targets": [{"code": k, "label": v["label"],
                         "enabled": bool(v.get("enabled"))}
                        for k, v in TARGETS.items()],
            "paused": self.paused,
            "history": list(self.history),
            "hotkeys": [lbl for _, _, _, lbl in self.hotkeys],
            "sessions": sessions,
            "favorites": [
                {"name": f["name"], "id": f.get("id"),
                 "open": any(s["name"] == f["name"] for s in sessions)}
                for f in self.favorites],
            "canonicals": sorted((self.cfg.get("phrases", "word_variants", {})
                                  or {}).keys()),
            "settings": {
                "name": self.cfg.get("phrases", "name", "mahmut"),
                "language": self.cfg.get("stt", "language") or "auto",
                "voice": self.speaker.voice,
                "voices": self._voices_cache,
                "langpack": self.cfg.get("ui", "langpack", "tr"),
                "custom_count": self._custom_count(),
                "packs": langpacks.available(),
            },
            "commands": ([{"key": k, "label": v,
                           "sample": self._sample(k), "n": self._count(k)}
                          for k, v in self.COMMAND_LABELS]
                         + [{"key": f"hk:{i}", "label": lbl,
                             "sample": self._sample(f"hk:{i}"),
                             "n": self._count(f"hk:{i}")}
                            for i, (_, _, _, lbl) in enumerate(self.hotkeys)]
                         + [{"key": f"fav:{i}",
                             "label": f"{i}. sıra — {f['name']}",
                             "sample": self._sample(f"fav:{i}"),
                             "n": self._count(f"fav:{i}")}
                            for i, f in enumerate(self.favorites, 1)]),
        }

    def panel_action(self, action: str, arg=None) -> None:
        """Paneldeki dugmeler sesli komutlarin AYNISINI calistirir."""
        self._amsg = ""                      # ilgili yerde gosterilecek sonuc
        if action == "cut":
            self.speaker.stop_current(clear_queue=True)
            self._set_status("okuma kesildi")
        elif action == "tts":
            self.toggle_tts()
        elif action == "start":
            self._wake_up()
        elif action == "stop":
            self._go_sleep()
        elif action == "off":
            self.mic.set_enabled(False)
            self.explicit_listen = False
            self._set_state(OFF)
            with self.lock:
                self.buffer = ""
            self._set_status("kapalı")
        elif action == "send":
            self.send_now()
        elif action == "clear":
            self.clear_buffer()
        elif action == "hotkey":
            try:
                hk, _, rep, lbl = self.hotkeys[int(arg)]
            except Exception:
                return
            self._do_hotkey(hk, rep, lbl)
        elif action == "switch" and arg:
            self._do_switch(str(arg))
        elif action == "set_name" and arg:
            ok, msg = self.set_name(str(arg))
            self._amsg = ("✅ " if ok else "🔴 ") + msg
            self._set_status(msg)
        elif action == "load_pack" and arg:
            ok, msg = self.load_langpack(str(arg))
            self._amsg = ("✅ " if ok else "🔴 ") + msg
            self._set_status(msg)
        elif action == "set_panel_port" and arg:
            ok, msg = self.set_panel_port(arg)
            self._amsg = ("✅ " if ok else "🔴 ") + msg
            self._set_status(msg)
        elif action == "set_stop_hotkey" and arg:
            ok, msg = self.set_stop_hotkey(str(arg))
            self._amsg = ("✅ " if ok else "🔴 ") + msg
            self._set_status(msg)
        elif action == "set_target" and arg:
            ok, msg = self.set_target(str(arg))
            self._amsg = ("✅ " if ok else "🔴 ") + msg
            self._set_status(msg)
        elif action == "set_language" and arg is not None:
            ok, msg = self.set_language(str(arg))
            self._amsg = ("✅ " if ok else "🔴 ") + msg
            self._set_status(msg)
        elif action == "set_voice" and arg:
            ok, msg = self.set_voice(str(arg))
            self._amsg = ("✅ " if ok else "🔴 ") + msg
            self._set_status(msg)
        elif action == "variant_add" and arg:
            try:
                canon, words = str(arg).split("|", 1)
            except ValueError:
                return
            added, skipped = [], []
            for w in words.split(","):
                ok, msg = self.add_word_variant(canon, w)
                (added if ok else skipped).append(fold(w.strip()))
            parts = []
            if added:
                parts.append(f"{', '.join(added)} → {fold(canon)}")
            if skipped:
                parts.append(f"{len(skipped)} zaten vardı")
            msg = "; ".join(parts) or "eklenmedi"
            self._amsg = ("✅ " if added else "🔴 ") + msg
            self._set_status(msg)
            print(f"[kelime] {msg}")
        elif action == "words_add" and arg:
            try:
                cmd, phrase = str(arg).split("|", 1)
            except ValueError:
                return
            ok, msg = self.add_words_aligned(cmd, phrase)
            self._amsg = ("✅ " if ok else "🔴 ") + msg
            self._set_status(msg)
            print(f"[kelime] {msg}")
        elif action == "phrase_add" and arg:
            try:
                cmd, phrase = str(arg).split("|", 1)
            except ValueError:
                return
            ok, msg = self.add_command_phrase(cmd, phrase)
            self._amsg = ("✅ " if ok else "🔴 ") + msg
            self._set_status(msg)
            print(f"[kalıp] {msg}")
        elif action == "fav_add" and arg:
            name = str(arg).strip()
            if name and name not in self._fav_names():
                sid = None
                try:
                    hit = find_exact(name, self.registry.all(force=True))
                    sid = hit.session_id if hit else None
                except Exception:
                    pass
                self.favorites.append({"name": name, "id": sid})
                self._save_favorites()
        elif action == "fav_rename" and arg:
            try:
                i, new = str(arg).split("|", 1)
                i = int(i)
            except ValueError:
                return
            new = new.strip()
            if new and 0 <= i < len(self.favorites):
                old_name = self.favorites[i]["name"]
                self.favorites[i]["name"] = new
                # Kimligi sifirla: yeni ad baska bir konusmaya isaret
                # ediyor olabilir, bir sonraki taramada yeniden baglanir.
                self.favorites[i]["id"] = None
                self._save_favorites()
                self._heal_favorites()
                self._set_status(f"{old_name} → {new}")
                print(f"[favori] yeniden adlandırıldı: {old_name!r} → {new!r}")
        elif action == "fav_link" and arg:
            try:
                i, name = str(arg).split("|", 1)
                i = int(i)
            except ValueError:
                return
            try:
                hit = find_exact(name.strip(), self.registry.all(force=True))
            except Exception:
                hit = None
            if hit is not None and 0 <= i < len(self.favorites):
                self.favorites[i] = {"name": hit.name, "id": hit.session_id}
                self._save_favorites()
                self._set_status(f"{i + 1}. sıra → {hit.name}")
        elif action == "fav_remove":
            try:
                i = int(arg)
            except Exception:
                return
            if 0 <= i < len(self.favorites):
                self.favorites.pop(i)
                self._save_favorites()
        elif action == "fav_move":
            try:
                i, d = (int(x) for x in str(arg).split(":"))
            except Exception:
                return
            j = i + d
            if 0 <= i < len(self.favorites) and 0 <= j < len(self.favorites):
                self.favorites[i], self.favorites[j] = (self.favorites[j],
                                                        self.favorites[i])
                self._save_favorites()
        elif action == "fav_select":
            try:
                self._select_favorite(int(arg) + 1)
            except Exception:
                return
        elif action == "list_read":
            self._speak_list()
        elif action == "volume":
            try:
                v = max(0.0, min(float(arg), 1.0))
            except Exception:
                return
            self.speaker.volume = v
            self.cfg.set("tts", "volume", v)      # kalici
            self._set_status(f"ses seviyesi %{int(v * 100)}")
        elif action == "voice_test":
            txt = self.cfg.get("tts", "voice_test_text",
                               "Merhaba, Claude mesajlarını böyle okuyacağım.")
            if arg:                              # panelden gelen ozel metin
                txt = str(arg)[:300]
            was = self.speaker.enabled
            self.speaker.enabled = True          # kapaliysa bile dinletelim
            self.speaker.stop_current(clear_queue=True)
            self.speaker.say(txt)
            if not was:
                threading.Timer(0.3, lambda: None).start()
            self._set_status(f"ses denemesi: {self.speaker.voice}")
        elif action == "pause":
            self.paused = bool(arg) if arg is not None else not self.paused
            if self.paused:
                self.speaker.stop_current(clear_queue=True)
            self._set_status("sistem duraklatıldı" if self.paused
                             else "sistem çalışıyor")
        elif action == "capture_start" and arg:
            self._capture = str(arg)
            self._capture_text = ""
            # Okumayi beklet (kuyruk korunur) ve o anki okumayi kes:
            # okuma surerken mikrofon kisik oldugu icin konusma duyulmuyordu.
            self.speaker.set_hold(True)
            self.speaker.stop_current()
            # Mikrofon KAPALI olsa bile ac ve kisilmisse hemen ac.
            if self.mic._stream is None:
                self.mic.start()
            self.mic.set_enabled(True)
            self.mic.unmute_after(0)
            self._wake_if_asleep()
            self._set_status("konuş — duyduğumu onayına sunacağım")
        elif action == "capture_cancel":
            self._capture = None
            self._capture_text = ""
            self.speaker.set_hold(False)
            self._set_status("yakalama iptal")
        elif action == "capture_commit":
            key, txt = self._capture, self._capture_text
            self.speaker.set_hold(False)
            if key == "__test__":
                self._capture = None; self._capture_text = ""
                return
            self._capture = None
            self._capture_text = ""
            if key and txt:
                ok, msg = self.add_command_phrase(key, txt)
                self._amsg = ("✅ " if ok else "🔴 ") + msg
                self._set_status(msg)
        elif action == "phrase_primary" and arg:
            try:
                k, ph = str(arg).split("|", 1)
            except ValueError:
                return
            ok, msg = self.set_primary(k, ph)
            self._amsg = ("✅ " if ok else "🔴 ") + msg
            self._set_status(msg)
        elif action == "variant_remove" and arg:
            try:
                canon, w = str(arg).split("|", 1)
            except ValueError:
                return
            ok, msg = self.remove_word_variant(canon, w)
            self._amsg = ("✅ " if ok else "🔴 ") + msg
            self._set_status(msg)
        elif action == "phrase_remove" and arg:
            try:
                k, ph = str(arg).split("|", 1)
            except ValueError:
                return
            ok, msg = self.remove_phrase(k, ph)
            self._amsg = ("✅ " if ok else "🔴 ") + msg
            self._set_status(msg)
        elif action == "history_clear":
            n = len(self.history)
            self.history.clear()
            self._set_status(f"kayıt temizlendi ({n})")
        elif action == "mic_refresh":
            name = self.mic.refresh_device(rescan=True)
            self._set_status(f"mikrofon yenilendi: "
                             f"{name or self.mic.device_name}")
        elif action == "mute" and arg:
            self._toggle_mute(str(arg))

    def _rebuild_matcher(self) -> None:
        """Kelime setleri degisince TUM kaliplari yeniden derler.

        Matcher bir kez kuruluyor ve kisayol/liste kaliplari ondan
        tureviyor; biri degisince hepsi yeniden uretilmeli.
        """
        self.matcher = Matcher(self.cfg["phrases"])
        groups_total = 0
        rebuilt = []
        for hk, _, reply, label in self.hotkeys:
            try:
                pats = self.matcher.compile_extra(
                    self._hotkey_phrases.get(id(hk), {}).get(label, []))
            except Exception:
                pats = []
            rebuilt.append((hk, pats, reply, label))
            groups_total += 1
        if all(p for _, p, _, _ in rebuilt):
            self.hotkeys = rebuilt
        self._compile_favorites()
        print(f"[kalıp] yeniden derlendi ({groups_total} kısayol)")

    def add_word_variant(self, canonical: str, word: str) -> tuple[bool, str]:
        """Yanlis duyulan bir yazimi komutun kelime setine ekler."""
        canon = fold(canonical).strip()
        w = fold(word).strip()
        if not canon or len(w) < 2 or " " in w:
            return False, "geçersiz kelime"
        wv = dict(self.cfg.get("phrases", "word_variants", {}) or {})
        cur = list(wv.get(canon, []))
        if w in [fold(x) for x in cur]:
            return False, f"{w!r} zaten {canon!r} setinde"
        cur.append(w)
        wv[canon] = cur
        self.cfg.set("phrases", "word_variants", wv)
        self._rebuild_matcher()
        return True, f"{w!r} → {canon!r} setine eklendi"

    def remove_word_variant(self, canonical: str, word: str) -> tuple[bool, str]:
        """Bir yazimi kelime setinden cikarir.

        Ana kelimenin kendisi cikarilamaz: set o kelimeyi temsil ediyor,
        kaldirilirsa komut hic eslesmez.
        """
        canon = fold(canonical).strip()
        w = fold(word).strip()
        wv = dict(self.cfg.get("phrases", "word_variants", {}) or {})
        cur = list(wv.get(canon, []))
        if not cur:
            return False, f"{canon!r} seti yok"
        if w == canon:
            return False, f"{w!r} ana kelime, kaldırılamaz"
        kept = [x for x in cur if fold(x) != w]
        if len(kept) == len(cur):
            return False, f"{w!r} bu sette yok"
        wv[canon] = kept
        self.cfg.set("phrases", "word_variants", wv)
        self._rebuild_matcher()
        return True, f"{w!r} → {canon!r} setinden kaldırıldı"

    # Panelde gosterilen komut listesi: (config anahtari, okunakli ad)
    COMMAND_LABELS = (
        ("send", "Gönder"),
        ("cut", "Okumayı kes"),
        ("listen", "Dinlemeye başla"),
        ("sleep", "Dinlemeyi durdur"),
        ("list", "Listeyi oku"),
        ("switch", "Konuşma seç"),
        ("reply", "Cevapla"),
        ("cancel", "İptal"),
        ("wake", "Uyandır"),
    )
    COMMAND_KEYS = tuple(k for k, _ in COMMAND_LABELS)

    def _hk_group(self, cmd: str):
        """'hk:1' -> (kisayol_sozlugu, eylem_grubu) ya da None."""
        if not cmd.startswith("hk:"):
            return None
        try:
            i = int(cmd[3:])
            hk_i, grp_i = self._hotkey_ref[i]
        except (ValueError, IndexError):
            return None
        hks = self.cfg.raw("hotkeys", []) or []
        try:
            return hks, hks[hk_i]["actions"][grp_i]
        except (KeyError, IndexError):
            return None

    @staticmethod
    def _fav_index(cmd: str) -> int | None:
        """'fav:3' -> 3, degilse None."""
        if cmd.startswith("fav:"):
            try:
                return int(cmd[4:])
            except ValueError:
                return None
        return None

    def add_words_aligned(self, command: str, phrase: str) -> tuple[bool, str]:
        """Duyulan cumleyi komutun kalibiyla HIZALAYIP farkli kelimeleri
        ilgili yazim setine ekler.

        Ornek: "Mahmut, çeşit" + komut=cut
          kalip  : mahmut | kes
          duyulan: mahmut | cesit
          -> "cesit" kelimesi "kes" setine eklenir ve bundan sonra BASKA
             cumlelerde de tutar.

        Kelime sayisi hicbir kalipla tutmuyorsa hizalama yapilamaz; o
        durumda cumlenin tamamini kalip olarak eklemek gerekir.
        """
        cmd = (command or "").strip()
        idx = self._fav_index(cmd)
        hk = self._hk_group(cmd)
        if idx is None and hk is None and cmd not in self.COMMAND_KEYS:
            return False, f"bilinmeyen komut: {cmd}"
        heard = [w for w, _, _ in tokenize(phrase)]
        if not heard:
            return False, "kelime yok"
        if idx is not None:
            source = self._fav_raw.get(idx, [])
        elif hk is not None:
            source = hk[1].get("phrases", [])
        else:
            source = self.cfg.get("phrases", cmd, []) or []
        canons = [[w for w, _, _ in tokenize(raw)] for raw in source]
        lens = {len(c) for c in canons}

        # Whisper tek kelimeyi ikiye bolebiliyor ("6.yi" -> "6 yi") ya da iki
        # kelimeyi birlestirebiliyor ("tamammahmut"). Duyulan dizi hicbir
        # kalipla ayni uzunlukta degilse komsulari birlestirip/bolup deniyoruz;
        # yoksa "N kelimelik kalip yok" deyip pes ediyordu.
        # Aday diziler HER ZAMAN uretilir: ayni uzunlukta kotu bir kalip
        # (orn. tek kelimelik "over") varken birlestirme denenmezse,
        # "tamammahmut" gibi bir sozcuk "over"in yazimi diye ekleniyordu.
        variants = [heard]
        if len(heard) - 1 in lens:
            for i in range(len(heard) - 1):
                variants.append(heard[:i] + [heard[i] + heard[i + 1]]
                                + heard[i + 2:])
        if len(heard) + 1 in lens:
            for i, w in enumerate(heard):
                if len(w) > 14:
                    continue
                for k in range(2, len(w) - 1):
                    variants.append(heard[:i] + [w[:k], w[k:]]
                                    + heard[i + 1:])

        # Ayni uzunluktaki kaliplar arasindan EN COK kelimesi tutani sec
        best, best_words, best_hit = None, None, -1
        for words in variants:
            for canon in canons:
                if len(canon) != len(words):
                    continue
                hit = sum(1 for h, c in zip(words, canon)
                          if h in (self.matcher._wordsets.get(c, {c})))
                if hit > best_hit:
                    best, best_words, best_hit = canon, words, hit
        if best is None:
            return False, (f"{len(heard)} kelimelik bir kalıp yok — "
                           f"“Cümleyi ekle”yi kullan")
        heard = best_words
        added, already = [], 0
        for h, c in zip(heard, best):
            if h in (self.matcher._wordsets.get(c, {c})):
                already += 1
                continue
            ok, _ = self.add_word_variant(c, h)
            if ok:
                added.append(f"{h}→{c}")
        if not added:
            return True, "zaten tutuyor — bu cümle bu komutu tetikliyor"
        return True, ", ".join(added) + (f" ({already} zaten tutuyordu)"
                                         if already else "")

    def add_command_phrase(self, command: str, phrase: str) -> tuple[bool, str]:
        """Bir cumlenin TAMAMINI komut kalibi olarak ekler.

        Bazen Whisper cumleyi o kadar bozuyor ki kurtaracak kelime
        kalmiyor ("listeyi getir mahmut" -> "Yüce 3 yi ten mamut").
        Boyle durumlarda kelime varyanti yetmez; kalibin kendisi eklenir.
        """
        cmd = (command or "").strip()
        idx = self._fav_index(cmd)
        hk = self._hk_group(cmd)
        if idx is None and hk is None and cmd not in self.COMMAND_KEYS:
            return False, f"bilinmeyen komut: {cmd}"
        norm = " ".join(w for w, _, _ in tokenize(phrase))
        if len(norm.split()) < 2:
            return False, "en az iki kelime gerekli"
        if hk is not None:                       # uygulama kisayolu
            hks, grp = hk
            cur = list(grp.get("phrases", []) or [])
            if norm in [" ".join(w for w, _, _ in tokenize(x)) for x in cur]:
                return False, f"{norm!r} zaten bu kısayolda"
            cur.append(norm)
            grp["phrases"] = cur
            self.cfg.set_raw("hotkeys", hks)
            self._rebuild_matcher()
            return True, f"{norm!r} → {grp.get('label', 'kısayol')} eklendi"
        if idx is not None:                      # sira secimi
            extra = dict(self.cfg.get("phrases", "fav_select", {}) or {})
            cur = list(extra.get(str(idx), []) or [])
            if norm in cur:
                return False, f"{norm!r} zaten {idx}. sıra kalıplarında"
            cur.append(norm)
            extra[str(idx)] = cur
            self.cfg.set("phrases", "fav_select", extra)
            self._rebuild_matcher()
            return True, f"{norm!r} → {idx}. sıra seçimine eklendi"
        cur = list(self.cfg.get("phrases", cmd, []) or [])
        if norm in [" ".join(w for w, _, _ in tokenize(x)) for x in cur]:
            return False, f"{norm!r} zaten {cmd!r} kalıplarında"
        cur.append(norm)
        self.cfg.set("phrases", cmd, cur)
        self._rebuild_matcher()
        return True, f"{norm!r} → {cmd!r} komutuna eklendi"

    # ---------------------------------------------------- ayarlar
    PHRASE_LISTS = ("send", "cut", "listen", "sleep", "reply", "switch",
                    "cancel", "list", "wake")

    def _custom_count(self) -> int:
        """Kullanicinin dil paketine EKLEDIGI kalip/yazim sayisi.

        Sifirsa panel bir bilgilendirme gosterir: kullanici henuz kendi
        yanlis duymalarini eklememistir ve komutlar sik sik kacacaktir.
        """
        code = self.cfg.get("ui", "langpack", "tr")
        pack = langpacks.build(code, self.cfg.get("phrases", "name", "mahmut"))
        if pack is None:
            return 0
        n = 0
        for key, base in pack["phrases"].items():
            cur = self.cfg.get("phrases", key, []) or []
            n += max(0, len(cur) - len(base))
        wv = self.cfg.get("phrases", "word_variants", {}) or {}
        for k, v in wv.items():
            n += max(0, len(v) - len(pack["word_variants"].get(k, [k])))
        for v in (self.cfg.get("phrases", "fav_select", {}) or {}).values():
            n += len(v or [])
        return n

    def _phrases_of(self, key: str) -> list[str]:
        idx = self._fav_index(key)
        if idx is not None:
            return list(self._fav_raw.get(idx, []))
        hk = self._hk_group(key)
        if hk is not None:
            return list(hk[1].get("phrases", []) or [])
        if key in self.COMMAND_KEYS:
            return list(self.cfg.get("phrases", key, []) or [])
        return []

    def _sample(self, key: str) -> str:
        ph = self._phrases_of(key)
        return ph[0] if ph else ""

    def _count(self, key: str) -> int:
        return len(self._phrases_of(key))

    def set_primary(self, key: str, phrase: str) -> tuple[bool, str]:
        """Bir kalibi listenin BASINA alir (panelde ornek olarak gorunur).

        Kalip yoksa once eklenir.
        """
        norm = " ".join(w for w, _, _ in tokenize(phrase))
        if len(norm.split()) < 2:
            return False, "en az iki kelime gerekli"
        idx = self._fav_index(key)
        hk = self._hk_group(key)
        if idx is not None:
            extra = dict(self.cfg.get("phrases", "fav_select", {}) or {})
            cur = [x for x in (extra.get(str(idx), []) or []) if x != norm]
            extra[str(idx)] = [norm] + cur
            self.cfg.set("phrases", "fav_select", extra)
        elif hk is not None:
            hks, grp = hk
            cur = [x for x in (grp.get("phrases", []) or []) if x != norm]
            grp["phrases"] = [norm] + cur
            self.cfg.set_raw("hotkeys", hks)
        elif key in self.COMMAND_KEYS:
            cur = [x for x in (self.cfg.get("phrases", key, []) or [])
                   if " ".join(w for w, _, _ in tokenize(x)) != norm]
            self.cfg.set("phrases", key, [norm] + cur)
        else:
            return False, "bilinmeyen komut"
        self._rebuild_matcher()
        return True, f"{norm!r} örnek kalıp oldu"

    def command_detail(self, key: str) -> dict:
        """Bir komutun kaliplarini ve ilgili yazim setlerini dondurur."""
        key = (key or "").strip()
        idx = self._fav_index(key)
        hk = self._hk_group(key)
        if idx is not None:
            phrases = list(self._fav_raw.get(idx, []))
            extra = (self.cfg.get("phrases", "fav_select", {}) or {})
            editable = list(extra.get(str(idx), []) or [])
            label = f"{idx}. sıra"
        elif hk is not None:
            phrases = list(hk[1].get("phrases", []) or [])
            editable = phrases
            label = hk[1].get("label") or "kısayol"
        elif key in self.COMMAND_KEYS:
            phrases = list(self.cfg.get("phrases", key, []) or [])
            editable = phrases
            label = dict(self.COMMAND_LABELS).get(key, key)
        else:
            return {"error": f"bilinmeyen komut: {key}"}
        # Kaliplarda gecen kelimelerin yazim setleri
        wv = self.cfg.get("phrases", "word_variants", {}) or {}
        used = set()
        for ph in phrases:
            for w, _, _ in tokenize(ph):
                if w in wv:
                    used.add(w)
        return {
            "key": key, "label": label,
            "phrases": phrases, "editable": editable,
            "variants": {w: _uniq(wv[w]) for w in sorted(used)},
        }

    def remove_phrase(self, key: str, phrase: str) -> tuple[bool, str]:
        """Bir kalibi komuttan cikarir."""
        key = (key or "").strip()
        idx = self._fav_index(key)
        hk = self._hk_group(key)
        norm = " ".join(w for w, _, _ in tokenize(phrase))
        if idx is not None:
            extra = dict(self.cfg.get("phrases", "fav_select", {}) or {})
            cur = [x for x in (extra.get(str(idx), []) or [])
                   if " ".join(w for w, _, _ in tokenize(x)) != norm]
            extra[str(idx)] = cur
            self.cfg.set("phrases", "fav_select", extra)
        elif hk is not None:
            hks, grp = hk
            grp["phrases"] = [x for x in (grp.get("phrases", []) or [])
                              if " ".join(w for w, _, _ in tokenize(x)) != norm]
            self.cfg.set_raw("hotkeys", hks)
        elif key in self.COMMAND_KEYS:
            cur = [x for x in (self.cfg.get("phrases", key, []) or [])
                   if " ".join(w for w, _, _ in tokenize(x)) != norm]
            self.cfg.set("phrases", key, cur)
        else:
            return False, "bilinmeyen komut"
        self._rebuild_matcher()
        return True, f"{norm!r} kaldırıldı"

    def classify(self, text: str) -> dict:
        """Bu metin hangi komutu tetiklerdi? (CALISTIRMADAN soyler)"""
        m = self.matcher
        if m.is_cut(text):
            return {"cmd": "cut", "label": "✂️ Okumayı kes"}
        if m.is_listen(text):
            return {"cmd": "listen", "label": "▶ Dinlemeye başla"}
        if m.is_sleep(text):
            return {"cmd": "sleep", "label": "⏸ Dinlemeyi durdur"}
        for idx, pats in getattr(self, "fav_patterns", []):
            if m.find_tail(text, pats)[0]:
                nm = self.favorites[idx - 1]["name"] if idx <= len(self.favorites) else ""
                return {"cmd": f"fav:{idx}", "label": f"#{idx} seç — {nm}"}
        if m.is_list(text):
            return {"cmd": "list", "label": "📋 Listeyi oku"}
        for i, (hk, pats, _, lbl) in enumerate(self.hotkeys):
            if m.find_tail(text, pats)[0]:
                return {"cmd": f"hk:{i}", "label": f"🎛 {lbl}"}
        if m.is_cancel(text):
            return {"cmd": "cancel", "label": "🗑 İptal"}
        if m.find_reply(text)[0]:
            return {"cmd": "reply", "label": "↩︎ Cevapla"}
        ok, name = m.find_switch(text)
        if ok:
            return {"cmd": "switch", "label": f"⇄ Konuşma seç — {name!r}"}
        ok, payload = m.find_send(text)
        if ok:
            return {"cmd": "send", "label": f"📨 Gönder — {payload!r}"}
        if m.find_wake(text) is not None:
            return {"cmd": "wake", "label": "🎙 Uyandır"}
        return {"cmd": None, "label": "— komut değil, tampona eklenir"}

    def set_name(self, new: str) -> tuple[bool, str]:
        """Cagri adini degistirir ve TUM kaliplari yeni ada tasir."""
        new_f = fold(new).strip()
        if not new_f or " " in new_f or len(new_f) < 3:
            return False, "ad en az 3 harf, tek kelime olmalı"
        old_f = fold(self.cfg.get("phrases", "name", "mahmut"))
        if new_f == old_f:
            return False, "ad zaten bu"

        def swap(items):
            out = []
            for raw in items or []:
                words = [w for w, _, _ in tokenize(raw)]
                out.append(" ".join(new_f if w == old_f else w for w in words))
            return out

        for key in self.PHRASE_LISTS:
            self.cfg.set("phrases", key, swap(self.cfg.get("phrases", key, [])))
        # kelime setleri: eski adin yazimlari yeni ad icin gecersiz
        wv = dict(self.cfg.get("phrases", "word_variants", {}) or {})
        wv.pop(old_f, None)
        wv[new_f] = [new_f]
        self.cfg.set("phrases", "word_variants", wv)
        # kisayol kaliplari
        hks = self.cfg.raw("hotkeys", []) or []
        for hk in hks:
            for grp in hk.get("actions", []) or []:
                grp["phrases"] = swap(grp.get("phrases", []))
            if "phrases" in hk:
                hk["phrases"] = swap(hk["phrases"])
        self.cfg.set_raw("hotkeys", hks)
        # sira secimi ekstralari
        extra = dict(self.cfg.get("phrases", "fav_select", {}) or {})
        self.cfg.set("phrases", "fav_select",
                     {k: swap(v) for k, v in extra.items()})
        self.cfg.set("phrases", "name", new_f)
        self.call_name = new_f.capitalize()
        self._rebuild_matcher()
        print(f"[ayar] çağrı adı: {old_f!r} → {new_f!r}")
        return True, (f"çağrı adı “{self.call_name}” oldu — "
                      f"yazım setini yeniden oluşturman gerekebilir")

    def load_langpack(self, code: str) -> tuple[bool, str]:
        """Bir dil paketini yukler: komut kaliplari, yazim setleri, sesli
        metinler ve sira sozcukleri.

        Kullanicinin FAVORILERI, kisayollari ve cagri adi korunur; sadece
        kalip/metin tarafi varsayilana doner. "Varsayilana don" islevi de
        budur: ayni paketi yeniden yuklemek yeter.
        """
        name = self.cfg.get("phrases", "name", "mahmut")
        pack = langpacks.build(code, name)
        if pack is None:
            return False, f"bilinmeyen dil paketi: {code}"
        for key, items in pack["phrases"].items():
            self.cfg.set("phrases", key, list(items))
        self.cfg.set("phrases", "word_variants",
                     {k: list(v) for k, v in pack["word_variants"].items()})
        self.cfg.set("phrases", "fav_select", {})     # ekstralar sifirlanir
        for key, val in pack["tts"].items():
            self.cfg.set("tts", key, val)
        self.cfg.set("ui", "langpack", code)
        if pack.get("voice_hint"):
            names = {v["name"] for v in (self._voices_cache or [])}
            if pack["voice_hint"] in names:
                self.speaker.voice = pack["voice_hint"]
                self.cfg.set("tts", "voice", pack["voice_hint"])
        self._pack = pack
        self._rebuild_matcher()
        print(f"[dil] {code!r} paketi yüklendi")
        return True, f"{pack['label']} komut seti yüklendi"

    def _ordinals(self) -> tuple[list, list, list, list, tuple]:
        p = getattr(self, "_pack", None) or langpacks.PACKS.get(
            self.cfg.get("ui", "langpack", "tr"), langpacks.PACKS["tr"])
        return (p["ordinals"], p["ordinals_acc"], p["numbers"],
                p["numbers_acc"], p["select_verbs"])

    def set_target(self, code: str) -> tuple[bool, str]:
        """Mesajin gonderilecegi uygulamayi secer.

        Okuma (cevaplarin seslendirilmesi) yalnizca Claude Code'da calisir:
        transkript JSONL dosyalarini oradan okuyoruz. Codex'te yazma/gonderme
        calisir, okuma icin kaynak yok.
        """
        code = (code or "").strip().lower()
        t = TARGETS.get(code)
        if not t:
            return False, f"bilinmeyen hedef: {code}"
        if not t.get("enabled"):
            return False, f"{t['label']} henüz hazır değil"
        self.cfg.set("inject", "target", code)
        self.cfg.set("inject", "bundle_id", t["bundle_id"])
        self.injector.bundle_id = t["bundle_id"]
        return True, f"hedef uygulama: {t['label']}"

    def set_language(self, lang: str) -> tuple[bool, str]:
        lang = (lang or "").strip().lower()
        if lang in ("", "auto", "oto"):
            self.stt.language = None
            self.cfg.set("stt", "language", None)
            return True, "dil: otomatik algıla"
        if not (2 <= len(lang) <= 5):
            return False, "geçersiz dil kodu"
        self.stt.language = lang
        self.cfg.set("stt", "language", lang)
        return True, f"dil: {lang}"

    def set_voice(self, voice: str) -> tuple[bool, str]:
        voice = (voice or "").strip()
        if not voice:
            return False, "ses seçilmedi"
        self.speaker.voice = voice
        self.cfg.set("tts", "voice", voice)
        return True, f"ses: {voice}"

    @staticmethod
    def list_voices() -> list[dict]:
        """`say -v '?'` ciktisini ayristirir."""
        try:
            out = subprocess.run(["say", "-v", "?"], capture_output=True,
                                 text=True, timeout=10).stdout
        except Exception:
            return []
        seen, voices = set(), []
        for line in out.splitlines():
            # "Yelda (Turkish (Türkiye)) tr_TR    # ..." — ic ice parantez
            # var ve dil kodundan once TEK bosluk olabiliyor; eski desen
            # iki+ bosluk bekledigi icin Yelda listeye hic girmiyordu.
            m = re.match(r"^(.+?)\s+([a-z]{2}[-_][A-Za-z]{2,})\s+#", line)
            if not m:
                continue
            name = m.group(1).strip()
            name = re.sub(r"\s*\(.*\)$", "", name).strip()
            key = (name, m.group(2))
            if key in seen:
                continue
            seen.add(key)
            voices.append({"name": name, "lang": m.group(2)})
        return voices

    def _save_favorites(self) -> None:
        self.cfg.set("ui", "favorites",
                     [{"name": f["name"], "id": f.get("id")}
                      for f in self.favorites])
        self._compile_favorites()

    def open_config(self, _=None) -> None:
        if not os.path.exists(CONFIG_PATH):
            self.cfg.write_default()
        subprocess.Popen(["open", "-t", CONFIG_PATH])

    def quit_app(self, _=None) -> None:
        try:                              # tek kopya kilidini birak
            os.remove(os.path.join(os.path.dirname(CONFIG_PATH), ".app.lock"))
        except Exception:
            pass
        self.mic.set_enabled(False)
        self.mic.stop()
        self.watcher.stop()
        self.panel.stop()
        self.speaker.shutdown()
        rumps.quit_application()

    # ------------------------------------------------------------ TTS kopru
    def _is_own_voice(self, text: str) -> bool:
        """Duyulan metin, o an okunan metnin KENDISI mi (hoparlor yankisi)?

        Yanki, okunan cumlenin bir parcasini AYNI SIRAYLA tasir. Sadece
        "kelimelerin cogu geciyor" demek yetmiyordu: okunan metinde "mahmut"
        ve "kes" ayri ayri gecerse kullanicinin gercek "mahmut kes" komutu da
        yanki sayilip yok ediliyordu. Bu yuzden ARDISIK alt dizi araniyor;
        boylece hoparlorle de calisir, mikrofonu kapatmaya gerek kalmaz.
        """
        # Son ses parcasi, okuma bittikten ~1 sn sonra yaziya cevriliyor;
        # o anda speaker.busy artik False oluyordu ve yanki tam korumasiz
        # geciyordu (kendi okudugumuz "tamam mahmut" mesaji gonderdi).
        spoken = self.speaker.recent_text()
        if not spoken:
            return False
        heard = [w for w, _, _ in tokenize(text)]
        pool = [w for w, _, _ in tokenize(spoken)]
        if not heard or not pool:
            return False
        if len(heard) == 1:               # tek kelime: gecmesi yeterli
            return any(word_eq(heard[0], p) for p in pool)
        n = len(heard)
        for i in range(len(pool) - n + 1):
            if all(word_eq(h, p) for h, p in zip(heard, pool[i:i + n])):
                return True
        return False

    def _tts_started(self, meta=None) -> None:
        # Okunmakta olan mesajin oturumu: "cevap mahmut" bunu hedef alir.
        if meta:
            self._last_heard = str(meta)
        if self._capture:
            return                       # yakalama acikken mikrofon kisilmaz
        if self._duck_now():
            self.mic.mute_for(3600)      # okuma bitene kadar mikrofonu kapat

    def _tts_ended(self) -> None:
        self.mic.unmute_after(self.cfg.get("tts", "mic_cooldown_ms", 400) / 1000)

    def _duck_now(self) -> bool:
        """Okuma sirasinda mikrofon kapatilsin mi?

        "auto" (varsayilan): SADECE ses mikrofonun duyabilecegi bir cikistan
        caliyorsa kapatilir. Kulaklikta mikrofon acik kalir, boylece okuma
        surerken "mahmut kes" calismaya devam eder.
        """
        mode = self.cfg.get("tts", "duck_mic_while_speaking", "auto")
        if isinstance(mode, str) and mode.lower() == "auto":
            # Mikrofon KAPATILMAZ: hoparlorle calisirken de konusabilmek
            # gerekiyor. Kendi sesimiz metin duzeyinde ayikliyor
            # (_is_own_voice). true dersen klasik kisma geri gelir.
            return False
        return bool(mode)

    def _announce_prefix(self, session_name: str) -> str:
        """Icerikten ONCE, AYRI bir cumle olarak okunan anons.

        Ayri `say` cagrisi oldugu icin araya dogal bir duraklama girer ve
        "... mesajini okuyorum." cumlesi icerikle birbirine karismaz.
        """
        mode = self.cfg.get("tts", "announce_session", "always")
        if mode == "never" or not session_name:
            return ""
        if mode == "on_change" and session_name == self._last_announced:
            return ""
        self._last_announced = session_name
        tpl = self.cfg.get("tts", "announce_template",
                           "{name} mesajını okuyorum.")
        return tpl.format(name=session_name)

    def _on_assistant_text(self, session_name: str, markdown: str) -> None:
        spoken = to_speech(
            markdown,
            code_placeholder=self.cfg.get("tts", "say_code_placeholder", "kod bloğu"),
            max_chars=int(self.cfg.get("tts", "max_chars", 1200)),
        )
        self._last_received = session_name
        self._recv_count = getattr(self, "_recv_count", 0) + 1
        # Takipci gercekten metin getiriyor mu, loga bak: sorun cikinca
        # "okundu mu / hic gelmedi mi" ayrimini yapacak tek iz buydu.
        print(f"[oku] {session_name}: {len(markdown)} karakter "
              f"-> {len(spoken)} okunacak")
        if not spoken:
            return
        # Kuyruk tek tek okudugu icin paralel gelen mesajlar sirasini bekler.
        self.speaker.say(spoken, meta=session_name,
                         prefix=self._announce_prefix(session_name))

    # ------------------------------------------------------------ STT dongusu
    def _stt_loop(self) -> None:
        while True:
            audio = self.audio_q.get()
            with self.lock:
                # Yakalama aciksa mikrofon kapali durumda bile isle:
                # kullanici panelden "dinle ve ekle" demis oluyor.
                if self.state == OFF and not self._capture:
                    continue
            text = self.stt.transcribe(audio, self.mic.sr)
            if not text:
                continue
            text = self.glossary.correct(text)
            self.last_transcript = text          # hata ayiklama icin
            self._last_action = ""
            self._handle_text(text)
            self.history.appendleft({
                "t": time.strftime("%H:%M:%S"),
                "text": text,
                "result": self._last_action,
                "fired": bool(self._last_action
                              and not self._last_action.startswith(("—", "…"))),
            })

    def _handle_text(self, text: str) -> None:
        # Sistem duraklatilmissa hicbir komut islenmez, tampona da yazilmaz.
        if self.paused and not self._capture:
            self._last_action = "⏸ duraklatıldı"
            return

        # Panelden "dinle ve ekle" aciksa: duyulani KOMUT OLARAK ISLEME,
        # onay icin beklet.
        if self._capture:
            self._capture_text = text
            print(f"[yakala] {self._capture} <- {text!r}", flush=True)
            self._last_action = "🎙 yakalandı"
            self._set_status(f"yakalandı: {text}")
            return

        # 0a) Okuma surerken duyulan sey okunan metnin kendisiyse (hoparlor
        # yankisi) hicbir komut calistirilmaz: okunan cumlede "mahmut" ve
        # "kes" gecerse uygulama kendi kendini kesiyordu.
        if self._is_own_voice(text):
            self._last_action = "🔇 kendi sesi"
            return

        # 0) Okumayi kesme / uyku komutlari her durumdan calisir.
        if self.matcher.is_cut(text):
            self._last_action = "✂️ KES"
            # Kuyrugu DA temizle: bir cevap birden cok metin blogu olarak
            # gelebiliyor, sadece o anki blogu durdurmak hic kesilmemis gibi
            # duyuluyordu (hemen sonraki blok basliyordu).
            self.speaker.stop_current(clear_queue=True)
            self._set_status("okuma kesildi")
            return
        if self.matcher.is_listen(text):
            self._last_action = "▶ BAŞLA"
            self._wake_up()
            return
        if self.matcher.is_sleep(text):
            self._last_action = "⏸ DUR"
            self._go_sleep()
            return
        # SIRA SECIMI once: "ikinciyi getir mahmut" hem sira secimine hem
        # liste kuralina (ad + "getir") uyuyor. Daha ozgul olan kazanmali.
        for idx, pats in getattr(self, "fav_patterns", []):
            if self.matcher.find_tail(text, pats)[0]:
                self._last_action = f"#{idx} SEÇ"
                self._select_favorite(idx)
                return
        if self.matcher.is_list(text):
            self._last_action = "📋 LİSTE"
            self._speak_list()
            return

        # Uygulama kisayollari da bir KONTROL komutudur: "mahmut dur"
        # durumundayken bile calisir (dikte degil, tek seferlik eylem).
        for hk, pats, reply, label in self.hotkeys:
            if self.matcher.find_tail(text, pats)[0]:
                self._last_action = f"🎛 {label}"
                self._do_hotkey(hk, reply, label)
                return

        # Okuma devam ederken mikrofon aciksa, duyulan sey buyuk ihtimalle
        # Claude'un kendi sesidir. Yukaridaki komutlar disinda hicbir sey
        # islenmez; boylece okunan metin yanlislikla mesaj olarak gitmez.
        if self.speaker.busy:
            self._last_action = "— okuma sürüyor"
            return

        with self.lock:
            state = self.state
        if state == SLEEP:
            # Durdurulmusken de konusma tamponda BIRIKIR ama hicbir sey
            # yapilmaz. Tek istisna gonderme: "tamam mahmut" denirse hem
            # uyanir hem birikeni gonderir — kullanici zaten mesaj yollamak
            # istedigini soylemis oluyor.
            with self.lock:
                cand = f"{self.buffer} {text}".strip()
            done, payload = self.matcher.find_send(cand)
            if not done:
                with self.lock:
                    self.buffer = cand
                self._buffer_at = time.monotonic()
                self._last_action = "— durduruldu (tamponda)"
                return
            self._wake_if_asleep()
            with self.lock:
                self.buffer = ""
            self._last_action = "📨 GÖNDER"
            if payload:
                self._deliver(payload)
            else:
                self._set_status("gönderilecek bir şey yoktu")
            return

        # "hey mahmut" beklenirken: uyandirma kelimesi gecmeyen her sey yok sayilir
        if state == ARMED:
            rest = self.matcher.find_wake(text)
            if rest is None:
                self._last_action = "— uyandırma bekleniyor"
                return
            self._set_state(LIVE)
            self._set_status("dinliyorum…")
            text = rest
            if not text:
                return

        if self.matcher.is_cancel(text):
            self._last_action = "🗑 İPTAL"
            self._reset_buffer()
            self._set_status("iptal edildi")
            return

        with self.lock:
            candidate = f"{self.buffer} {text}".strip()

        # 1) Uygulama kisayollari:  "mahmut mikrofon aç"
        for hk, pats, reply, label in self.hotkeys:
            hit, before = self.matcher.find_tail(candidate, pats)
            if hit:
                self._last_action = f"🎛 {label}"
                with self.lock:
                    self.buffer = before       # dikte edilen metni koru
                self._do_hotkey(hk, reply, label)
                return

        # 2) Cevap hedefi:  "cevap mahmut"
        is_reply, before = self.matcher.find_reply(candidate)
        if is_reply:
            self._last_action = "↩︎ CEVAP"
            with self.lock:
                self.buffer = before          # dikteye devam edilir
            self._arm_reply()
            return

        # 3) Konusma degistirme:  "<ad> seç mahmut"
        is_switch, name = self.matcher.find_switch(candidate)
        if is_switch:
            self._last_action = "⇄ GEÇİŞ"
            self._reset_buffer()
            self._do_switch(name)
            return

        # 3) Gonderme:  "... tamam claude"
        done, payload = self.matcher.find_send(candidate)
        if not done:
            self._last_action = "… tampona eklendi"
            with self.lock:
                self.buffer = candidate
            self._buffer_at = time.monotonic()
            self._set_status("dinliyorum…")
            return

        self._last_action = "📨 GÖNDER"
        self._reset_buffer()
        if payload:
            self._deliver(payload)
        else:
            self._set_status("gönderilecek bir şey yoktu")

    def _reset_buffer(self) -> None:
        with self.lock:
            self.buffer = ""
            if self.explicit_listen:
                self.state = LIVE          # "beni dinle" dendi, dinlemeye devam
            else:
                self.state = ARMED if self.wake_mode else LIVE

    # ------------------------------------------------------------ eylemler
    def _wake_up(self) -> None:
        """"mahmut başla" — durdurulmussa da kapaliyken de aktif dinlemeye gecer."""
        with self.lock:
            already = self.state == LIVE and self.explicit_listen
        if already:
            # Zaten dinliyoruz: tamponu BOZMA, sadece teyit et.
            self._set_status("zaten dinliyorum")
            if self.speaker.enabled:
                self.speaker.say(self.cfg.get(
                    "tts", "already_listening_reply", "Zaten açığım, dinliyorum."))
            return
        if self.mic._stream is None and not self.mic.start():
            self._set_status(f"Mikrofon hatası: {self.mic.error}")
            return
        self.mic.set_enabled(True)
        self.explicit_listen = True
        with self.lock:
            self.buffer = ""
            self.state = LIVE
        self._set_status(f'dinliyorum — bitince "tamam {self.call_name}" de')
        if self.speaker.enabled:
            self.speaker.say(self.cfg.get("tts", "listen_reply", "Dinliyorum."))

    def _go_sleep(self) -> None:
        """"mahmut dur" — mikrofon acik kalir ama sadece uyandirma dinlenir."""
        with self.lock:
            already = self.state == SLEEP
        if already:
            self._set_status("zaten durmuştum")
            if self.speaker.enabled:
                self.speaker.say(self.cfg.get(
                    "tts", "already_stopped_reply", "Zaten durmuştum."))
            return
        self.explicit_listen = False
        with self.lock:
            self.buffer = ""
            self.state = SLEEP
        self._set_status(f'durduruldu — "{self.call_name} başla" ile aç')
        if self.speaker.enabled:
            self.speaker.say(self.cfg.get("tts", "sleep_reply", "Tamam, tatildeyim."))

    # ------------------------------------------------- numarali liste
    def _load_favorites(self) -> list[dict]:
        """Favorileri {ad, kimlik} bicimine cevirir.

        Sadece ADI saklamak kirilgan: konusma yeniden adlandirilinca favori
        tutmuyor ve "kapali" gorunuyor. Oturum KIMLIGI degismedigi icin
        onu da sakliyoruz; ad degisirse kendiliginden guncelleniyor.
        """
        out: list[dict] = []
        for item in (self.cfg.get("ui", "favorites", []) or []):
            if isinstance(item, dict):
                out.append({"name": str(item.get("name", "")).strip(),
                            "id": item.get("id") or None})
            elif str(item).strip():
                out.append({"name": str(item).strip(), "id": None})
        return [f for f in out if f["name"] or f["id"]]

    def _fav_names(self) -> list[str]:
        return [f["name"] for f in self.favorites]

    def _heal_favorites(self) -> None:
        """Eksik kimlikleri doldurur, degisen adlari gunceller."""
        try:
            sessions = self.registry.all()
        except Exception:
            return
        by_id = {s.session_id: s for s in sessions}
        changed = False
        for f in self.favorites:
            if f.get("id"):
                live = by_id.get(f["id"])
                if live is not None and live.name and live.name != f["name"]:
                    print(f"[favori] ad güncellendi: {f['name']!r} → {live.name!r}")
                    f["name"] = live.name
                    changed = True
                continue
            # kimlik yok: once acik oturumlardan, sonra baslik indeksinden
            hit = find_exact(f["name"], sessions)
            if hit is not None:
                f["id"] = hit.session_id
                changed = True
                continue
            sid = self.titles.find(f["name"]) if self.titles.ready else None
            if sid:
                f["id"] = sid
                changed = True
        if changed:
            self._save_favorites()

    def _compile_favorites(self) -> None:
        """Her sira numarasi icin sesli secim kaliplarini uretir.

        "birinci sec mahmut", "bir sec mahmut", "1 sec mahmut",
        "birinci mahmut", "birinci numara mahmut" — hepsi ayni seyi yapar.
        """
        self.fav_patterns = []
        self._fav_raw: dict[int, list[str]] = {}
        n = self.cfg.get("phrases", "name", "mahmut")
        ORD, ORD_A, NUM, NUM_A, VERBS = self._ordinals()
        for i in range(1, min(len(self.favorites), len(ORD) - 1) + 1):
            o, w = ORD[i], NUM[i]
            oa = ORD_A[i] if i < len(ORD_A) else o
            wa = NUM_A[i] if i < len(NUM_A) else w
            raw = []
            # "sec" disinda "getir" ve "ac" da kullaniliyor:
            # "ikinciyi getir mahmut" liste komutuna benziyordu.
            verbs = VERBS
            for form in (o, oa):              # "birinci" ve "birinciyi"
                for v in verbs:
                    raw += [f"{form} {v} {n}", f"{n} {form} {v}", f"{n} {v} {form}"]
                raw += [f"{form} {n}", f"{n} {form}", f"{form} numara {n}",
                        f"{form} konusma {n}", f"{form} sohbet {n}"]
            for form in (w, wa):              # "bir" ve "biri"
                for v in verbs:
                    raw += [f"{form} {v} {n}", f"{n} {form} {v}"]
            raw += [f"{i} sec {n}", f"{n} {i} sec"]
            # Panelden eklenen ekstra kaliplar
            extra = (self.cfg.get("phrases", "fav_select", {}) or {})
            raw += list(extra.get(str(i), []) or [])
            self._fav_raw[i] = raw
            try:
                pats = self.matcher.compile_extra(raw)
            except Exception as exc:
                print(f"[liste] {i}. kalıp derlenemedi: {exc!r}")
                continue
            if pats:
                self.fav_patterns.append((i, pats))
        print(f"[liste] {len(self.favorites)} favori, "
              f"{len(self.fav_patterns)} sıra kalıbı")

    def _speak_list(self) -> None:
        """Listeyi numaralandirarak sesli okur."""
        g = lambda k, d: self.cfg.get("tts", k, d) or d
        if not self.favorites:
            self._set_status("liste boş")
            if self.speaker.enabled:
                self.speaker.say(g("list_empty", "Liste boş."))
            return
        try:
            acik = {s.name for s in self.registry.all(force=True)}
        except Exception:
            acik = set()
        item_tpl = g("list_item", "{no} {name}")
        closed = g("list_closed_suffix", ", kapalı")
        parts = [g("list_lead", "Listeyi okuyorum.")]
        for i, name in enumerate(self._fav_names(), 1):
            NUM = self._ordinals()[2]
            no = NUM[i] if i < len(NUM) else str(i)
            parts.append(item_tpl.format(no=no, name=name)
                         + ("" if name in acik else closed))
        self._set_status(f"liste okunuyor ({len(self.favorites)} konuşma)")
        if self.speaker.enabled:
            # say_parts: aralara GERCEK sessizlik koyar. Noktalama ile
            # dogru duraklama elde edilemiyor (olculdu).
            self.speaker.say_parts(parts, pause=float(
                self.cfg.get("tts", "list_pause_sec", 0.35)))

    def _select_favorite(self, index: int) -> None:
        """Listedeki n'inci konusmaya gecer; kapaliysa ONCE acar."""
        if not (1 <= index <= len(self.favorites)):
            self._set_status(f"listede {index}. sıra yok")
            return
        fav = self.favorites[index - 1]
        name, fid = fav.get("name", ""), fav.get("id")
        try:
            sessions = self.registry.all(force=True)
        except Exception:
            sessions = []
        # 1) KIMLIK: ad degisse bile tutar
        session = next((x for x in sessions if x.session_id == fid), None)
        # 2) birebir ad (bulanik eslestirme "Portal" icin "Pam"i seciyordu)
        if session is None:
            session = find_exact(name, sessions)
        if session is None:
            from .sessions import match as _match
            session, _, _ = _match(name, sessions, threshold=0.85)
        if session is not None:
            if session.name and session.name != name:
                fav["name"] = session.name        # ad degismisse guncelle
                self._save_favorites()
            if not fid:
                fav["id"] = session.session_id
                self._save_favorites()
            self._switch_and_announce(session)
            return
        # Kapali: transcript indeksinden kimligi bul, resume deep link'i ile
        # ac, listede belirmesini bekle. Acilma ~10 sn surdugu icin bu is
        # AYRI bir is parcaciginda yapilir, yoksa ses isleme bloklanir.
        sid = fid or self.titles.find(name)
        if not sid:
            self._set_status(f"{name} bulunamadı")
            self._say_tpl("not_found_reply", "{name} bulunamadı.", name)
            return
        self._set_status(f"{name} kapalı, açılıyor…")
        self._say_tpl("resume_opening", "{name} kapalı, açıyorum.", name)
        threading.Thread(target=self._resume_then_switch, args=(name, sid),
                         daemon=True, name="claudevoice-resume").start()

    def _resume_then_switch(self, name: str, sid: str) -> None:
        ok, err = resume_session(sid)
        if not ok:
            self._set_status(f"{name} açılamadı: {err}")
            self._say_tpl("resume_failed", "{name} açılamadı.", name)
            return
        timeout = float(self.cfg.get("ui", "resume_timeout_sec", 45))
        # Kimlikle bekle: yeni acilan oturumun ADI hemen atanmiyor, bir sure
        # klasor adiyla gorunuyor ve isimle arama bos donuyordu.
        session = wait_for_session_id(sid, timeout=timeout / 2)
        if session is None:
            # Deep link bazen sessizce dusuyor (uygulama o an mesgulse).
            # Olculen davranis: ilk denemede hic acilmadi, ikincisinde
            # 2 saniyede acildi. Bir kez daha dene.
            print(f"[resume] {name!r} ilk denemede açılmadı, tekrar deneniyor")
            self._set_status(f"{name} açılmadı, tekrar deneniyor…")
            resume_session(sid)
            session = wait_for_session_id(sid, timeout=timeout / 2)
        if session is None:
            session = wait_for_session(name, timeout=5.0)
        if session is None:
            self._set_status(f"{name} açıldı ama listede görünmedi")
            self._say_tpl("resume_failed", "{name} açılamadı.", name)
            return
        self._switch_and_announce(session, resumed=True)

    def _app_name(self, pid) -> str:
        if pid is None:
            return "?"
        from AppKit import NSWorkspace as _W
        for a in _W.sharedWorkspace().runningApplications():
            if int(a.processIdentifier()) == int(pid):
                return a.localizedName() or "?"
        return f"pid {pid}"

    def _restore_focus(self, pid: int, name: str) -> None:
        delay = self.cfg.get("inject", "switch_restore_delay_ms", 700) / 1000
        ok = self.injector.restore_front(pid, delay)
        after = self._app_name(self.injector.capture_front())
        print(f"[odak] {name!r} iadesi: {'başarılı' if ok else 'BAŞARISIZ'} "
              f"— şimdi önde: {after!r}")
        self._set_status(f"geçildi, odak → {after}")

    def _say_tpl(self, key: str, fallback: str, name: str) -> None:
        """Config'deki sablonu doldurup okur."""
        if not self.speaker.enabled:
            return
        tpl = self.cfg.get("tts", key, fallback) or fallback
        try:
            text = tpl.format(name=name, dative=dative(name))
        except Exception:
            text = fallback.format(name=name)
        self.speaker.say(text)

    def _wake_if_asleep(self) -> None:
        """Konusma secmek konusma NIYETI demek: durduruldu durumundaysa ac.

        Aksi halde kullanici konusmayi seciyor, sonra diktesi sessizce
        yok sayiliyor ve neden gitmedigini anlamiyor.
        """
        with self.lock:
            if self.state != SLEEP:
                return
        self.explicit_listen = True
        self.mic.set_enabled(True)
        with self.lock:
            self.buffer = ""
            self.state = LIVE
        print("[durum] seçim yapıldı, dinlemeye geçildi")

    def _switch_and_announce(self, session, resumed: bool = False) -> None:
        # Gecis Claude'u one getiriyor. Mesaj gonderirken odagi nasil iade
        # ediyorsak burada da ediyoruz: baska bir pencerede calisirken
        # ekranin Claude'da kalmasi istenmiyor.
        restore = bool(self.cfg.get("inject", "restore_focus_after_switch", True))
        prev = self.injector.capture_front() if restore else None
        claude = self.injector.find_app()
        prev_name = self._app_name(prev)
        if claude is not None and prev == int(claude.processIdentifier()):
            print(f"[odak] geçiş öncesi zaten Claude'daydı, iade yok")
            prev = None                        # zaten Claude'daydik, dokunma
        else:
            print(f"[odak] geçiş öncesi önde: {prev_name!r} (pid {prev})")
        ok, msg = switch_to(session)
        if ok:
            self._last_announced = None
            self._set_status(("açıldı ve seçildi: " if resumed else "seçildi: ")
                             + session.name)
            self._wake_if_asleep()
            if resumed:
                self._say_tpl("resume_done", "{name} açıldı ve seçildi.",
                              session.name)
            else:
                self._say_tpl("select_reply", "{name} seçildi.", session.name)
            if prev is not None:
                threading.Thread(
                    target=self._restore_focus, args=(prev, prev_name),
                    daemon=True, name="claudevoice-refocus").start()
        else:
            self._set_status(f"geçilemedi: {msg}")

    def _arm_reply(self) -> None:
        """"cevap mahmut": en son duyulan mesajin oturumunu hedef al."""
        target = self._last_heard or self._last_received
        if not target:
            self._set_status("henüz cevaplanacak mesaj gelmedi")
            if self.speaker.enabled:
                self.speaker.say("Henüz gelen mesaj yok.")
            return
        self.reply_to = target
        self._set_status(f"cevap hedefi: {target} — söyle, sonra 'tamam claude'")
        if self.speaker.enabled:
            tpl = self.cfg.get("tts", "reply_template", "{dative} cevap veriyorsun.")
            self.speaker.say(tpl.format(dative=dative(target), name=target))

    def _install_stop_hotkey(self) -> None:
        """Okumayi kesen GENEL kisayolu dinler.

        NSEvent genel izleyicisi olayi YUTMAZ; tusa basildiginda one gelen
        uygulama da olayi gorur. Bu yuzden hicbir yerde karsiligi olmayan bir
        kombinasyon secildi (varsayilan ⌥⌘.).
        """
        spec = str(self.cfg.get("shortcuts", "stop_reading", "cmd+alt+.") or "")
        parts = [p.strip().lower() for p in spec.split("+") if p.strip()]
        code = KEYCODES.get(parts[-1]) if parts else None
        if code is None:
            print(f"[kısayol] geçersiz: {spec!r}")
            return
        want = 0
        for m in parts[:-1]:
            f = _NS_MODS.get(m)
            if f is None:
                print(f"[kısayol] bilinmeyen değiştirici: {m}")
                return
            want |= f

        def fired(event) -> bool:
            return (event.keyCode() == code
                    and (event.modifierFlags() & _NS_MOD_MASK) == want)

        def on_global(event):
            if fired(event):
                self._stop_reading_hotkey()

        def on_local(event):
            if fired(event):
                self._stop_reading_hotkey()
            return event

        try:
            from AppKit import NSEvent, NSEventMaskKeyDown
            self._hk_global = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                NSEventMaskKeyDown, on_global)
            self._hk_local = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
                NSEventMaskKeyDown, on_local)
            self.stop_hotkey = hotkey_label(spec)
            print(f"[kısayol] okumayı kes: {self.stop_hotkey}")
        except Exception as exc:
            print(f"[kısayol] kurulamadı: {exc}")

    def set_panel_port(self, raw) -> tuple[bool, str]:
        """Paneli baska bir porta tasir (uygulama kapanmadan)."""
        from .panel import port_status
        st = port_status(raw, self.panel.port)
        if not st.get("ok"):
            return False, st["msg"]
        port = int(st["port"])
        if st.get("same"):
            return False, f"panel zaten {port} portunda"
        if not st.get("free"):
            return False, st["msg"]
        self.cfg.set("ui", "panel_port", port)
        # Yeni porta tasima isteği YANITLADIKTAN sonra yapilmali; yoksa
        # cevabi gonderen baglanti kapanir ve tarayici hata gosterir.
        threading.Timer(0.6, self._move_panel, args=(port,)).start()
        return True, f"panel {port} portuna taşınıyor"

    def _move_panel(self, port: int) -> None:
        if self.panel.restart(port):
            print(f"[panel] yeni adres: {self.panel.url}")
            self._set_status(f"panel {self.panel.port} portunda")
        else:
            print(f"[panel] {port} portuna taşınamadı")
            self._set_status(f"panel {port} portuna taşınamadı")

    def set_stop_hotkey(self, spec: str) -> tuple[bool, str]:
        """Okumayi kesen kisayolu degistirir ve aninda yeniden kurar."""
        spec = (spec or "").strip().lower().replace(" ", "")
        parts = [p for p in spec.split("+") if p]
        if len(parts) < 2:
            return False, "en az bir değiştirici + tuş gerekli (örn. cmd+alt+.)"
        if KEYCODES.get(parts[-1]) is None:
            return False, f"bilinmeyen tuş: {parts[-1]}"
        for m in parts[:-1]:
            if m not in _NS_MODS:
                return False, f"bilinmeyen değiştirici: {m}"
        try:
            from AppKit import NSEvent
            for mon in (getattr(self, "_hk_global", None),
                        getattr(self, "_hk_local", None)):
                if mon is not None:
                    NSEvent.removeMonitor_(mon)
        except Exception:
            pass
        self._hk_global = self._hk_local = None
        self.cfg.set("shortcuts", "stop_reading", spec)
        self._install_stop_hotkey()
        return True, f"okumayı kes kısayolu: {self.stop_hotkey}"

    def _stop_reading_hotkey(self) -> None:
        self.speaker.stop_current(clear_queue=True)
        self._last_action = "✂️ KES (kısayol)"
        self._set_status(f"okuma kesildi ({self.stop_hotkey})")

    def _do_hotkey(self, hk: dict, reply: str | None = None,
                   label: str | None = None) -> None:
        name = label or hk.get("name") or "kısayol"
        ok, err = self.injector.send_hotkey(
            hk.get("bundle_id", ""), hk.get("key", ""), hk.get("modifiers", []))
        if ok:
            self._set_status(f"çalıştırıldı: {name}")
            if reply and self.speaker.enabled:
                self.speaker.say(reply)
        else:
            self._set_status(f"{name} çalıştırılamadı: {err}")
            self._notify(name, err)

    def _do_switch(self, spoken_name: str) -> None:
        if not spoken_name:
            self._set_status(
                f"hangi konuşma? örn: 'Kunaz Geliştirme seç {self.call_name}'")
            return
        session, score, ranked = self.registry.find(spoken_name)
        if session is None:
            sid = self.titles.find(spoken_name)       # kapali olabilir
            if sid:
                self._set_status(f"{spoken_name} kapalı, açılıyor…")
                self._say_tpl("resume_opening", "{name} kapalı, açıyorum.",
                              spoken_name)
                threading.Thread(target=self._resume_then_switch,
                                 args=(spoken_name, sid), daemon=True,
                                 name="claudevoice-resume").start()
                return
            near = ranked[0][0].name if ranked else "—"
            self._set_status(f"konuşma bulunamadı: {spoken_name} (en yakın: {near})")
            self._notify("Konuşma bulunamadı", f"{spoken_name} → en yakın: {near}")
            return
        ok, msg = switch_to(session)
        if ok:
            self._last_announced = None          # yeni konusmada adi tekrar soyle
            self._set_status(f"geçildi: {session.name} ({score:.0%})")
            if self.speaker.enabled:
                self.speaker.say(f"{session.name} seçildi.")
        else:
            self._set_status(f"geçilemedi: {msg}")
            self._notify("Geçilemedi", msg)

    def _deliver(self, text: str) -> None:
        # "cevap mahmut" ile bir oturum hedeflendiyse once oraya gec.
        if self.reply_to:
            session, _, _ = self.registry.find(self.reply_to)
            if session is not None:
                moved, msg = switch_to(session)
                if not moved:
                    self._set_status(f"cevaplanamadı: {msg}")
                    self._notify("Cevaplanamadı", msg)
                    self.reply_to = None
                    return
                time.sleep(self.cfg.get("inject", "switch_settle_ms", 700) / 1000)
            self.reply_to = None                 # tek seferlik; artik o oturumdayiz

        ok, note = self.injector.send(text)
        if ok:
            self.last_sent = text
            self._set_status(f"gönderildi: {text[:40]}" + (f" ({note})" if note else ""))
            if self.cfg.get("ui", "notify_on_send", True):
                self._notify("Claude'a gönderildi", text[:140])
        else:
            self._set_status(f"gönderilemedi: {note}")
            self._notify("Gönderilemedi", note)


def _run_inject_test() -> None:
    """Uygulamanin kendi izin kimligiyle yazma testi. Enter'a BASMAZ."""
    cfg = Config()
    out = {"ax_trusted": bool(ax_trusted()), "ts": time.strftime("%H:%M:%S")}
    try:
        icfg = dict(cfg["inject"])
        icfg["press_enter"] = False
        inj = Injector(icfg)
        app = inj.find_app()
        out["claude_running"] = app is not None
        if app is not None:
            out["focused_role"] = inj.focused_role(app.processIdentifier())
            ok, note = inj.send("ClaudeVoice testi — gönderilmedi, silebilirsin.")
            out["injected"] = ok
            out["note"] = note
    except Exception as exc:
        out["error"] = repr(exc)
    path = os.path.join(os.path.dirname(CONFIG_PATH), ".inject_test.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)


def _setup_logging() -> None:
    """Uygulama `open` ile baslatildiginda stdout hicbir yere gitmiyor ve
    hatalar goze carpmiyor. Ciktiyi .app.log dosyasina yonlendir."""
    if sys.stdout is not None and sys.stdout.isatty():
        return
    path = os.path.join(os.path.dirname(CONFIG_PATH), ".app.log")
    try:
        fh = open(path, "a", buffering=1, encoding="utf-8")
        sys.stdout = fh
        sys.stderr = fh
        print(f"\n===== başlangıç {time.strftime('%Y-%m-%d %H:%M:%S')} =====")
    except Exception:
        pass


# NSEvent degistirici bayraklari (Quartz'inkilerden FARKLI sayilar).
_NS_MODS = {
    "cmd": 1 << 20, "command": 1 << 20,
    "shift": 1 << 17,
    "alt": 1 << 19, "option": 1 << 19,
    "ctrl": 1 << 18, "control": 1 << 18,
}
_NS_MOD_MASK = (1 << 17) | (1 << 18) | (1 << 19) | (1 << 20)
_MOD_SYM = {"cmd": "⌘", "command": "⌘", "shift": "⇧",
            "alt": "⌥", "option": "⌥", "ctrl": "⌃", "control": "⌃"}


def hotkey_label(spec: str) -> str:
    """'cmd+alt+.' -> '⌥⌘.' (okunakli hal)."""
    parts = [p.strip().lower() for p in str(spec).split("+") if p.strip()]
    if not parts:
        return ""
    key, mods = parts[-1], parts[:-1]
    order = ["ctrl", "control", "alt", "option", "shift", "cmd", "command"]
    mods.sort(key=lambda m: order.index(m) if m in order else 99)
    return "".join(_MOD_SYM.get(m, m) for m in mods) + key.upper()


def _dock_hide() -> None:
    """Tek seferlik CLI modlari Dock'ta kare acmasin."""
    try:
        from AppKit import NSApplication, NSApplicationActivationPolicyProhibited
        NSApplication.sharedApplication().setActivationPolicy_(
            NSApplicationActivationPolicyProhibited)
    except Exception:
        pass


def _single_instance() -> bool:
    """Zaten calisan bir kopya varsa False doner.

    Bundle artik Dock'ta gorunuyor; her fazladan kopya ayri bir kare aciyor
    ve ayni mikrofonu/portu paylasmaya calisiyor. Kilit dosyasi pid tutar,
    surec olmusse kilit devralinir.
    """
    lock = os.path.join(os.path.dirname(CONFIG_PATH), ".app.lock")
    try:
        with open(lock, encoding="utf-8") as fh:
            pid = int((fh.read() or "0").strip() or 0)
        if pid and pid != os.getpid():
            os.kill(pid, 0)                  # yasiyor mu?
            print(f"[tek kopya] zaten calisiyor (pid {pid}), cikiliyor")
            return False
    except (FileNotFoundError, ValueError, ProcessLookupError, PermissionError):
        pass
    except Exception:
        pass
    try:
        with open(lock, "w", encoding="utf-8") as fh:
            fh.write(str(os.getpid()))
    except Exception:
        pass
    return True


def main() -> None:
    _setup_logging()
    if "--probe-ax" in sys.argv:
        _dock_hide()
        from . import axprobe
        i = sys.argv.index("--probe-ax")
        bundle = sys.argv[i + 1] if len(sys.argv) > i + 1 else ""
        axprobe.main(bundle, os.path.join(os.path.dirname(CONFIG_PATH),
                                          ".axprobe.json"))
        return
    if "--test-hotkey" in sys.argv:
        _dock_hide()
        import time as _t
        from AppKit import NSWorkspace as _WS
        cfg = Config()
        ws = _WS.sharedWorkspace()
        front = lambda: (ws.frontmostApplication().localizedName()
                         if ws.frontmostApplication() else "?")
        out = {"ax_trusted": bool(ax_trusted()), "before": front(), "steps": []}
        inj = Injector(cfg["inject"])
        hk = (cfg.raw("hotkeys", []) or [{}])[0]
        # Hedef uygulama GERCEKTEN one gelebiliyor mu? Gelemiyorsa kisayol
        # web icerigine ulasmaz ve sessizce etkisiz kalir.
        from AppKit import NSApplicationActivateIgnoringOtherApps as _IGN
        tgt = inj.find_app(hk.get("bundle_id", ""))
        out["target_running"] = tgt is not None
        if tgt is not None:
            prev = ws.frontmostApplication()
            tgt.activateWithOptions_(_IGN)
            _t.sleep(0.45)
            out["front_during_activation"] = front()
            if prev is not None:
                prev.activateWithOptions_(_IGN)
            _t.sleep(0.3)
        for i in (1,):                        # TEK sefer: durumu gercekten degistir
            ok, err = inj.send_hotkey(hk.get("bundle_id", ""), hk.get("key", ""),
                                      hk.get("modifiers", []))
            out["steps"].append({"n": i, "ok": ok, "err": err, "front": front()})
            _t.sleep(1.2)
        out["after"] = front()
        out["focus_restored"] = out["after"] == out["before"]
        with open(os.path.join(os.path.dirname(CONFIG_PATH),
                               ".hotkey_test.json"), "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)
        return
    if "--test-inject" in sys.argv:
        _dock_hide()
        _run_inject_test()
        return
    if not _single_instance():
        return
    ClaudeVoice().run()


if __name__ == "__main__":
    main()
