"""Ayarlar: config.json okunur, eksik alanlar DEFAULTS ile tamamlanir."""
from __future__ import annotations

import json
import os
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config.json")
STATE_PATH = os.path.join(ROOT, ".state.json")
MUTED_PATH = os.path.join(ROOT, ".muted.json")   # menuden susturulanlar
TTS_PIDS_PATH = os.path.join(ROOT, ".tts.pids")  # calan say/afplay surecleri

# Whisper'a verilen on-sozluk. Turkce konusurken araya karisan Ingilizce
# yazilim terimlerinin fonetige cevrilmesini ("deploy" -> "diploy") engeller.
DEV_PROMPT = (
    "Backend'deki authentication endpoint'ini refactor ettim. Docker image'ini "
    "build edip staging'e deploy et. Pull request'i merge etmeden once test "
    "coverage'a bak. Database migration'i rollback etmemiz gerekebilir. React "
    "component'inde bir race condition var, async await kullanarak duzelttim. "
    "Redis cache'ini temizle, queue'daki worker'lari restart et. Log'lardaki "
    "stack trace'e gore null pointer exception aliyoruz. TypeScript interface'ini "
    "guncelle, dependency'leri package.json'a ekle. Kubernetes cluster'indaki "
    "pod'lar timeout veriyor, load balancer config'ini kontrol et. Branch'i "
    "rebase edip commit'leri squash ettim. API response payload'inda JSON schema "
    "uyusmuyor. Lint ve format'tan sonra CI pipeline'i yesile dondu."
)

