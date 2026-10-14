# Mahmut: Voice Assistant

*[English](README.md) · **Türkçe***

*v1.0.0 — [changelog](CHANGELOG.md)*

Claude Code ile **sesli** konuşmak için macOS (Apple Silicon) menubar uygulaması.

> Uygulamanın adı **Mahmut: Voice Assistant** — menü çubuğunda ve Dock'ta kısa
> haliyle "Mahmut", uyandırma kelimesiyle aynı. Markalı bir ad kullanılmıyor,
> depo adında "Claude" geçmesi gerekmez.

Arka planda çalışır: sen başka bir pencerede gezinirken konuşursun, telsiz usulü
"tamam mahmut" deyince mesaj gider. Gelen cevaplar — **kod blokları hariç** —
hangi konuşmadan geldiği söylenerek sesli okunur.

Her şey yerelde çalışır; ses hiçbir yere gönderilmez. İmza/notarization yok.

> **Bağımsız bir projedir.** Anthropic ile bir ilişkisi, ortaklığı veya onayı
> yoktur. "Claude" ve "Claude Code" Anthropic'in markalarıdır; burada yalnızca
> hangi uygulamayla çalıştığını belirtmek için geçer.

Lisans: [MIT](LICENSE).


## Güvenlik

**Hiçbir anahtar, token veya kimlik bilgisi yok.** Mahmut Claude'un API'sine
bağlanmaz; mesajı tıpkı senin gibi *pencereye yazar* (pano + ⌘V + Enter).
Dolayısıyla depoda ya da `config.json`'da API anahtarı bulunmaz, hesabına
erişemez, oturum çerezi okumaz.

**Dışarı hiçbir şey gitmez.** Uygulama kodunda tek bir ağ çağrısı yok; ses
Whisper ile cihazda yazıya çevrilir. Tek indirme, kurulumda modelin
Hugging Face'ten çekilmesi.

**Neye erişiyor:**

| | ne için |
|---|---|
| Mikrofon | konuşmanı yazıya çevirmek |
| Erişilebilirlik | mesajı Claude penceresine yazmak, uygulama kısayolu göndermek |
| `~/.claude/projects/**.jsonl` | gelen cevapları okumak (yalnızca okuma) |
| `~/.claude/sessions/*.json` | açık konuşmaların adı/kimliği |

Erişilebilirlik izni güçlüdür: bu izinle bir uygulama her yere tuş gönderebilir.
Kodun tamamı açık; `inject.py` bu iznin kullanıldığı tek yerdir.

**Yerel panel.** `127.0.0.1`'e bağlanır, dışarıdan erişilemez. Yine de
tarayıcıdaki herhangi bir site `text/plain` ile preflight'sız POST atıp komut
çalıştırabilirdi; bu yüzden yabancı `Origin` başlığı olan istekler **403** ile
reddedilir (kendi sayfası ve terminal/curl çalışır).

**Diskte kalan veri** — hepsi `.gitignore`'da, repoya gitmez:
`config.json` (ayarlar + konuşma adları), `.state.json` (son duyulanlar,
200 satırlık arşiv), `.app.log`, `.muted.json`.

**Kod tarafı:** `shell=True`, `eval`, `exec`, `pickle` kullanılmıyor; tüm
`subprocess` çağrıları liste argümanlı. AppleScript'e yalnızca sayısal `pid`
geçer. `claude://` deep link'lerindeki oturum kimliği biçim olarak doğrulanır
(`[A-Za-z0-9_-]{1,64}`), böylece `~/.claude` altına bozuk bir değer yazılsa
bile `open` beklenmedik bir URL şemasını açamaz.

## Kurulum (başka bir Mac'e)

```bash
git clone <repo-adresi> mahmut && cd mahmut
```

Sonra Finder'da klasörü aç ve **`Kur.command`** dosyasına çift tıkla. Terminal
açılır, kurulum kendi kendine ilerler:

1. Homebrew yoksa sorar ve kurar
2. `portaudio` + `ffmpeg`, ardından `python@3.13`
3. sanal ortam + python paketleri (`requirements.txt`)
4. Whisper modeli (~1.5 GB, ilk sefer)
5. `Mahmut.app` derlenir ve başlatılır
6. Erişilebilirlik ayar penceresi açılır — izni verirsin
7. "Açılışta otomatik başlasın mı?" diye sorar

Gereken: **Apple Silicon** (M serisi) + macOS 13+. Kurulum bittiğinde
`./selftest.py` her şeyi tek tek kontrol eder.

### İmza / sertifika

Hiçbir Apple Developer hesabı, Developer ID veya kurum sertifikası
kullanılmaz; keychain'e dokunulmaz. Uygulama **ad-hoc** imzalanır
(`codesign --sign -`, `TeamIdentifier=not set`) ve bunu `build_app.sh` her
derlemeden sonra doğrular — imza ad-hoc değilse imzayı kaldırır.

Uygulama indirilmiş bir ikili değil, **senin makinende derlenir**; bu yüzden
"geliştirici doğrulanamadı" uyarısı çıkmaz. ZIP olarak indirdiysen macOS
karantina bayrağı koyabilir: `Kur.command` ilk iş onu temizler, ama ilk çift
tıklamada engellenirse dosyaya **sağ tık > Aç** de (`git clone` ile indirirsen
bu adım hiç gerekmez).

### Kurulumu doğrulama

Kurulum, projenin temiz bir kopyasında (venv ve `config.json` olmadan) baştan
sona çalıştırılarak test edildi: paketler, model, bundle derleme, başlatma.
İki tuzak çıktı ve ikisi de düzeltildi:

- `codesign -dv ... | grep -q` **yanıltıcı**: `grep -q` eşleşince erken çıkıyor,
  `codesign` SIGPIPE alıyor ve `set -o pipefail` yüzünden pipeline başarısız
  sayılıyor. İmza doğruyken "ad-hoc değil" deyip imzayı siliyordu. Çıktı önce
  değişkene alınıyor.
- `codesign -dv --verbose=2` çıktısında `Signature=adhoc` satırı güvenilir
  değil; kontrol `--verbose=4` ile yapılıyor.

### Güncelleme

```bash
git pull && ./setup.sh
```

`setup.sh` yeniden çalıştırmak güvenli: kurulu paketlere dokunmaz, `config.json`
korunur (eksik ayarlar eklenir), bundle gerçekten değişmediyse yeniden
derlenmez — yani **izinler sıfırlanmaz**.

---


## Ne yapabiliyor

