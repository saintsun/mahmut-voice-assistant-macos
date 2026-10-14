"""Settings: config.json is read and missing fields come from DEFAULTS."""
from __future__ import annotations

import json
import os
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config.json")
STATE_PATH = os.path.join(ROOT, ".state.json")
MUTED_PATH = os.path.join(ROOT, ".muted.json")   # menuden susturulanlar
TTS_PIDS_PATH = os.path.join(ROOT, ".tts.pids")  # calan say/afplay surecleri

# The prompt handed to Whisper. Keeps English technical terms mixed into
# another language from being rendered phonetically ("deploy" -> "diploy").
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
        # mlx-community HF repo. large-v3-turbo is a good balance.
        "model": "mlx-community/whisper-large-v3-turbo",
        "language": "tr",
        # LEFT EMPTY. DEV_PROMPT was tried and measured to HURT:
        # - no benefit on plain speech (output was identical)
        # - in mixed sentences it pushed native words towards English:
        #     "Şu backend'deki" -> "Shubach kenddeki"
        # - on silence it read the prompt back ("API response", "JSON"),
        #   which looked like it was translating.
        # glossary.py already repairs the technical terms.
        # To try it: "initial_prompt": DEV_PROMPT
        "initial_prompt": "",
        # Threshold for discarding text Whisper invents on silence
        "no_speech_threshold": 0.5,
        "min_segment_sec": 0.35,
        # The built-in microphone records very quietly; lift it to a target
        # level before handing it to Whisper. The gain is capped by max_gain.
        "normalize": True,
        "target_rms": 0.08,
        "max_gain": 12.0,
    },
    "audio": {
        # Input device: null = automatic, a name fragment like "airpods", or an index
        "device": None,
        # Automatic selection order:
        #   "headset" -> headset microphone first (DEFAULT). Away from the
        #                desk the built-in mic cannot hear you; a headset can.
        #   "builtin" -> built-in microphone first. Opening the mic on a
        #                Bluetooth headset can drop macOS into HFP and degrade
        #                playback quality; pick this if that bothers you.
        #   "system"  -> the system default
        "prefer": "headset",
        # When the user picks an explicit OUTPUT device in the panel, reading
        # plays there; null means the system default.
        "output_device": None,
        "sample_rate": 16000,
        "frame_ms": 30,
        "vad_ratio": 3.2,            # gurultu tabanina gore kac kat
        # Absolute floor. The built-in mic peaks around 0.005, so the old
        # value of 0.006 left speech BELOW the threshold.
        "vad_min_rms": 0.0022,
        "start_frames": 3,           # ~90ms konusma -> baslat
        # TOTAL speech frames required before a segment is sent.
        # 8 x 30 ms = 240 ms. Shorter noises (a click, a breath) pushed Whisper
        # into hallucinating; they are no longer sent at all.
        "min_voiced_frames": 8,
        "silence_ms": 700,           # bu kadar sessizlik -> segmenti kapat
        "preroll_ms": 300,           # kelime basi kirpilmasin
        "max_segment_sec": 25.0,
    },
    "phrases": {
        # The assistant's wake name. A non-English name was chosen: Whisper
        # kept writing "Claude" as Clod/Cloud/Klot, while "Mahmut" comes out
        # one way. To change it, update "name", "name_variants" and the word in
        # the patterns below together.
        "name": "mahmut",
        # Whisper spells the same word in wildly different ways. Collected
        # from real recordings: "kes" -> Mahmutçes / kiss / çez / keç / Chris,
        # "başla" -> bu / Pashle. Fuzzy matching cannot cover that much, so an
        # explicit list is kept. When you see a new misrecognition (.app.log or
        # "recently heard" in the panel), add it here.
        "word_variants": {
            "mahmut": ["mahmut", "mahmud", "mamut", "marmut", "makmut",
                       "mahmet", "mahmit", "mahmout", "machmut",
                       # from real recordings: "Ahmut"
                       "ahmut", "ahmet", "mahmutt", "mamud"],
            "kes": ["kes", "kess", "kec", "kech", "kecc", "ces", "cess",
                    "cec", "ches", "chess", "kiss", "kis", "cez", "kez",
                    "chris", "kris", "keche", "gec", "kesh",
                    # from real recordings: "Mahmut, çeşit."
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
            # from real recordings: also heard as "seçme", "seçmek"
            "sec": ["sec", "sech", "sek", "secc", "sets", "secme", "sece",
                    "secer", "secmek", "sez", "ses"],
            "gonder": ["gonder", "gondere", "gonda", "gonder"],
            "iptal": ["iptal", "iptall", "ipta"],
            "bosver": ["bosver", "bosfer", "bosvere"],
            "yeter": ["yeter", "yeterr", "yetter"],
            "uyan": ["uyan", "uyaan", "uyyan"],
            "bekle": ["bekle", "beklee", "bakle"],
            # "listeyi getir mahmut" was heard as "Mahmut'u getirdim."
            "getir": ["getir", "gatir", "getiri", "yatir", "getir'",
                      "getirdim", "getirdi", "getirin", "getirip",
                      "getirem", "getirdin"],
            "liste": ["liste", "listeyi", "listemi", "listesi", "listeye"],
        },
        "name_variants": [
            "mahmut", "mahmud", "mamut", "marmut", "makmut",
            "mahmet", "mahmit", "mahmut'",
        ],
        # Radio style: the message is sent when one of these ends the sentence.
        "send": [
            "tamam mahmut", "mahmut tamam", "tamam gonder",
            "gonder mahmut", "mahmut gonder", "over", "tamam over",
            "gonderebilirsin", "yolla mahmut", "mahmut yolla",
        ],
        # Clears the buffer; no message is sent.
        "cancel": [
            "iptal mahmut", "mahmut iptal", "bosver mahmut",
            "sil mahmut", "unut mahmut", "iptal et mahmut",
        ],
        # "mahmut basla" -> turns listening on (wakes from a pause too).
        "listen": [
            "mahmut basla", "basla mahmut", "mahmut baslayalim",
            "mahmut beni dinle", "beni dinle mahmut", "mahmut dinle beni",
            "mahmut uyan", "uyan mahmut", "mahmut dinlemeye basla",
        ],
        # "mahmut stop" -> deep sleep. ONLY "listen" patterns wake it.
        # "mahmut dur" -> deep sleep. ONLY "listen" patterns wake it.
        "sleep": [
            "mahmut dur", "dur mahmut", "mahmut duralim",
            "mahmut bekle", "bekle mahmut", "mahmut mola",
            "mola mahmut", "mahmut beni dinleme", "mahmut tatilde",
        ],
        # "mahmut kes" -> stops ONLY the current reading. Listening continues
        # and the queue moves on to the next message (unlike "mahmut dur").
        "cut": [
            "mahmut kes", "kes mahmut", "mahmut sus", "sus mahmut",
            "mahmut yeter", "yeter mahmut", "mahmut gec", "gec mahmut",
        ],
        # "listeyi getir mahmut" -> reads the favourite conversations by number.
        "list": [
            "listeyi getir mahmut", "mahmut listeyi getir",
            "listeyi oku mahmut", "mahmut listeyi oku",
            "liste mahmut", "mahmut liste", "listeyi say mahmut",
            "listeyi getir", "listeyi oku", "listeyi say",
            "mahmut getir", "getir mahmut", "mahmutu getir",
        ],
        # Reading the list is a HARMLESS action (nothing is sent, no state
        # changes), so it gets its own lenient rule: a short sentence that
        # STARTS with "liste" reads the list even when the wake name was not
        # recognised. Why: Whisper wrote "listeyi getir mahmut" as "Listeyi
        # yatırmamışım." - nothing recognisable was left in the second word.
        # Set it to 0 to turn the rule off.
        "list_loose_max_tokens": 3,
        # "cevap mahmut" -> replies in the session of the message you LAST heard.
        "reply": [
            "cevap mahmut", "cevapla mahmut", "cevap ver mahmut",
            "yanit mahmut", "yanitla mahmut", "buna cevap mahmut",
            "cevap vereyim mahmut",
        ],
        # Ordinal patterns ("birinci sec mahmut") are generated IN CODE.
        # Extra patterns added from the panel are stored here:
        #   {"1": ["ikinciyi secme aldik"], "2": [...]}
        "fav_select": {},
        # "<session name> sec mahmut" -> switches to that conversation.
        "switch": [
            "sec mahmut", "gec mahmut", "secc mahmut",
            "oturumu sec mahmut", "konusmayi sec mahmut", "sohbeti sec mahmut",
            "oturumuna gec mahmut", "konusmasina gec mahmut",
            "sec gec mahmut", "ac mahmut",
        ],
        # Turns listening on in "hey mahmut" mode.
        # NOTE: do NOT put the bare name here. find_wake searches INSIDE the
        # text, so a bare name would treat commands like "... tamam mahmut" as
        # a wake phrase and swallow the message.
        "wake": [
            "hey mahmut", "ey mahmut", "selam mahmut", "merhaba mahmut",
            "baksana mahmut", "gunaydin mahmut",
        ],
    },
    "tts": {
        "enabled": True,
        "voice": "Yelda",
        "rate": 210,
        # Reading volume (0.0 - 2.0). Any value other than 1.0 renders the
        # speech to a file and plays it with `afplay -v` (a small extra delay).
        "volume": 1.0,
        # Two-voice reading (English terms spoken by a separate voice).
        # OFF BY DEFAULT: switching voices on every term breaks the flow and
        # each segment adds about a second of dead time. While off, the main
        # voice reads English words too (with local phonetics, but seamlessly).
        # Set it to true to try it.
        "bilingual": False,
        "voice_en": "Samantha",
        "rate_en": 200,                 # words per minute
        "max_chars": 1200,           # upper limit read from a single message
        "say_code_placeholder": "kod bloğu",
        # Mute the microphone while reading. OFF BY DEFAULT: with it off you
        # can stop the reading by saying "mahmut kes". Only cut/stop/start
        # commands are processed while reading, so the app's own voice cannot
        # send a message by accident.
        # If you listen through SPEAKERS and the echo bothers you, set it to
        # true (then you stop reading from the menu instead of by voice).
        "duck_mic_while_speaking": "auto",
        # Close the microphone STREAM while reading (only when the mic and
        # the speaker are the same wireless device). While a stream is open
        # macOS can hold AirPods in the HFP profile and playback crackles.
        # MEASURED: on AirPods Pro 3 an open microphone alone does not drop
        # the profile and the sound stays clean, so this is OFF by default;
        # being able to say "kes" during a reading is worth more.
        # "auto" (release on a shared device) | true | false (default)
        "release_mic_while_speaking": False,
        "mic_cooldown_ms": 400,
        # Announce which conversation a message came from before reading it.
        #   "always"    -> on every message
        #   "on_change" -> only when the conversation changes
        #   "never"     -> never
        "announce_session": "always",
        "announce_template": "{name} mesajını okuyorum.",
        # Pause after the announcement before the content starts
        "announce_pause_ms": 500,
        # Join the segments into one file and play them seamlessly (needs ffmpeg)
        "seamless": True,
        # Spoken confirmation template for "cevap mahmut"
        "reply_template": "{dative} cevap veriyorsun.",
        # The sample sentence the panel's "test" button reads
        "voice_test_text": "Merhaba, Claude mesajlarını böyle okuyacağım.",
        "listen_reply": "Dinliyorum.",
        # When "mahmut basla" is said while already listening
        "already_listening_reply": "Zaten açığım, dinliyorum.",
        # When "mahmut dur" is said while already stopped
        "already_stopped_reply": "Zaten durmuştum.",
        # Spoken feedback for conversation switching
        "select_reply": "{name} seçildi.",
        "resume_opening": "{name} kapalı, açıyorum.",
        "resume_done": "{name} açıldı ve seçildi.",
        "resume_failed": "{name} açılamadı.",
        "not_found_reply": "{name} bulunamadı.",
        # Reading the numbered list
        "list_lead": "Listeyi okuyorum.",
        "list_item": "{no} {name}",
        "list_closed_suffix": ", kapalı",
        "list_empty": "Liste boş.",
        # Silence inserted between parts. Punctuation gives no reliable
        # pause: measured, a period produced none at all in most places, and a
        # comma paused AFTER the number and glued the name to the next one.
        "list_pause_sec": 0.35,
        "sleep_reply": "Tamam, durdum."  ,
    },
    # GLOBAL shortcut that stops reading (works with the app in the
    # background). "cmd+alt+k" was chosen (k for "kes" = cut). Plain Cmd+K is
    # taken everywhere (browser address search, clearing a terminal, command
    # palettes); adding Alt leaves it free. The event is not swallowed, so an
    # unused combination is required.
    "shortcuts": {
        "stop_reading": "cmd+alt+k",
    },
    "inject": {
        # "claude" | "codex" - picked in the panel (Settings > Coding app)
        "target": "claude",
        "bundle_id": "com.anthropic.claudefordesktop",
        "activate_delay_ms": 160,    # wait for the app to come to the front
        # Bringing the target forward can take longer when sending a shortcut
        # (Electron windows focus late)
        "hotkey_activate_delay_ms": 400,
        # true: post the shortcut DIRECTLY to the target process (focus does
        # not move). Some applications IGNORE those events, so the default is
        # false: the app is brought forward briefly, the key is pressed and
        # focus is handed back.
        "direct_post": False,
        "paste_delay_ms": 90,        # wait between Cmd+V and Enter
        "restore_focus": True,       # return to the previous app after sending
        "restore_clipboard": True,
        "press_enter": True,
        # Wait for the session switch to settle after "cevap mahmut"
        "switch_settle_ms": 700,
        # Hand focus back to the app you were in after switching conversations.
        # Set it to false to let the screen stay on Claude (to watch it).
        "restore_focus_after_switch": True,
        "switch_restore_delay_ms": 700,
    },
# Application shortcuts triggered by voice.
    # The target app is brought forward briefly, the key is pressed and focus
    # returns to where you were. To add a shortcut, add an entry here; no code
    # change is needed.
    #
    # Example: toggle a meeting app's microphone by voice. Find your app's
    # bundle id with `osascript -e 'id of app "YourApp"'`.
    #
    # NOTE: most apps expose the microphone as a TOGGLE; "on" and "off" press
    # the same key. If the app does not publish its microphone state, the real
    # state cannot be read, so the spoken confirmation follows the command YOU
    # said. Each group carries its own reply and panel label.
    "hotkeys": [],

    "ui": {
        # Which state to start in:
        #   "sleep"  -> microphone ON but only "mahmut basla" is listened for
        #               (recommended)
        #   "listen" -> straight into active listening
        #   "off"    -> microphone fully off (cannot be opened by voice, use
        #               the menu)
        "start_mode": "sleep",
        "wake_word_mode": True,      # wait for "hey mahmut"
        # macOS notifications. Off: the panel and spoken replies are enough.
        "notifications": False,
        "notify_on_send": False,
        # The control panel served in a browser (127.0.0.1 only)
        "panel_enabled": True,
        "panel_port": 8765,
        # The loaded command set (langpacks.py). "Reset" reloads it.
        "langpack": "tr",
        # Numbered quick-access list. Read aloud with "listeyi getir mahmut"
        # and selected with "birinci sec mahmut". Editable from the panel.
        "favorites": [
            "Kunaz Reklam",
            "Kunaz Geliştirme",
            "Saint Panel",
            "Ses Kontrolü",
            "Pam Geliştirme",
            "Portal Geliştirme",
        ],
        # How many "recently heard" rows the panel keeps
        "history_size": 200,
        # Clear the buffer after this many seconds with no addition (0 = off)
        "buffer_timeout_sec": 180,
        # How long to wait for a reopened conversation to appear in the list
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
        except Exception as exc:  # broken json -> carry on with the defaults
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
        """Updates one setting and writes config.json so it persists."""
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
        """Updates a top-level value and writes it to disk."""
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
        """Returns a top-level value as-is (it may be a list)."""
        with self._lock:
            return self.data.get(name, default)

    def get(self, section: str, key: str, default=None):
        with self._lock:
            return self.data.get(section, {}).get(key, default)