DEFAULTS = {
    "stt": {
        # mlx-community HF repo. Turkce icin large-v3-turbo iyi denge.
        "model": "mlx-community/whisper-large-v3-turbo",
        "language": "tr",
        # BOS BIRAKILDI. DEV_PROMPT'u denedim ve ZARAR verdigini olctum:
        # - Duz Turkce'de hicbir fayda saglamadi (ciktilar birebir ayni)
        # - Karisik cumlede Turkce kelimeyi Ingilizce'ye itti:
        #     "Şu backend'deki" -> "Shubach kenddeki"
        # - Sessizlikte prompt'un kendisini geri okudu ("API response",
        #   "JSON"), bu da "Ingilizce'ye ceviriyor" izlenimi verdi.
        # Ingilizce terimleri zaten glossary.py duzeltiyor.
        # Denemek istersen: "initial_prompt": DEV_PROMPT
        "initial_prompt": "",
        # Whisper'in sessizlikte uydurdugu metinleri eleme esigi
        "no_speech_threshold": 0.5,
        "min_segment_sec": 0.35,
        # Dahili mikrofon cok dusuk seviyede kaydediyor; Whisper'a vermeden
        # once hedef seviyeye yukselt. Kazanc max_gain ile sinirli.
        "normalize": True,
        "target_rms": 0.08,
        "max_gain": 12.0,
    },
    "audio": {
        # Giris cihazi: null = otomatik, "airpods" gibi isim parcasi, ya da indeks
        "device": None,
        # Otomatik secim sirasi:
        #   "headset" -> once kulaklik mikrofonu (VARSAYILAN). Masadan uzakta
        #                dahili mikrofon duymaz; kulaklik duyar.
        #   "builtin" -> once dahili mikrofon. Bluetooth kulaklikta mikrofon
        #                acilinca macOS HFP'ye duser ve oynatma kalitesi
        #                bozulabilir ("patlak" ses); bunu istemiyorsan bunu sec.
        #   "system"  -> sistem varsayilani
        "prefer": "headset",
        # Kullanici panelden belirli bir CIKIS cihazi sectiyse okuma oradan
        # calar; null ise sistem varsayilani kullanilir.
        "output_device": None,
        "sample_rate": 16000,
        "frame_ms": 30,
        "vad_ratio": 3.2,            # gurultu tabanina gore kac kat
        # Mutlak alt sinir. Dahili mikrofon ~0.005 tepe yapiyor, eski 0.006
        # degeri konusmayi esigin ALTINDA birakiyordu.
        "vad_min_rms": 0.0022,
        "start_frames": 3,           # ~90ms konusma -> baslat
        # Segmentin gonderilmesi icin gereken TOPLAM konusma cercevesi.
        # 8 x 30ms = 240ms. Altindaki kisa gurultuler (tiklama, nefes)
        # Whisper'i halusinasyona sokuyordu; artik hic gonderilmiyor.
        "min_voiced_frames": 8,
        "silence_ms": 700,           # bu kadar sessizlik -> segmenti kapat
        "preroll_ms": 300,           # kelime basi kirpilmasin
        "max_segment_sec": 25.0,
    },
    "phrases": {
        # Asistanin cagri adi. Turkce bir isim secildi: Whisper Turkce modunda
        # "Claude"u surekli Clod/Cloud/Klot diye yaziyordu, "Mahmut" tek sekilde
        # yaziliyor. Degistirmek istersen "name" + "name_variants" ve asagidaki
        # kaliplardaki kelimeyi birlikte degistir.
        "name": "mahmut",
        # Whisper ayni kelimeyi cok farkli yazabiliyor. Gercek kayitlardan
        # toplanan yazimlar: "kes" -> Mahmutçes / kiss / çez / keç / Chris,
        # "başla" -> bu / Pashle. Bulanik eslestirme bu kadarini yakalayamaz,
        # bu yuzden acik liste tutuluyor. Yeni bir yanlis duyma gorursen
        # (.app.log ya da panelde "son duyulan") buraya ekle.
        "word_variants": {
            "mahmut": ["mahmut", "mahmud", "mamut", "marmut", "makmut",
                       "mahmet", "mahmit", "mahmout", "machmut",
                       # gercek kayitlardan: "Ahmut"
                       "ahmut", "ahmet", "mahmutt", "mamud"],
            "kes": ["kes", "kess", "kec", "kech", "kecc", "ces", "cess",
                    "cec", "ches", "chess", "kiss", "kis", "cez", "kez",
                    "chris", "kris", "keche", "gec", "kesh",
                    # gercek kayitlardan: "Mahmut, çeşit."
                    "cesit", "cesid", "cesitt", "kesit", "kesid", "cesiit"],
            "basla": ["basla", "baslaa", "baslar", "basle", "bashla",
                      "pasla", "pashle", "pasle", "bashle", "basta", "bu",
                      "baslah", "bashlar"],
            "dur": ["dur", "durr", "tur", "dor", "duur", "dour"],
            "sus": ["sus", "suss", "sos", "sush"],
            "mikrofon": ["mikrofon", "mikrofonu", "mikrafon", "mikrafonu",
                         "microfon", "mutofan", "mikrofan", "mikrofun",
                         "mikrophone", "microphone", "mikrofono"],
            "ac": ["ac", "ach", "as", "acc"],
            "kapat": ["kapat", "kapa", "kappat", "kapatt", "kapad"],
            "tamam": ["tamam", "taman", "tamamm", "tamaam", "daman"],
            "cevap": ["cevap", "cevab", "cevaap", "cevapp", "jevap"],
            # gercek kayitlardan: "seçme", "seçmek" diye de duyuluyor
            "sec": ["sec", "sech", "sek", "secc", "sets", "secme", "sece",
                    "secer", "secmek", "sez", "ses"],
            "gonder": ["gonder", "gondere", "gonda", "gonder"],
            "iptal": ["iptal", "iptall", "ipta"],
            "bosver": ["bosver", "bosfer", "bosvere"],
            "yeter": ["yeter", "yeterr", "yetter"],
            "uyan": ["uyan", "uyaan", "uyyan"],
            "bekle": ["bekle", "beklee", "bakle"],
            # "listeyi getir mahmut" -> "Mahmut'u getirdim." diye duyuldu
            "getir": ["getir", "gatir", "getiri", "yatir", "getir'",
                      "getirdim", "getirdi", "getirin", "getirip",
                      "getirem", "getirdin"],
            "liste": ["liste", "listeyi", "listemi", "listesi", "listeye"],
        },
        "name_variants": [
            "mahmut", "mahmud", "mamut", "marmut", "makmut",
            "mahmet", "mahmit", "mahmut'",
        ],
        # Telsiz usulu: bunlardan biri cumlenin SONUNDA gecince mesaj gonderilir.
        "send": [
            "tamam mahmut", "mahmut tamam", "tamam gonder",
            "gonder mahmut", "mahmut gonder", "over", "tamam over",
            "gonderebilirsin", "yolla mahmut", "mahmut yolla",
        ],
        # Tamponu temizler, mesaj gitmez.
        "cancel": [
            "iptal mahmut", "mahmut iptal", "bosver mahmut",
            "sil mahmut", "unut mahmut", "iptal et mahmut",
        ],
        # "mahmut basla" -> dinlemeyi acar (duraklatilmissa da uyandirir).
        "listen": [
            "mahmut basla", "basla mahmut", "mahmut baslayalim",
            "mahmut beni dinle", "beni dinle mahmut", "mahmut dinle beni",
            "mahmut uyan", "uyan mahmut", "mahmut dinlemeye basla",
        ],
        # "mahmut stop" -> derin uyku. SADECE "listen" kaliplari uyandirir.
        # "mahmut dur" -> derin uyku. SADECE "listen" kaliplari uyandirir.
        "sleep": [
            "mahmut dur", "dur mahmut", "mahmut duralim",
            "mahmut bekle", "bekle mahmut", "mahmut mola",
            "mola mahmut", "mahmut beni dinleme", "mahmut tatilde",
        ],
        # "mahmut kes" -> SADECE o anki okumayi keser. Dinleme devam eder,
        # kuyrukta bekleyen varsa sonraki mesaja gecer ("mahmut dur" degil).
        "cut": [
            "mahmut kes", "kes mahmut", "mahmut sus", "sus mahmut",
            "mahmut yeter", "yeter mahmut", "mahmut gec", "gec mahmut",
        ],
        # "listeyi getir mahmut" -> sik kullanilan konusmalari numarali okur.
        "list": [
            "listeyi getir mahmut", "mahmut listeyi getir",
            "listeyi oku mahmut", "mahmut listeyi oku",
            "liste mahmut", "mahmut liste", "listeyi say mahmut",
            "listeyi getir", "listeyi oku", "listeyi say",
            "mahmut getir", "getir mahmut", "mahmutu getir",
        ],
        # Liste okumak ZARARSIZ bir eylem (mesaj gitmez, durum degismez),
        # bu yuzden ona ozel gevsek bir kural var: kisa bir cumle "liste"
        # ile BASLIYORSA, cagri adi taninmasa bile liste okunur.
        # Gerekcesi: Whisper "listeyi getir mahmut"u "Listeyi yatırmamışım."
        # diye yazdi — ikinci kelimede taninacak hicbir sey kalmamisti.
        # 0 yaparsan bu kural kapanir.
        "list_loose_max_tokens": 3,
        # "cevap mahmut" -> en son DUYDUGUN mesajin oturumuna cevap yazar.
        "reply": [
            "cevap mahmut", "cevapla mahmut", "cevap ver mahmut",
            "yanit mahmut", "yanitla mahmut", "buna cevap mahmut",
            "cevap vereyim mahmut",
        ],
        # Sira secimi ("birinci sec mahmut") kaliplari KODDA uretilir.
        # Panelden eklenen ekstra kaliplar burada saklanir:
        #   {"1": ["ikinciyi secme aldik"], "2": [...]}
        "fav_select": {},
        # "<oturum adi> sec mahmut" -> o konusmaya gecer.
        "switch": [
            "sec mahmut", "gec mahmut", "secc mahmut",
            "oturumu sec mahmut", "konusmayi sec mahmut", "sohbeti sec mahmut",
            "oturumuna gec mahmut", "konusmasina gec mahmut",
            "sec gec mahmut", "ac mahmut",
        ],
        # "hey mahmut" modunda dinlemeyi acar.
        # NOT: buraya ciplak "mahmut" KOYMA. find_wake metnin ICINDE arar;
        # ciplak ad, "... tamam mahmut" gibi komutlari da uyandirma sanip
        # mesaji yutar.
        "wake": [
            "hey mahmut", "ey mahmut", "selam mahmut", "merhaba mahmut",
            "baksana mahmut", "gunaydin mahmut",
        ],
    },
    "tts": {
        "enabled": True,
        "voice": "Yelda",
        "rate": 210,
        # Okuma ses seviyesi (0.0 - 2.0). 1.0 disinda bir deger verilince
        # okuma dosyaya basilip `afplay -v` ile calinir (kucuk ek gecikme).
        "volume": 1.0,
        # Iki sesli okuma (Ingilizce terimleri ayri bir sesle okuma).
        # VARSAYILAN KAPALI: her terimde ses degistirmek akiciligi bozuyor ve
        # her parca ~1 sn olu zaman ekliyor. Kapaliyken Yelda Ingilizce
        # kelimeleri de okur (Turkce fonetikle, ama kesintisiz).
        # Denemek istersen true yap.
        "bilingual": False,
        "voice_en": "Samantha",
        "rate_en": 200,                 # kelime/dakika
        "max_chars": 1200,           # tek mesajda okunacak ust sinir
        "say_code_placeholder": "kod bloğu",
        # Okuma sirasinda mikrofonu kapat. VARSAYILAN KAPALI: kapali olursa
        # "mahmut kes" diyerek okumayi sozle kesebilirsin. Okuma sirasinda
        # yalnizca kes/dur/basla komutlari islenir, bu yuzden Claude'un kendi
        # sesi yanlislikla mesaj gondermez.
        # HOPARLORDEN dinliyorsan ve yankidan sikayetciysen true yap
        # (o zaman okumayi sozle kesemezsin, menuden kesersin).
        "duck_mic_while_speaking": "auto",
        # Okuma sirasinda mikrofon AKISINI kapat (sadece mikrofon ve
        # hoparlor ayni kablosuz cihazsa). Akis acik kaldigi surece macOS
        # AirPods'u HFP profilinde tutuyor ve ses cizirtili caliyor.
        # OLCUM: AirPods Pro 3'te acik mikrofon tek basina profili
        # dusurmuyor, ses temiz kaliyor. Bu yuzden varsayilan KAPALI;
        # okuma sirasinda sesli "kes" diyebilmek daha degerli.
        # "auto" (paylasimli cihazda birak) | true | false (varsayilan)
        "release_mic_while_speaking": False,
        "mic_cooldown_ms": 400,
        # Okumadan once hangi konusmadan geldigini soyler.
        #   "always"    -> her mesajda
        #   "on_change" -> sadece konusma degistiginde
        #   "never"     -> hic
        "announce_session": "always",
        "announce_template": "{name} mesajını okuyorum.",
        # Anons bittikten sonra icerige gecmeden once beklenen sure
        "announce_pause_ms": 500,
        # Parcalari tek dosyada birlestirip kesintisiz cal (ffmpeg gerekir)
        "seamless": True,
        # "cevap mahmut" deyince sesli teyit sablonu
        "reply_template": "{dative} cevap veriyorsun.",
        # Paneldeki "dene" dugmesinin okudugu ornek cumle
        "voice_test_text": "Merhaba, Claude mesajlarını böyle okuyacağım.",
        "listen_reply": "Dinliyorum.",
        # Zaten dinliyorken tekrar "mahmut basla" denirse
        "already_listening_reply": "Zaten açığım, dinliyorum.",
        # Zaten durdurulmusken tekrar "mahmut dur" denirse
        "already_stopped_reply": "Zaten durmuştum.",
        # Konusma secimi sesli bildirimleri
        "select_reply": "{name} seçildi.",
        "resume_opening": "{name} kapalı, açıyorum.",
        "resume_done": "{name} açıldı ve seçildi.",
        "resume_failed": "{name} açılamadı.",
        "not_found_reply": "{name} bulunamadı.",
        # Numarali liste okuma
        "list_lead": "Listeyi okuyorum.",
        "list_item": "{no} {name}",
        "list_closed_suffix": ", kapalı",
        "list_empty": "Liste boş.",
        # Parcalar arasina konulan sessizlik. Noktalama ile guvenilir
        # duraklama elde edilemiyor: olctugumde nokta cogu yerde hic
        # duraklama uretmedi, virgul ise sayidan SONRA duraklatip ismi
        # bir sonraki sayiya yapistirdi.
        "list_pause_sec": 0.35,
        "sleep_reply": "Tamam, durdum."  ,
    },
    # Okumayi kesen GENEL kisayol (uygulama onde olmasa da calisir).
    # "cmd+alt+k" secildi (k = kes). Yalin ⌘K her yerde dolu (tarayici
    # adres aramasi, terminal temizleme, komut paleti) ama ⌥ eklenmis hali
    # bos; olay yutulmadigi icin bos bir kombinasyon sart.
    "shortcuts": {
        "stop_reading": "cmd+alt+k",
    },
    "inject": {
        # "claude" | "codex" — panelden secilir (Ayarlar > Kod uygulaması)
        "target": "claude",
        "bundle_id": "com.anthropic.claudefordesktop",
        "activate_delay_ms": 160,    # app one gelsin diye bekleme
        # Kisayol gonderirken hedef uygulamanin one gelmesi daha uzun surebilir
        # (Electron pencereleri gec odaklaniyor)
        "hotkey_activate_delay_ms": 400,
        # true: kisayolu hedef surece DOGRUDAN gonder (odak degismez).
        # Bazi uygulamalar bu olaylari YOK SAYIYOR, bu yuzden varsayilan false:
        # uygulama kisa sureligine one alinir, tusa basilir, odak iade edilir.
        "direct_post": False,
        "paste_delay_ms": 90,        # Cmd+V sonrasi Enter oncesi bekleme
        "restore_focus": True,       # mesaj sonrasi eski uygulamaya don
        "restore_clipboard": True,
        "press_enter": True,
        # "cevap mahmut" sonrasi oturum gecisinin oturmasi icin bekleme
        "switch_settle_ms": 700,
        # Konusma degistirdikten sonra odagi bulundugun uygulamaya iade et.
        # false yaparsan ekran Claude'da kalir (o konusmayi gormek istersen).
        "restore_focus_after_switch": True,
        "switch_restore_delay_ms": 700,
    },
# Sesle tetiklenen uygulama kisayollari.
    # Hedef uygulama kisa sureligine one alinir, tus basilir, odak kaldigin
    # uygulamaya iade edilir. Yeni bir kisayol eklemek icin buraya bir kayit
    # ekle; kod degistirmen gerekmez.
    #
    # Ornek: toplanti uygulamasinin mikrofonunu sesle ac/kapa. Kendi
    # uygulamanin bundle id'sini `osascript -e 'id of app "Uygulama"'`
    # ile ogrenebilirsin.
    #
    # NOT: Cogu uygulamanin mikrofon kisayolu bir ANAHTAR'dir; "ac" da
    # "kapat" da ayni tusa basar. Uygulama mikrofon durumunu disariya
    # vermiyorsa gercek durum okunamaz, bu yuzden sesli teyit SOYLEDIGIN
    # komuta gore verilir. Her grup kendi cevabini (reply) ve panel
    # etiketini (label) tasir.
    "hotkeys": [],

    "ui": {
        # Acilista hangi durumda baslasin:
        #   "sleep"  -> mikrofon ACIK ama sadece "mahmut basla" dinlenir (onerilen)
        #   "listen" -> dogrudan aktif dinleme
        #   "off"    -> mikrofon tamamen kapali (sesle acilamaz, menuden ac)
        "start_mode": "sleep",
        "wake_word_mode": True,      # "hey mahmut" bekle
        # macOS bildirimleri. Kapali: panel ve sesli cevap zaten yeterli.
        "notifications": False,
        "notify_on_send": False,
        # Tarayicida acilan kontrol paneli (sadece 127.0.0.1)
        "panel_enabled": True,
        "panel_port": 8765,
        # Yuklu komut seti (langpacks.py). "Varsayilana don" bunu yeniden yukler.
        "langpack": "tr",
        # Numarali hizli erisim listesi. "listeyi getir mahmut" ile sesli
        # okunur, "birinci sec mahmut" ile secilir. Panelden duzenlenebilir.
        "favorites": [
            "Kunaz Reklam",
            "Kunaz Geliştirme",
            "Saint Panel",
            "Ses Kontrolü",
            "Pam Geliştirme",
            "Portal Geliştirme",
        ],
        # Panelde tutulan "son duyulanlar" sayisi
        "history_size": 200,
        # Tampona bu kadar saniye ekleme yapilmazsa otomatik temizlenir (0=kapali)
        "buffer_timeout_sec": 180,
        # Kapali bir konusma acilirken listede belirmesi icin beklenen sure
        "resume_timeout_sec": 45,
    },
}


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