| Komut | Ne olur |
|---|---|
| ***"mahmut başla"*** | Dinlemeye başlar, *"Dinliyorum."* der |
| ***"mahmut dur"*** | Dinlemeyi durdurur, *"Tamam, durdum."* der |
| ***"mahmut kes"*** | Sadece **o anki okumayı** keser — dinleme sürer, kuyruktaki sıradaki mesaj okunur |
| ***"mahmut mikrofon"*** | toplantı uygulaması'daki mikrofonu açar/kapatır (⇧⌘A gönderir) |
| ***"listeyi getir mahmut"*** | Numaralı listeyi sesli okur |
| ***"birinci seç mahmut"*** | Listedeki 1. konuşmaya geçer (kapalıysa açar) |
| *"hey mahmut"* | Dinlemeyi açar (menubar düğmesi de var) |
| *…konuş… **"tamam mahmut"*** | Konuştuğun her şey Claude'a gider |
| *"**Backend Refactor** seç mahmut"* | Sol taraftaki o konuşmaya geçer |
| *"cevap mahmut"* | Sana en son okunan mesajın konuşmasını hedefler |
| *"boşver mahmut"* | Tamponu siler, mesaj gitmez |

**Zamanlanmış görevler (routines) okunmaz.** Tespit isimden değil, kaynaktan
yapılıyor: routine tarafından başlatılan bir oturumun transcript'i şu izi taşır —

```json
"origin": {"kind": "task-notification", "subkind": "scheduled-trigger"}
```

Normal konuşmalarda bu iz yok. Oturum üst verisi (`kind`, `nameSource`, `cwd`)
routine'leri ayırt **etmiyor** — hepsi `interactive`/`user` görünüyor, hatta
routine'ler gerçek oturumlarla aynı klasörde çalışıyor. Transcript izi tek
güvenilir sinyal.

Bu yüzden **yeni eklediğin routine'ler adı ne olursa olsun otomatik susturulur**.
Kapatmak için `config.json` → `watch.mute_routines: false`.