class Config:
    def __init__(self, path: str = CONFIG_PATH):
        self.path = path
        self._lock = threading.Lock()
        self.data = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                user = json.load(fh)
            with self._lock:
                self.data = _merge(DEFAULTS, user)
        except FileNotFoundError:
            self.write_default()
        except Exception as exc:  # bozuk json -> varsayilanla devam
            print(f"[config] {self.path} okunamadi ({exc}); varsayilanlar kullaniliyor")

    def write_default(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump(DEFAULTS, fh, ensure_ascii=False, indent=2)
        except Exception as exc:
            print(f"[config] yazilamadi: {exc}")

    def __getitem__(self, key: str):
        with self._lock:
            return self.data[key]

    def set(self, section: str, key: str, value) -> None:
        """Tek bir ayari gunceller ve config.json'a yazar (kalici olsun)."""
        with self._lock:
            self.data.setdefault(section, {})[key] = value
            snapshot = json.loads(json.dumps(self.data))
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(snapshot, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except Exception as exc:
            print(f"[config] kaydedilemedi: {exc}")

    def set_raw(self, name: str, value) -> None:
        """Ust seviye bir degeri gunceller ve diske yazar."""
        with self._lock:
            self.data[name] = value
            snapshot = json.loads(json.dumps(self.data))
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(snapshot, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except Exception as exc:
            print(f"[config] kaydedilemedi: {exc}")

    def raw(self, name: str, default=None):
        """Ust seviye bir degeri oldugu gibi dondurur (liste de olabilir)."""
        with self._lock:
            return self.data.get(name, default)

    def get(self, section: str, key: str, default=None):
        with self._lock:
            return self.data.get(section, {}).get(key, default)