Ad bazlı `watch.exclude_patterns` listesi de yedek olarak duruyor. Ayrıca
menubar > **Sesli okunacaklar** altından herhangi bir konuşmayı tek tıkla açıp
kapatabilirsin (seçimin `.muted.json`'a yazılır, yeniden başlatınca korunur).

Ayrıca **tüm açık konuşmalar** aynı anda dinlenir. Bir cevap geldiğinde
önce *"Backend Refactor mesajını okuyorum."* denir, kısa bir duraklamadan
sonra içerik okunur — anons ayrı bir `say` çağrısı olduğu için cümleyle
birbirine karışmaz. Aynı anda birkaç
konuşmadan cevap gelirse hepsi tek kuyruğa girer, sırayla okunur.

Türkçe-İngilizce karışık konuşma hem **anlamada** hem **okumada** desteklenir:
İngilizce terimler İngilizce telaffuzla (Samantha), Türkçe iskelet Türkçe sesle
(Yelda) okunur.

---

## Kurulum

```bash
./setup.sh
open Mahmut.app
```

İki izin gerekiyor:

| İzin | Niye | Nerede |
|---|---|---|
| **Mikrofon** | Konuşmanı duymak | Açılışta dialog → "İzin ver" |
| **Erişilebilirlik** | Claude'a yazıp Enter'a basmak | Sistem Ayarları > Gizlilik ve Güvenlik > Erişilebilirlik |

```bash
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
```

> **İzin takılırsa** (listede açık görünüyor ama uygulama "izin yok" diyor):
> kayıt bayatlamıştır. Açıp kapatmak düzeltmez, kaydı sıfırlamak gerekir:
>
> ```bash
> tccutil reset Accessibility com.erengunes.mahmut
> ```
>
> Sonra uygulamayı yeniden başlat; izin dialogu temiz olarak yeniden çıkar.

Doğrulama:

```bash
./verify.sh                              # her şeyi kontrol et + yazma testi
./.venv/bin/python selftest.py --mic     # 6 sn konuş, ne anladığını göster
```

### Açılışta otomatik başlatma

```bash
./install_autostart.sh
```

macOS her açıldığında ClaudeVoice başlar. Ayrıca 5 dakikada bir kontrol edilir —
uygulama çökerse geri getirilir.

```bash
./install_autostart.sh --status    # durumu gör
./install_autostart.sh --remove    # kaldır
```

İki tasarım kararı, ikisi de deneyerek bulundu:

- **Başlatıcı script `~/Library/Application Support/ClaudeVoice/` altına yazılır**,
  proje klasörüne değil. Proje `~/Desktop` altında ve macOS orayı TCC ile koruyor;
  launchd oradaki bir scripti çalıştıramıyor (`Operation not permitted`, exit 126).
- **Uygulama `open -a` ile başlatılır**, ikili doğrudan çalıştırılmaz. Böylece
  LaunchServices üzerinden açılır ve Erişilebilirlik/Mikrofon izinleri geçerli
  kalır — test edildi, launchd'nin başlattığı örnekte `ax_trusted: true`.

Alternatif olarak Sistem Ayarları > Genel > Giriş Öğeleri > `+` > `Mahmut.app`
da kullanılabilir, ama o yolda çökme sonrası geri getirme olmaz.

---

## Kullanım

| Simge | Anlamı |
|---|---|
| ⚪️ | Kapalı (menubar düğmesi) — mikrofon hiç açık değil |
| 😴 | Durduruldu (`"mahmut dur"`) — mikrofon açık ama **sadece** `"mahmut başla"` dinleniyor |
| 🎙 | Açık, `"hey mahmut"` bekliyor |
| 🔴 7 | Dinliyor, tamponda 7 kelime |
| 🔊 | Cevap okunuyor (*"mahmut kes"* ile kesebilirsin) |

**İki ayrı "kapalı" var ve farkı önemli:**

- **⚪️ Kapalı** menubar düğmesiyle olur, mikrofonu tamamen kapatır. Sesle
  açılamaz — çünkü mikrofon kapalıyken seni duyamaz.
- **😴 Durduruldu** `"mahmut dur"` ile olur, mikrofon açık kalır ama konuştuğun
  hiçbir şey işlenmez. `"hey mahmut"`, `"tamam mahmut"`, `"seç mahmut"` —
  hiçbiri çalışmaz. Sadece `"mahmut başla"` seni geri açar.

**Akış:** menubar > *Dinleme: Açık* (ya da *"hey mahmut"*) → normal konuş,
durakla, devam et (hiçbir şey gitmez) → **"tamam mahmut"**.

Konuşurken Claude arka planda olabilir. Mesaj giderken odak ~300ms Claude'a
geçer, sonra bulunduğun uygulamaya **geri döner** — test edildi, Finder öndeyken
yazıp odağı Finder'a iade ediyor.

### Cevaplama senaryosu

```
🔊  "Backend Refactor mesajını okuyorum."  …  "Migration çalıştı, 3 tablo güncellendi."
🗣  "cevap mahmut"
🔊  "Backend Refactor'ye cevap veriyorsun."
🗣  "güzel, şimdi indexleri de ekle tamam mahmut"
    → mesaj Backend Refactor konuşmasına gider (oraya otomatik geçilir)
```

### Telsiz kelimeleri

| Amaç | Söyleyeceklerin |
|---|---|
| **Başlat** | "mahmut başla", "başla mahmut", "mahmut beni dinle", "mahmut uyan" |
| **Durdur** | "mahmut dur", "dur mahmut", "mahmut bekle", "mahmut mola" |
| **Okumayı kes** | "mahmut kes", "kes mahmut", "mahmut sus", "mahmut yeter" |

> Okuma sürerken **sadece** kes/dur/başla komutları işlenir. Uygulama
> kısayolları (ör. "mahmut mikrofon aç") okuma bitene kadar çalışmaz — bu
> bilinçli: okunan metnin içinde komut adı geçerse kendini tetiklemesin diye.
| **Gönder** | "tamam mahmut", "mahmut tamam", "gönder mahmut", "yolla mahmut", "over" |
| **Cevapla** | "cevap mahmut", "cevapla mahmut", "yanıtla mahmut" |
| **Konuşma seç** | "`<ad>` seç mahmut", "`<ad>` geç mahmut" |
| **İptal** | "iptal mahmut", "boşver mahmut", "sil mahmut" |
| **Uyandır** | "hey mahmut", "selam mahmut", "merhaba mahmut" |

Çağrı adı **Mahmut** — kasıtlı olarak Türkçe bir isim. Whisper Türkçe modunda
"Claude"u sürekli Clod/Cloud/Klot/Kılot diye yazıyordu; "Mahmut" tek şekilde
yazılıyor. Bonus: artık konuşurken "Claude" diyebilirsin, komut tetiklenmez.

Eşleştirme yine 1 harf hataya toleranslı (Mahmud, Mamut, Marmut hepsi tutar).
Sadece "tamam" demek mesajı **göndermez** — sonunda "mahmut" da olmalı.

Adı değiştirmek istersen `config.json` → `phrases.name` + `phrases.name_variants`
ve kalıplardaki kelimeyi birlikte güncelle; menü ve durum metinleri addan
türetildiği için kendiliğinden uyar.

Konuşma adı eşleştirmesi de toleranslı: *"vois kontrol"* → `Voice Control`,
*"admin"* → `Admin Paneli`. Alakasız bir isim söylersen eşleşmez, en
yakın adayı söyler.

### Türkçe-İngilizce karışık

**Anlamada** düzeltme tek katmanda yapılır: Whisper çıktısı bir terim
sözlüğünden geçer (`bajkenddeki → backend'deki`, `dojker → docker`,
`stagginge → staging'e`, `kubernetis → kubernetes`). Düzeltme muhafazakârdır —
düz Türkçe cümlelere dokunmaz.

Whisper'a yazılımcı ağzıyla örnek cümleler veren bir `initial_prompt` da
denedim ve **kaldırdım** — ölçtüğümde zarar verdiği çıktı:

- Düz Türkçe'de hiçbir fayda sağlamadı (çıktılar birebir aynı)
- Karışık cümlede Türkçe kelimeyi İngilizce'ye itti: *"Şu backend'deki"* →
  `"Shubach kenddeki"`
- Sessizlikte prompt'un kendisini geri okudu (`"API response"`, `"JSON"`) —
  bu da "İngilizce'ye çeviriyor" izlenimi veriyordu

Denemek istersen `config.json` → `stt.initial_prompt` alanına
`claudevoice/config.py` içindeki `DEV_PROMPT` metnini koyabilirsin.

**Okumada** tek ses kullanılır (Yelda). İngilizce terimleri de o okur —
Türkçe fonetikle, ama **kesintisiz**.

İngilizce terimleri ayrı bir İngilizce sesle okutmayı denedim ve kapattım:
her terimde ses değiştirmek akıcılığı bozuyor, ayrıca her parça ayrı bir `say`
çağrısı demek ve her çağrı ~1 saniye ölü zaman ekliyor (7 parçalı bir cümlede
7 saniye). Denemek istersen `config.json` → `tts.bilingual: true`.

Okunmadan önce metinden ayıklananlar: kod blokları, tablolar, dosya yolları,
URL'ler, emoji, markdown işaretleri (`**`, `#`, `` ` ``, `|`) ve sesli
okunmasının anlamı olmayan işaretler — `--`, `—`, `->` gibi tireler ve oklar
virgüle çevrilir (doğal duraklama), geri kalanı atılır.

---

## Kaynak kullanımı (ölçüldü, M serisi)

| Durum | CPU | Bellek |
|---|---|---|
| Boşta (dinleme kapalı) | **%0.9** | 432 MB |
| Dinliyor (mikrofon + VAD) | **+%0.14** (8 çekirdeğin toplamında) | — |
| Cümle çözümleme | **0.05–0.12 sn CPU** / cümle | — |

Çözümleme 5.3 sn'lik bir cümleyi 1.05 sn'de bitiriyor (5x gerçek zaman) ama
bunun neredeyse tamamı **GPU'da** (MLX/Metal) — CPU'ya düşen pay 0.1 saniyeden
az. Yani fan dönmez, pil yemez.

Asıl maliyet bellek: `large-v3-turbo` ağırlıkları ~430 MB tutuyor. Düşürmek
istersen `config.json` → `stt.model` → `mlx-community/whisper-small-mlx`
(~150 MB, Türkçe'de belirgin şekilde daha zayıf).

---

## Uygulama kısayolları (sesle)

Başka uygulamalara klavye kısayolu gönderebilir. Hedef uygulama kısa süreliğine
öne alınır, tuş basılır, odak kaldığın uygulamaya **geri verilir** — test edildi,
Claude öndeyken toplantı uygulaması'a kısayol gitti ve odak Claude'a döndü.

Hazır gelen tek kayıt toplantı uygulaması mikrofonu:

> *"mahmut mikrofon"*, *"mahmut mikrofon aç"*, *"mahmut mikrofonu kapat"*,
> *"mikrofon aç mahmut"* …

Hepsi aynı tuşa basar (⇧⌘A bir **anahtar**), ama sesli teyit söylediğin
komuta göre verilir: *"aç"* → **"Mikrofon açıldı."**, *"kapat"* →
**"Mikrofon kapatıldı."**, düz *"mahmut mikrofon"* → **"Mikrofon değiştirildi."**

Gerçek durumu okuyup ayırt etmek mümkün değil: toplantı uygulaması mikrofon durumunu
erişilebilirlik ağacında yayınlamıyor (arayüzünü ve menü çubuğu girişini
yokladım, ikisi de boş geliyor).

Kısayol gönderimi hedef uygulamayı kısa süreliğine öne alır, tuşa basar, odağı
iade eder. Öne gelemezse **tuş gönderilmez** — yoksa kısayol o an önde olan
uygulamaya düşer (bir keresinde Chrome'a ⇧⌘A gidip sekme arama paneli açtı).

Yeni kısayol eklemek için `config.json` → `hotkeys` listesine bir kayıt ekle,
kod değiştirmen gerekmez:

```json
{
  "name": "Slack sessize al",
  "bundle_id": "com.tinyspeck.slackmacgap",
  "key": "m",
  "modifiers": ["shift", "command"],
  "phrases": ["mahmut slack sessiz", "slack sessiz mahmut"],
  "reply": "Slack sessize alındı."
}
```

`bundle_id`'yi bulmak için:

```bash
osascript -e 'id of app "Uygulama Adı"'
```

Desteklenen tuşlar: `a`–`z`, `0`–`9`, `space`, `return`, `escape`, `tab`,
`delete`, yön tuşları, `f1`–`f12`. Değiştiriciler: `cmd`, `shift`, `alt`, `ctrl`.

---

## Ayarlar

`config.json` (menubar > *Ayarları aç*). Değişiklikten sonra yeniden başlat.

| Alan | Varsayılan | Ne yapar |
|---|---|---|
| `phrases.listen` / `sleep` | — | "mahmut başla" / "mahmut dur" kalıpları |
| `phrases.send` / `reply` / `switch` / `cancel` / `wake` | — | Diğer komut kelimeleri |
| `tts.listen_reply` / `sleep_reply` | `Dinliyorum.` / `Tamam, durdum.` | Sesli teyitler |
| `tts.voice` / `rate` | `Yelda` / `210` | Türkçe ses ve hız |
| `ui.favorites` | 6 konuşma | Numaralı hızlı erişim listesi |
| `tts.volume` | `1.0` | Okuma ses seviyesi (0.0–1.0) |
| `tts.list_pause_sec` | `0.35` | Liste öğeleri arasındaki sessizlik |
| `ui.resume_timeout_sec` | `45` | Kapalı konuşma açılırken beklenecek süre |
| `watch.mute_routines` | `true` | Zamanlanmış görevleri okuma (transcript izinden tespit) |
| `watch.exclude_patterns` | "her sabah", "günlük"… | Ek olarak, adında bunlar geçenleri de okuma |
| `tts.duck_mic_while_speaking` | `false` | `true` → okuma sırasında mikrofonu kapat (sözle kesemezsin) |
| `tts.bilingual` | `false` | `true` → İngilizce terimleri ayrı sesle oku (akıcılığı bozar) |
| `tts.voice_en` / `rate_en` | `Samantha` / `200` | Yukarısı açıkken kullanılacak İngilizce ses |
| `tts.announce_pause_ms` | `500` | Anons ile içerik arasındaki duraklama |
| `tts.seamless` | `true` | Çok parçalı okumayı tek dosyada birleştirip kesintisiz çal |
| `tts.announce_session` | `always` | `on_change` → sadece konuşma değişince söyle, `never` → hiç |
| `tts.announce_template` | `{name} mesajını okuyorum.` | Anons şablonu |
| `tts.max_chars` | `1200` | Tek mesajda okunacak üst sınır |
| `audio.vad_ratio` | `3.2` | Gürültülü ortamda yükselt (5–6) |
| `audio.silence_ms` | `700` | Cümle arası duraklama toleransı |
| `ui.wake_word_mode` | `true` | `false` → "hey mahmut" demeden dinle |
| `ui.start_listening` | `false` | `true` → açılışta mikrofon açık |
| `inject.press_enter` | `true` | `false` → yazar ama göndermez |

---

## Nasıl çalışır

```
mikrofon ─> VAD ─> MLX Whisper ─> sözlük ─> tampon
                     (GPU)        düzeltme     │
                                               ├─ "claude start/stop" ─> dinlemeyi aç / durdur
                                               ├─ "tamam mahmut" ─> pano+Cmd+V+Enter ─> Claude.app
                                               ├─ "<ad> seç mahmut" ─> claude://code/continue?session=…
                                               └─ "cevap mahmut" ─> hedef oturumu hatırla

~/.claude/sessions/*.json      ─> hangi konuşmalar açık, adları ne
~/.claude/projects/*/*.jsonl   ─> TÜMÜ paralel izlenir
         │
         └─> markdown + işaret temizle ─> say (Yelda)
             "<ad> mesajını okuyorum."  ─ 0.5 sn ─  içerik
```

**Neden pano?** Claude.app Electron. Accessibility ile metin alanına doğrudan
değer yazmak React state'ini güncellemiyor. Pano + Cmd+V her sürümde çalışır.

**Neden transcript dosyası?** Claude Code cevabı zaten `~/.claude/projects/`
altına yazıyor. Ekran kazımaya gerek yok; `thinking` blokları ve araç çağrıları
doğal olarak elenir.

**Konuşma değiştirme AX gerektirmez.** Claude.app'in kendi deep link'i
(`claude://code/continue?session=local_…`) kullanılıyor — uygulamanın kendi
tepsi menüsünün kullandığı yol.

**Okuma sırasında mikrofon açık kalır** ki *"mahmut kes"* diyebilesin. Claude'un
kendi sesini duyup mesaj göndermesini engellemek için, okuma sürerken **yalnızca**
kes / dur / başla komutları işlenir; duyulan başka her şey yok sayılır.

Hoparlörden dinliyorsan ve yankı rahatsız ediyorsa `tts.duck_mic_while_speaking`
değerini `true` yap — o zaman okuma sırasında mikrofon tamamen kapanır, okumayı
sözle kesemezsin (menüden *Okumayı kes* ile kesersin).

---

## İzinler hakkında bilinmesi gereken

Uygulama ad-hoc imzalı. Ad-hoc imza **sabit kimlik vermez** — imza, ikilinin
hash'ine bağlıdır. `Mahmut.app/Contents/MacOS/ClaudeVoice` her yeniden
derlendiğinde Erişilebilirlik izni geçersiz olur.

Pratikte sorun değil: Python kodu bundle'ın **dışında** durur ve mutlak yolla
çağrılır, yani kodu istediğin kadar değiştirirsin — bundle'a dokunulmaz.
`build_app.sh` idempotenttir, gerçekten gerekmedikçe derlemez
(zorlamak için `./build_app.sh --force`).

Launcher'ı yeniden derlemen gerekirse: `tccutil reset Accessibility
com.erengunes.mahmut` → uygulamayı başlat → izni yeniden ver.

---

## Ses kalitesi ve mikrofon seçimi

**Varsayılan: kulaklık mikrofonu.** Masadan uzaktayken dahili mikrofon seni
duymaz, kulaklık duyar. Kulaklık takılıp çıkarıldığında mikrofon ~5 saniye
içinde kendiliğinden değişir.

Bedeli: Bluetooth kulaklıkta mikrofon açılınca macOS kulaklığı HFP (hands-free)
profiline düşürür ve **oynatma** kalitesi bozulabilir ("patlak" ses). Hep masada
çalışıyorsan ve bu rahatsız ediyorsa dahili mikrofona geç:

```jsonc
"audio": {
  "prefer": "headset",   // "builtin" = dahili mikrofon, "system" = sistem varsayılanı
  "device": null         // ya da "airpods" gibi isim parçası / cihaz indeksi
}
```

Dahili mikrofon çok daha kısık kaydediyor (tepe ~0.006 vs AirPods ~0.08).
Bunun için iki telafi var: ses Whisper'a verilmeden önce hedef seviyeye
yükseltiliyor (`stt.normalize`) ve VAD alt sınırı buna göre ayarlı
(`audio.vad_min_rms`). Yine de kısık mikrofonda tanıma bir miktar düşer —
"kes" gibi üç harfli komutlar "test" diye duyulabilir; o durumda
*"mahmut sus"* veya *"mahmut yeter"* de.

## voice panel

```
http://127.0.0.1:8765
```

Menubar > **Kontrol panelini aç**. Sadece yerel arayüze bağlanır, dışarıdan
erişilemez. Saniyede bir yenilenir.

| Bölüm | Ne var |
|---|---|
| **Okuma** | Açık/kapalı anahtarı, *Okumayı kes*, ses seviyesi kaydırağı (%0–100) |
| **Dinleme** | Başla · Dur · Mikrofonu kapat · Mikrofonu yenile |
| **Kısayollar** | Mikrofon aç / kapat / değiştir (ve `hotkeys`'e eklediklerin) |
| **Tampon** | Ne biriktiğini gösterir, elle gönder/temizle |
| **Liste** | Numaralı hızlı erişim — sırala (↑↓), geç, çıkar, ekle |
| **Son duyulanlar** | Son 200 metin, sağında hangi komutu tetiklediği. Yeşil = komut çalıştı |
| **Açık konuşmalar** | Tek tıkla geç, 🔊/🔇 ile sesli okumayı aç/kapat |
| **Durum** | İzin, mikrofon cihazı, sinyal seviyesi, kuyruk, **CPU ve bellek** |

Ses kaydırağı **okuma sürerken** de çalışır: ses blok blok çalınıyor ve her
blokta güncel seviye okunuyor, yani kaydırağı oynattığın an (~43 ms) uygulanır.

**Son duyulanlar** bölümünde her satırın sağındaki **+** düğmesiyle yanlış
duyulan bir cümleyi komut setine ekleyebilirsin. Komutu seç, sonra:

- **Kelimeleri ekle** — cümleyi komutun aynı uzunluktaki kalıbıyla hizalar ve
  farklı kelimeleri yazım setine alır. Örnek: *"Mahmut, çeşit"* + `kes` →
  `çeşit` kelimesi `kes` setine girer ve **başka cümlelerde de tutar**.
- **Cümleyi ekle** — kelime sayısı hiçbir kalıpla tutmuyorsa (cümle çok
  bozulmuşsa) tamamı kalıp olarak eklenir. Örnek: *"listeyi getir Mahmut"*
  → *"Yüce 3 yi ten mamut"* gibi kurtarılamaz durumlar için.

`config.json` anında güncellenir ve kalıplar yeniden derlenir — uygulamayı
yeniden başlatmaya gerek yok.

Bir satıra tıkla →
panoya kopyalanır, *Hepsini kopyala* ile tüm liste `saat  metin  → sonuç`
biçiminde alınır. Yeni bir yanlış duyma görürsen `config.json` →
`phrases.word_variants` altındaki ilgili kelimenin listesine ekle.

## Mikrofon ve hoparlör seçimi

**Ayarlar > Ses ve dil** altında iki açılır liste var. Varsayılan ikisinde de
**Otomatik**:

| Seçim | Davranış |
|---|---|
| Mikrofon: Otomatik | Kulaklık varsa kulaklık mikrofonu, yoksa dahili (`audio.prefer`) |
| Mikrofon: belirli cihaz | Kulaklık takılsa bile o cihazda kalır. Seçtiğin cihaz ortada yoksa otomatiğe düşer, sistem sağır kalmaz |
| Hoparlör: Otomatik | Sistem çıkışı |
| Hoparlör: belirli cihaz | Okuma o cihazdan çalar. Cihaz yoksa sistem varsayılanına döner |

Seçim `audio.device` ve `audio.output_device` olarak saklanır; isim parçası da
yeterli (`"airpods"`), indeks de verilebilir. Belirli bir **çıkış** seçilince
okuma her zaman render yolundan geçer — `say` süreci sistem çıkışına çalar,
cihaz seçimini dinlemez.

`./test_devices.py` bu kuralları ses donanımı olmadan, sahte cihaz listesiyle
test eder (12 durum: otomatik seçim, açık seçim, cihaz yokken düşme, indeksle
seçim, tam ad önceliği, geçersiz seçim).

## Bluetooth kulaklıkta cızırtı

Okuma AirPods'ta cızırtılı geliyordu. Teşhis için çal-dinle ile tek tek eledik:

| test | sonuç |
|---|---|
| `afplay` ile tek parça | temiz |
| `sounddevice` ile tek parça | temiz |
| 9 parçalı birleştirme, `afplay` | temiz |
| uygulamanın ffmpeg çıktısı, `afplay` | temiz |
| **uygulamanın kendi okuması** | **cızırtılı** |

Suçlu kendi çalma yolumuzdu: sesi blok blok biz yazıyorduk (seviye kaydırağı
canlı çalışsın diye) ve Whisper aynı anda çalışırken bu döngü altta kalıp
tampon açlığı yaratıyordu. `afplay` ayrı bir süreç, CoreAudio tamponunu kendi
yönetiyor.

- Ses seviyesi **%100** ve seçili çıkış sistem varsayılanıysa → `afplay`
- Seviye %100'ün altındaysa → kendi yolumuz (afplay çalarken seviye
  değiştirilemiyor)
- Kendi yolumuz bir kez hata verirse bir daha denenmiyor (`_play_broken`)

**PortAudio -9986:** panelden çıkış cihazı olarak aynı Bluetooth kulaklık
seçilince `sounddevice` o cihazı açamıyor (giriş olarak zaten açık) ve her
mesajda `Internal PortAudio error` verip afplay'e düşüyordu. Seçilen çıkış
zaten sistem varsayılanıysa artık PortAudio hiç açılmıyor.

> Yanlış teşhis: önce mikrofon akışının HFP'ye düşürdüğünü sanıp okuma
> boyunca akışı kapatmıştık. Ölçtük: AirPods Pro 3'te mikrofon **açıkken de**
> ses temiz. `audio.release_mic_while_speaking` varsayılanı `false` yapıldı,
> okuma sürerken sesli "kes" yine çalışıyor.

### Eski not: profil değişimi

AirPods takılıyken okuma cızırtılı geliyordu. Sebep yazılım hatası değil,
macOS'un profil değiştirmesi: **mikrofon akışı açık olduğu sürece** giriş ve
çıkış aynı kablosuz cihazsa macOS A2DP'den HFP'ye düşüyor, oynatma dar bantlı
ve bozuk oluyor. Aynısı Shazam'da da yaşanır — dinlemeyi açınca ses
dandikleşir, dinleme bitince düzelir.

Çözüm de oradan: okuma boyunca mikrofon **akışı kapatılıyor** (sadece kısılmış
değil), okuma bitince geri açılıyor. Akış kapanınca macOS A2DP'ye döner.

- `audio.release_mic_while_speaking`: `"auto"` (varsayılan) yalnızca giriş ve
  çıkış **aynı kablosuz cihazsa** bırakır; dahili mikrofonda hiç dokunmaz.
  `true` her zaman, `false` hiç.
- Arka arkaya gelen mesajlarda mikrofon tekrar tekrar açılıp kapanmaz:
  yeniden açma zamanlayıcısı okuma sürerken iptal edilir.
- Boştaki cihaz taraması (`_check_mic`) bu sırada mikrofona dokunmaz.

**Bedeli:** okuma sürerken mikrofon kapalı olduğu için *"mahmut kes"* sesli
komutu o anda duyulmaz. **⌥⌘K** kısayolu ve paneldeki "Okumayı kes" düğmesi
her zaman çalışır. Sesle kesebilmeyi cızırtıya tercih edersen ayarı `false`
yap.

## Kendi sesini duyması (hoparlör yankısı)

Kulaklıksız çalışırken mikrofon, Mahmut'un **kendi okuduğunu** duyuyor. Gerçek
vakada şu oldu: cevabımda `tamam mahmut` yazıyordu → Mahmut onu sesli okudu →
mikrofon duydu → gönder komutu tetiklendi ve **kullanıcının yazmadığı bir mesaj
Claude'a gitti**. Arşivdeki "Mahmut test" satırları da kullanıcının değil,
uygulamanın kendi sesiydi (`test` kelimesi `kes` yazım setinde).

Çözüm — mikrofonu kapatmak değil (hoparlörle de konuşabilmek gerekiyor),
**metin düzeyinde ayıklamak**:

- `Speaker.current_text` o an okunan metni tutar, `recent_text()` okuma
  bittikten sonra da **8 sn** boyunca verir. Bu şart: son ses parçası okuma
  bittikten ~1 sn sonra yazıya çevriliyor, `speaker.busy` o anda `False`
  olduğu için yankı tam korumasız geçiyordu.
- `_is_own_voice()` duyulan kelimeleri okunan metinde **ardışık alt dizi**
  olarak arar (`word_eq` ile toleranslı). Sadece "kelimelerin çoğu geçiyor"
  demek yetmiyor: okunan metinde "mahmut" ve "kes" ayrı ayrı geçerse
  kullanıcının gerçek `mahmut kes` komutu da yok ediliyordu.
- Eşleşirse hiçbir komut çalışmaz, arşivde `🔇 kendi sesi` olarak görünür.

`tts.duck_mic_while_speaking`: `"auto"` (varsayılan) mikrofonu **kapatmaz**,
yalnızca yukarıdaki metin filtresine güvenir. `true` dersen klasik davranış
döner (okuma boyunca mikrofon kapalı, ama o zaman okuma sürerken
"mahmut kes" de diyemezsin). `audio.output_is_loud()` çıkışın hoparlör mü
kulaklık mı olduğunu söyler (giriş/çıkış aynı cihazsa kulaklık sayılır).

> Kalan sınır: okunan metin `mahmut kes` ifadesini **aynen ve ardışık**
> içeriyorsa, o sırada sen de "mahmut kes" dersen bastırılır. Gerçek akustik
> echo cancellation olmadan bu ayrılamıyor; panel ve menubar'daki "Okumayı
> kes" düğmeleri her durumda çalışır.

### "+" ile kelime ekleme (arşivden)

Arşivdeki bir satırın `+` düğmesi, duyulan cümleyi komutun kalıbıyla **hizalayıp**
farklı kelimeleri yazım setine atar. İki gerçek hata çıktı, ikisi de düzeltildi:

1. **"6.yi seç Mahmut." hizalanamıyordu.** `tokenize` noktada bölüyordu:
   `['6','yi','sec','mahmut']` → 4 kelime, kalıp 3 kelime → "4 kelimelik kalıp yok".
   Kelime **içindeki** nokta/kesme artık bölmüyor: `6.yi → 6yi`,
   `Mahmut'un → mahmutun`. Cümle sonundaki nokta hâlâ ayrılır
   (`"Merhaba. Nasılsın" → ['merhaba','nasilsin']`). Bu sadece ekleme değil,
   **tanımayı da** düzeltti: "6.yi seç Mahmut." artık doğrudan `fav:6` tutuyor.
2. **Yanlış kalıba yapıştırma.** Aday diziler yalnızca "aynı uzunlukta kalıp yok"
   iken üretiliyordu. `send` içinde tek kelimelik `over` olduğu için
   "tamammahmut" 1 kelime sayılıp **"over"in yazımı** diye ekleniyordu. Artık
   komşuları birleştirme/bölme adayları her zaman üretilip en çok tutan seçiliyor
   (`tamammahmut → tamam|mahmut`, zaten tutuyor).

Hepsi zaten tutuyorsa artık kırmızı "eklenecek yeni kelime yok" değil, yeşil
"zaten tutuyor — bu cümle bu komutu tetikliyor" yazıyor.

### Bildirimler (toast)

Durum metni header'da duruyordu ve uzun mesajlar (örn. "'tamam namık' →
'send' komutuna eklendi") şeridi taşırıyordu. Artık header'da sadece durum
ikonu var; mesajlar **sağ üstten balon** olarak çıkıp 4.5 sn sonra kayboluyor,
en fazla 3 tane üst üste durur. Renk metne göre seçilir (`TKIND`):
kırmızı = hata/çakışma, yeşil = eklendi/kaydedildi, camgöbeği = dinliyorum,
sarı = duraklatıldı/kesildi, gri = nötr.

> Ölçülen tuzak: giriş animasyonu `opacity` oynatırsa, sekme arka plandayken
> tarayıcı çizim yapmadığı için animasyon ilk karede (opacity 0) donup kalıyor
> ve bildirim **hiç görünmüyor**. Bu yüzden animasyon sadece `transform`
> oynatıyor, `requestAnimationFrame` da kullanılmıyor.

### Hedef uygulama (Ayarlar > Kod uygulaması)

- **Claude Code** (`com.anthropic.claudefordesktop`) — varsayılan, tam destek.
- **GPT Codex (ChatGPT)** (`com.openai.codex`) — listede görünür ama
  **seçilemez** (`TARGETS[...]["enabled"] = False`); henüz denenmedi.

Codex'in ayrı bir masaüstü uygulaması yok: `/Applications/ChatGPT.app`'in
bundle id'si zaten `com.openai.codex` (eski uygulama "ChatGPT Classic" =
`com.openai.chat`). Yazma/gönderme yolu aynı (pano + Cmd+V + Enter) olduğu için
muhtemelen çalışır; **okuma çalışmaz**, çünkü cevapları Claude'un
`~/.claude/projects/**.jsonl` transkriptlerinden okuyoruz, Codex'te o kaynak yok.

### Komut penceresi (Komutlar > Düzenle)

- **Ekleme kutusu en üstte**: kalıbı yazıp `Ekle`, ya da 🎙 ile söyleyerek ekle.
  Liste uzun olduğu için kutu altta kalınca her seferinde aşağı kaydırmak
  gerekiyordu.
- **Sonuç aynı pencerede** gösterilir ("🔴 'tamam mahmut' zaten 'send'
  kalıplarında"). Eskiden sadece sağ üstteki durum satırına düşüyordu, ilgisiz
  bir yerde görünüyordu. `/api/action` artık `{"ok":…, "msg":…}` döndürüyor.
- **Yazım setleri rozet olarak** listelenir, her birinin `×`'i vardır. Ana kelime
  (setin adı) camgöbeği ve `×`'siz: kaldırılırsa komut hiç eşleşmez.
- Aynı yazım iki kez görünmez (`_uniq`), eski config'lerdeki tekrarlar temizlenir.

### Sesle yakalama (🎙) neden sessiz kalıyordu

Okuma başlarken mikrofon kısılıyor (`mic.mute_for(3600)`, kendi sesini duymasın
diye). Yakalama o anki okumayı kesiyordu ama **kısma kalkmıyordu**; konuşmanın
hiçbir çerçevesi işlenmiyordu. Ayrıca mikrofon kapalıyken (`OFF`) STT döngüsü
sesi tamamen atıyordu. Şimdi yakalama açılınca:

1. okuma kuyruğu **bekletilir** (`Speaker.set_hold` — mesajlar silinmez),
2. mikrofon zorla açılır ve kısma anında kaldırılır (`unmute_after(0)`),
3. yakalama açıkken `_tts_started` mikrofonu kısmaz,
4. STT döngüsü `OFF` durumunda bile sesi işler.

Duyulan metin `.app.log`'a `[yakala]` satırı olarak düşer.

## Numaralı liste

`config.json` → `ui.favorites`. Panelden düzenlenir, değişiklik anında
kaydedilir ve sesli komut kalıpları yeniden derlenir.

> 🗣 *"listeyi getir Mahmut"* → *"Listeyi okuyorum."* · *"bir Mobil Uygulama"* ·
> *"iki Backend Refactor"* · *"üç Site Yenileme, kapalı"* …
>
> 🗣 *"birinci seç Mahmut"* → *"Mobil Uygulama seçildi."*

Liste okuma komutu **gevşek** eşleştirilir: kısa bir cümle "liste" ile
başlıyorsa, çağrı adı tanınmasa bile liste okunur. Gerekçesi ölçülmüş bir
durum — Whisper *"listeyi getir Mahmut"*u **"Listeyi yatırmamışım."** diye
yazdı, ikinci kelimede tanınacak hiçbir şey kalmamıştı. Liste okumak zararsız
olduğu için (mesaj gitmez, durum değişmez) burada gevşek davranmak güvenli.
Uzun cümleler tetiklemez: *"listeyi güncelledikten sonra bana haber ver"*
komut sayılmaz. `phrases.list_loose_max_tokens: 0` ile kapatılır.

Her sıra için beş söyleyiş kabul edilir: `birinci seç Mahmut`, `birinci Mahmut`,
`bir seç Mahmut`, `1 seç Mahmut`, `Mahmut birinci`.

**Kapalı bir konuşma seçilirse önce açılır:**

> *"Site Yenileme kapalı, açıyorum."* → (birkaç saniye) → *"Site Yenileme açıldı ve seçildi."*

Bunun için Claude'un kendi deep link'i kullanılır
(`claude://code/resume?session=<uuid>`) ve **oturum kimliği korunur** — yeni bir
konuşma açılmaz, aynısı devam eder. Kapalı konuşmaların kimliğini bulmak için
arka planda bir başlık indeksi çalışır (418 transcript ~0.3 sn'de taranır,
5 dakikada bir yalnızca değişenler yenilenir).

Deep link bazen sessizce düşüyor (uygulama meşgulse); bir kez daha deneniyor.

### Liste neden parça parça okunuyor

Noktalama ile doğru duraklama elde edilemiyor. Ölçtüm:

- `"bir, Mobil Uygulama. iki, …"` → duraklama **sayıdan sonra** (0.29 sn'de), isim
  bir sonraki sayıya yapışıyor
- `"bir Mobil Uygulama. iki …"` → öğeler arası duraklama **tamamen kayboluyor**
  (Yelda bu bağlamda noktada duraklamıyor)

Bu yüzden her öğe ayrı ses parçası olarak basılıp aralarına **gerçek sessizlik**
(`tts.list_pause_sec`, varsayılan 0.35 sn) konuyor, hepsi tek dosyada
birleştirilip çalınıyor.

## Durdurma

```bash
./stop.sh
```

`say` ve `afplay` **ayrı süreçlerdir** ve uygulama ölse bile okumaya devam
ederler. Doğrudan `pkill python` yaparsan ses yetim kalıp konuşmayı sürdürür
(üst üste binen yetimler "patlak" ses de yapar). `stop.sh` hepsini kapatır.

Uygulama kendi de korur: `SIGTERM`/`SIGINT` alınca okuyan süreci öldürür, ve her
açılışta önceki çalışmadan kalan yetimleri temizler (`.tts.pids` dosyasından).
Sadece `kill -9` durumunda yetim kalır, o da bir sonraki açılışta temizlenir.

## Panel'i değiştirirken

`panel.py` içindeki `PAGE` çalışan sürecin belleğinden servis edilir. Sayfayı
düzenledikten sonra **uygulamayı yeniden başlatmadan** tarayıcıyı yenilemek eski
HTML'i gösterir (bir kez bu yüzden "düzelttim" sanıp eski CSS'i test ettim).
Sıra: `./check_panel.sh` → `./stop.sh && open Mahmut.app` → yenile.

## Okumayı kesen kısayol

Varsayılan **⌥⌘K** (k = kes) — her yerde çalışır, uygulama arkada olsa da. Panelden
değiştirilir (Ayarlar > Okumayı kes kısayolu, `cmd+alt+.` yazımıyla).

Seçim kriteri: `NSEvent` genel izleyicisi olayı **yutmaz**, tuş basımı öndeki
uygulamaya da gider. Bu yüzden boşta bir kombinasyon şart:

| Kombinasyon | Durum |
|---|---|
| `⌘K` | Chrome/Safari adres araması, Terminal ekran temizleme, Slack/Notion/VS Code komut paleti |
| `⌘L` | Tarayıcılarda adres çubuğuna atlar |
| `⌘B` | Her editörde kalın yazı, Xcode'da Build |
| `⌃Space`, `⌃⌥Space` | macOS giriş kaynağı değiştirme |
| `⇧⌘.` | Finder'da gizli dosyalar |
| **`⌥⌘K`** | **boşta** — seçilen kısayol (yalın `⌘K` dolu, `⌥` eklenmiş hali değil) |
| **`⌥⌘.`**, **`⌃⌥` + harf** | **boşta** — alternatifler |

Olayı gerçekten yutmak için `CGEventTap` gerekir; o zaman da o kısayol **tüm**
uygulamalardan çalınır (örn. `⌘L` ile artık adres çubuğuna gidemezsin), bu
yüzden tercih edilmedi.

## Panel portu

- Port doluysa panel **sıradaki boş portu** dener (`8765` → `8766` … `+9`,
  sonra rastgele). Eskiden hiç açılmıyordu ve bunu sadece logdan anlardın.
- Ayarlar > Panel portu: yazdığın anda `/api/portcheck` boş mu dolu mu söyler
  (yeşil/kırmızı), boşsa sağdaki **Kaydet** aktifleşir.
- Kaydedince panel uygulamayı kapatmadan yeni porta taşınır ve açık sayfa
  kendiliğinden yeni adrese gider. Taşıma, yanıt gönderildikten 0.6 sn sonra
  yapılır; yoksa cevabı taşıyan bağlantı kapanıp tarayıcı hata gösterir.

## Bundle: Python neden içeride

Eski launcher, bundle'ın **dışındaki** venv python'unu `exec` ediyordu. O anda
sürecin bundle'ı `Python.app` oluyor; Dock'ta "Python" + roket ikonu görünüyor,
`CFBundleName`'i çalışma anında değiştirmek de yalnızca menü çubuğunu
düzeltiyordu (`lsappinfo` doğru ismi gösterse bile Dock karesi diskteki
bundle'dan okuyor).

Şimdi launcher `libpython`'a bağlanıp **kendi içinde** `Py_BytesMain` çağırıyor:
ayrı süreç yok, sürecin bundle'ı `Mahmut.app`. Dock'ta isim ve robot ikonu
doğru. Python kodu hâlâ bundle'ın dışında (`APP_ROOT`, venv site-packages
derleme sırasında gömülür), yani kodu değiştirmek imzayı bozmaz.

### Tek kopya kilidi

`LSUIElement` kalktığı için her süreç artık Dock'ta **ayrı bir kare** açıyor.
`verify.sh` testi `open -n` (yeni kopya) ile çalıştığından ve LaunchAgent 5
dakikada bir kontrol ettiğinden Dock'ta üst üste Mahmut ikonları birikti.
İki önlem:

- `_single_instance()` — `.app.lock` içinde pid tutar; canlı bir kopya varsa
  yeni süreç hemen çıkar (`[tek kopya] zaten calisiyor`). Çıkışta kilit silinir.
- `_dock_hide()` — `--test-inject`, `--probe-ax`, `--test-hotkey` gibi tek
  seferlik modlar `NSApplicationActivationPolicyProhibited` ile hiç kare açmaz.

### Bundle değişince izinler sıfırlanır

Ad-hoc imza cdhash tabanlı: launcher veya Info.plist değişirse Erişilebilirlik
(ve mikrofon) izni geçersiz olur. Bundle id de `com.erengunes.mahmut` →
`com.erengunes.mahmut` oldu. Yeniden vermek gerekir:
Sistem Ayarları > Gizlilik ve Güvenlik > Erişilebilirlik > `+` > `Mahmut.app`.
`build_app.sh` gerçekten değişiklik yoksa bundle'a dokunmaz (fingerprint).

### Ürün hali için eksikler

Şu an bundle **taşınabilir değil**: `APP_ROOT` ve venv yolu derlemede gömülü,
Whisper ağırlıkları da `~/.cache/huggingface` altında. Başka makinede
çalışması için bağımlılıkların ve modelin .app içine paketlenmesi
(py2app/PyInstaller + model dosyası) ve ilk açılışta izin anlatan bir ekran
gerekir.

## İsim ve ikon

- `assets/robot.svg` → neon robot; `make_icon.py` bunu `assets/Mahmut.icns`,
  `icon.png` ve menubar PNG'lerine çevirir (pyobjc ile render, ek bağımlılık yok).
- İkon **bundle'ın içine kopyalanmaz**. Kopyalansa imza mührü bozulur ve
  Erişilebilirlik izni gider. Bunun yerine açılışta
  `NSApplication.setApplicationIconImage_()` ile atanır.
- macOS uygulamayı normalde `org.python.python` (yani "Python") diye gösteriyordu;
  çünkü launcher, bundle dışındaki venv python'unu çalıştırıyor. `_brand()`
  `NSBundle.mainBundle().infoDictionary()` içindeki `CFBundleName` alanını
  değiştirerek bunu düzeltiyor. Doğrulama: `lsappinfo list | grep Mahmut`.
- İkonu değiştirmek istersen SVG'yi düzenle, `./.venv/bin/python make_icon.py`
  çalıştır, uygulamayı yeniden başlat. Dock ikonu önbelleklenmez.

## Sorun giderme

| Belirti | Çözüm |
|---|---|
| Menubar simgesi yok | `./run.sh` ile terminalden çalıştır, hatayı gör |
| "Erişilebilirlik izni yok" ama listede açık | `tccutil reset Accessibility com.erengunes.mahmut` sonra yeniden başlat |
| Mesaj gidiyor ama boş | Claude'da imleç yazma alanında değil; composer'a bir kez tıkla |
| Konuşuyorum, tampon boş | `audio.vad_ratio`'yu düşür (2.5) |
| Ortam gürültüsü mesaj yapıyor | `audio.vad_ratio`'yu yükselt (5–6), `wake_word_mode` aç |
| Konuşma adı bulunamıyor | Menubar > *Konuşmalar* ile elle geç; adı kısalt ("portal" yeter) |
| İngilizce terimler Türkçe okunuyor | `claudevoice/bilingual.py` → `_EN_WORDS`'e ekle |
| İngilizce okuma rahatsız ediyor | `config.json` → `tts.bilingual: false` |
| Çözümleme yavaş | `stt.model` → `mlx-community/whisper-small-mlx` |
| Uygulama açılınca ses "patlak" oluyor | Kulaklık mikrofonu HFP'ye düşürüyor — `audio.prefer_builtin: true` (varsayılan) olmalı |
| Kapattım ama hâlâ okuyor | `pkill` yerine `./stop.sh` kullan |
| Komut hiç tepki vermiyor | `.app.log` dosyasına bak — açılışta yüklenen kısayol sayısı ve hatalar orada |
| Saçma metinler tampona giriyor | Whisper halüsinasyonu; filtre var ama `audio.vad_ratio`'yu yükseltmek de yardımcı olur |

## Bilinen sınırlar

- Mesaj gönderilirken odak kısa süre Claude'a geçer; o anda yazıyorsan tuşların kaybolur.
- Pano gönderim anında geçici değişir, ~250 ms sonra eski içeriği geri yüklenir.
- Sadece **çalışan** konuşmalar izlenir ve geçilebilir (kapalı olanlar listede olmaz).
- Her `say` çağrısı ~1 sn ölü zaman getirir. Bu yüzden okuma en fazla iki
  parçaya bölünür (anons + içerik); içerik kendi içinde tek parçadır.
- 😴 durduruldu modunda konuşma yine çözümlenir (uyandırma kelimesini duymak
  için). Uzun süre hiç kullanmayacaksan menubar düğmesiyle tamamen kapat.
