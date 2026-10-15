<div align="center">

<img src="https://raw.githubusercontent.com/saintsun/mahmut-voice-assistant-macos/main/assets/icon.png" width="128" alt="Mahmut">

# Mahmut: Voice Assistant

**Claude Code ve GPT Codex ile konuşarak çalış.**

Konuştuğunu yazıya çevirip uygulamaya yazar, gelen cevapları sesli okur.
Her şey bilgisayarında çalışır, ses hiçbir yere gönderilmez.

![platform](https://img.shields.io/badge/platform-macOS%2013%2B-111?style=flat-square)
![chip](https://img.shields.io/badge/i%C5%9Flemci-Apple%20Silicon-111?style=flat-square)
![ücret](https://img.shields.io/badge/%C3%BCcret-yok-00c853?style=flat-square)
![license](https://img.shields.io/badge/lisans-MIT-111?style=flat-square)

*[English](README.md) · **Türkçe***

*v1.1.0, [değişiklikler](CHANGELOG.md)*

</div>

---

## Kurulum: tek komut

Terminal'i aç (⌘ + Boşluk → "Terminal" yaz → Enter), aşağıdaki satırı
kopyalayıp yapıştır ve Enter'a bas:

```bash
curl -fsSL https://raw.githubusercontent.com/saintsun/mahmut-voice-assistant-macos/main/install.sh | bash
```

Hepsi bu. Toplam 10-15 dakika sürer, çoğu indirme beklemesi. Sorarsa **E**
yazıp Enter'a bas; sonunda uygulama kendiliğinden açılır.

---

## Mahmut'a ısmarla

Proje ücretsiz ve öyle kalacak. Faydalı bulduysan Mahmut'un karnını
doyurabilirsin.

[![Payoneer](https://img.shields.io/badge/Payoneer-Mahmut'a%20%C4%B1smarla-FF4800?style=for-the-badge&logo=payoneer&logoColor=white&labelColor=0D1117)](https://link.payoneer.com/Token?t=B8694A2C126D470EAE34E7CC7A0817D9&src=pl)
[![GitHub Sponsors](https://img.shields.io/badge/GitHub-Sponsor%20ol-39FF14?style=for-the-badge&logo=githubsponsors&logoColor=white&labelColor=0D1117)](https://github.com/sponsors/saintsun)

| | |
|---|---|
| $5 | Bir türk kahvesi |
| $10 | Döner ekmek |
| $25 | İskender |
| $50 | Nargile |
| $100 | Pavyon |

Payoneer'da tutarı sen yazıyorsun, kart ile ödeniyor. GitHub Sponsors
butonu profil onaylandığında devreye girer.

---

## Kurulumun ayrıntıları

Komut gereken her şeyi kendisi indirir ve kurar:

| | |
|---|---|
| Proje dosyaları | `~/Mahmut` klasörüne iner (git gerekmez) |
| Homebrew, PortAudio, FFmpeg, Python | eksikse kurulur |
| Konuşma tanıma modeli | 1.5 GB, en uzun adım bu |
| Uygulama | derlenir ve başlatılır |

**Gereken:** Apple Silicon Mac (M1/M2/M3/M4) ve macOS 13+. Bir de Claude Code
veya Codex masaüstü uygulaması kurulu olmalı.
*Mac'im uygun mu:* sol üstteki  > Bu Mac Hakkında > "Yonga" satırında
"Apple M..." yazıyorsa evet.

<details>
<summary>Terminal kullanmak istemiyorum</summary>

[ZIP olarak indir](https://github.com/saintsun/mahmut-voice-assistant-macos/archive/refs/heads/main.zip),
çift tıklayıp aç, çıkan klasördeki **`Kur.command`** dosyasına çift tıkla.
Açılmazsa dosyaya sağ tık → **Aç** → yine **Aç**.
</details>

### Kurulumdan sonra: iki izin

macOS iki izin soracak, ikisi de şart.

**Mikrofon:** ilk konuşmada çıkan pencerede **İzin Ver**.

**Erişilebilirlik:** yazdığı metni Claude'un penceresine yapıştırabilmesi
için. Kurulum sonunda ayar penceresi kendiliğinden açılır; açılmazsa:

```bash
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
```

Listede **Mahmut**'u bul, anahtarı **aç**. Listede yoksa `+` düğmesiyle
`~/Mahmut/Mahmut.app` dosyasını ekle. Sonra bir kez kapatıp aç:

```bash
cd ~/Mahmut && ./stop.sh && open Mahmut.app
```

### İlk konuşma

Claude Code'u aç, bir sohbete gir, sonra sırayla:

1. **"Mahmut başla"** diyince dinlemeye başlar
2. Ne istiyorsan söyle: *"Şu fonksiyondaki hatayı düzelt, testleri de ekle"*
3. **"tamam Mahmut"** diyince mesaj gider

Cevap geldiğinde sesli okur. Kesmek için **"Mahmut kes"** ya da **⌥⌘K**.

---

## Ne yapıyor?

- **Sen konuşuyorsun, o yazıyor.** Başka bir pencerede çalışırken bile.
  Mesajı sen "tamam Mahmut" deyince gönderiyor, sustuğun an değil.
- **Cevapları sesli okuyor.** Kod bloklarını atlayarak, hangi konuşmadan
  geldiğini söyleyerek.
- **Birden çok konuşmayı takip ediyor.** "Kunaz Reklam seç Mahmut" deyince
  oraya geçiyor, "cevap Mahmut" deyince en son konuşana yazıyor.
- **Bedava ve tamamen bilgisayarında.** API anahtarı yok, hesap yok, abonelik
  yok. İnternet bile gerekmiyor (ilk kurulumdan sonra).

| | |
|---|---|
| ![Kontrol paneli](https://raw.githubusercontent.com/saintsun/mahmut-voice-assistant-macos/main/docs/screenshots/kontrol.png) | ![Komut listesi](https://raw.githubusercontent.com/saintsun/mahmut-voice-assistant-macos/main/docs/screenshots/komutlar.png) |

---

## Her şey hazır, şimdi ne yapmalıyım?

**Kurulumdan sonraki ilk iş: komutları kendi sesinle öğret.** Bu adımı atlama;
konuşma tanıma senin telaffuzunu ilk seferde tam tutturamaz.

1. Menü çubuğundaki simgeye tıkla → **Panel**
2. Üstteki **Komutlar** sekmesine geç
3. Bir komutun yanındaki **Düzenle**'ye bas
4. 🎙 düğmesine basıp komutu **kendi söylediğin gibi** söyle
5. Duyduğu şey ekranda çıkar; doğruysa **Ekle**'ye bas

En çok kullandığın beş komut için bunu yap (başla, dur, kes, gönder, cevap).
Beş dakika sürer, isabet gözle görülür şekilde artar.

---

## Günlük kullanım

| Ne dersen | Ne olur |
|---|---|
| **"Mahmut başla"** | Dinlemeye başlar |
| *(konuş)* **"tamam Mahmut"** | Söylediklerin mesaj olarak gider |
| **"Mahmut iptal"** | Biriken metni siler, mesaj gitmez |
| **"Mahmut kes"** | Okumayı susturur |
| **"Mahmut dur"** | Dinlemeyi durdurur (okuma devam eder) |
| **"cevap Mahmut"** | En son konuşan sohbete geçip yazar |
| **"Kunaz Reklam seç Mahmut"** | O konuşmaya geçer |
| **"listeyi getir Mahmut"** | Kayıtlı konuşmaları numaralı okur |
| **"birinci seç Mahmut"** | Listeden 1 numarayı açar |
| **⌥⌘K** | Okumayı keser (her uygulamadan) |

Her komutun birden çok söyleniş biçimi var ("Mahmut sus", "Mahmut yeter" de
okumayı keser). Hepsini panelden görebilir, yenisini ekleyebilirsin.

---

## Kontrol paneli

Menü çubuğu simgesi → **Panel**, ya da tarayıcıda `http://127.0.0.1:8765`

| Sekme | İçinde ne var |
|---|---|
| **Kontrol** | Dinleme/okuma anahtarları, ses seviyesi, son duyulanlar listesi |
| **Komutlar** | Komut kalıpları, konuşma listen, açık sohbetler |
| **Ayarlar** | Çağrı adı, mikrofon, hoparlör, dil, ses, kısayol, kod uygulaması |

**Son duyulanlar** kutusu en işe yarar yer: ne duyduğunu ve ne yaptığını
gösterir. Bir komut tutmadıysa orada görürsün; satırın yanındaki **+** ile o
yanlış duymayı komuta ekleyebilirsin.

---

## Claude Code mu, Codex mi?

İkisi de destekleniyor. **Ayarlar → Kod uygulaması**'ndan seç.

Panel ikisini birden gösterir: seçili olan etkin, diğeri altta soluk durur.

**Codex seçtiğinde:** konuşmalar proje adıyla listelenir. Codex'te "Kunaz"
projesi altındaki "Reklam" sohbeti, listede **"Kunaz Reklam"** olarak görünür;
sesle seçerken de böyle söylersin. Varsayılan listeye sadece projelerin altındaki
sohbetler girer; "Recents" altındakileri istersen elle eklersin.

İki uygulamanın listesi ve ayarları ayrı tutulur; arada geçiş yapman bir şeyi
bozmaz.

---

## Bir şey çalışmıyorsa

**Hiç duymuyor.** Menü çubuğu simgesine bak: ⚪️ kapalı, 😴 uyku, 🔴 dinliyor.
Uyku modundaysa "Mahmut başla" de. Panelde mikrofon çubuğu konuşurken
oynamıyorsa Ayarlar'dan başka bir mikrofon seç.

**Duyuyor ama komutları tutmuyor.** Yukarıdaki "komutları öğret" adımını yap.
Panelde **Son duyulanlar** kutusuna bak: ne duyduğunu orada görürsün.

**Mesaj gitmiyor.** Erişilebilirlik izni verilmemiş olabilir. Kontrol et:

```bash
cd ~/Mahmut && ./selftest.py
```

**Cevapları okumuyor.** Panelde **Kontrol → Okuma** anahtarı açık mı? Bir de
o konuşma susturulmuş olabilir, **Açık konuşmalar** listesinde hoparlör
simgesine bak.

**Ses cızırtılı geliyor.** Ses seviyesini %100'e al; altındaki değerlerde
farklı bir çalma yolu kullanılıyor ve bazı Bluetooth kulaklıklarda cızırtı
yapabiliyor.

**Her şeyi kapat:**

```bash
cd ~/Mahmut && ./stop.sh
```

**Güncelle:**

```bash
cd ~/Mahmut && git pull && ./setup.sh
```

Güncelleme güvenlidir: ayarların, listen ve öğrettiğin yazımlar korunur.

---

## Bu branch: Gather entegrasyonu

`main` hiçbir uygulamaya özel kısayol taşımaz. Bu branch, Gather'in mikrofon
kısayolunu (⇧⌘A) sesle açıp kapatan kaydı varsayılanlara ekler:

> 🗣 *"Mahmut mikrofon aç"* → Gather öne alınır, ⇧⌘A gönderilir, odak sana
> iade edilir, *"Açıldı."* denir.

Gather mikrofon durumunu dışarıya vermediği için gerçek durum okunamıyor; tuş
bir anahtar olduğundan sesli teyit **söylediğin komuta** göre veriliyor. Kendi
kısayolunu eklemek için `config.json > hotkeys` yeterli.

## Ücret ve gizlilik

- **Hiçbir ücret yok.** API anahtarı, hesap, abonelik gerekmiyor.
- **Ses bilgisayardan çıkmıyor.** Konuşma tanıma Apple Silicon'ın GPU'sunda
  çalışıyor. Tek indirme, kurulumdaki model dosyası.
- Uygulama sadece şunlara erişir: mikrofon, Erişilebilirlik (yazabilmek için),
  ve Claude/Codex'in kendi konuşma dosyaları (okumak için).
- Kontrol paneli yalnızca `127.0.0.1`'e bağlanır; dışarıdan erişilemez.
- Kurulan uygulama **senin bilgisayarında derleniyor**, indirilmiş bir ikili
  dosya değil. Bu yüzden "geliştirici doğrulanamadı" uyarısı çıkmaz ve hiçbir
  geliştirici sertifikası kullanılmaz.

---

## Ayarlar

Panelden değiştirilebilen her şey `config.json` dosyasında saklanır. Sık
kullanılanlar:

```jsonc
{
  "audio": { "prefer": "headset", "device": null, "output_device": null },
  "stt":   { "language": "tr" },
  "tts":   { "voice": "Yelda", "enabled": true },
  "shortcuts": { "stop_reading": "cmd+alt+k" },
  "ui":    { "panel_port": 8765 }
}
```

**Çağrı adını değiştirmek:** Ayarlar → Çağrı adı. "Mahmut" yerine ne yazarsan
tüm komutlar ona taşınır. Türkçe olmayan kısa adlar (özellikle İngilizce
kelimeler) daha çok yanlış duyuluyor, uzun ve ayırt edici bir ad seç.

**Açılışta otomatik başlatma:**

```bash
cd ~/Mahmut && ./install_autostart.sh
```

---

## Kaldırma

Tek komut yeter:

```bash
cd ~/Mahmut && ./uninstall.sh
```

Ya da klasördeki **Kaldir.command** dosyasına çift tıkla.

| Sormadan silinir | Sana sorulur | Hiç dokunulmaz |
|---|---|---|
| Mahmut.app, Python ortamı, geçici dosyalar | kendi komut kalıplarının olduğu `config.json` | Homebrew ve paketleri (portaudio, ffmpeg, python) |
| Açılışta başlatma (launch agent) | konuşma modeli (~1.5 GB yer açar) | Claude Code / Codex ve konuşmaların |
| Mikrofon ve Erişilebilirlik kayıtları | proje klasörünün kendisi | |

Hiç soru sormadan:

```bash
./uninstall.sh --all     # model ve klasör dahil her şey
./uninstall.sh --keep    # sadece uygulama; ayarlar ve model kalsın
```

Homebrew paketlerine dokunulmuyor, çünkü başka programlar da kullanıyor.
Bilgisayarında başka hiçbir şey kullanmıyorsa:

```bash
brew uninstall portaudio ffmpeg
```

---

## Geliştiriciler için

Bu bölümden sonrası teknik: nasıl çalıştığı, ölçülen davranışlar ve
karşılaşılan tuzaklar.

### Akış

```
mikrofon → enerji VAD → MLX Whisper → sözlük düzeltme → tampon
                                        tampon sonunda "tamam mahmut" → ⌘V + Enter

~/.claude/projects/**.jsonl   ─┐
~/.codex/sessions/**.jsonl    ─┴→ takipçi → markdown temizleme → say → hoparlör
```

- **VAD** enerji tabanlı: uyarlanan gürültü tabanı, ön-tampon ve en az konuşma
  çerçevesi eşiği. Model yalnızca gerçekten konuşma olduğunda çalışır.
- **Halüsinasyon filtresi:** Whisper sessizlikte metin uyduruyor. Kara liste,
  sıkıştırma oranı (> 2.4 döngüye girmiş demek) ve prompt yankısı kontrolü.
- **Eşleştirme** Türkçe karakterleri ASCII'ye katlar, tekrar eden harfleri
  teke indirir, 4+ harfli kelimelerde 1 harf hata tolere eder, birleşmiş
  kelimeleri ayırır. Rakam içeren yazımlarda tolerans yoktur (`5inci` ≠ `1inci`).
- **Yazma** panoya kopyalar, hedefi öne alır (`CGWindowList` ile *doğrulayarak*,
  çünkü `NSRunningApplication` değerleri tazelenmiyor), ⌘V + Enter gönderir ve
  odağı geri verir.
- **Okuma** kod bloklarını, tabloları ve yolları atar, metni dil parçalarına
  böler, parçaları paralel render edip ffmpeg ile birleştirir.

### Codex nasıl okunuyor

| kaynak | içerik |
|---|---|
| `~/.codex/state_5.sqlite` → `threads` | ad, `cwd`, `rollout_path` (transkript) |
| `~/.codex/.codex-global-state.json` → `local-projects` | proje adı ve `rootPaths` |
| aynı dosya → `projectless-thread-ids` | projeye bağlı OLMAYAN konuşmalar |

Veritabanındaki `project_id` sütunu hep boş; proje eşleşmesi thread'in
`cwd`'sini projelerin `rootPaths` listesiyle karşılaştırarak bulunuyor, en uzun
eşleşen kök kazanıyor. `projectless-thread-ids` içindekiler yolu bir projenin
altında olsa bile projesiz sayılıyor.

Geçiş `codex://threads/<id>` deep link'iyle, okuma thread'in rollout
dosyasından. Takipçi iki biçimi de anlıyor: Claude'un
`assistant/message/content[text]` yapısı ve Codex'in
`response_item/payload/content[output_text]` yapısı.

Claude tarafında geçiş `claude://code/continue?session=<id>`, kapalı konuşmayı
açmak `claude://code/resume?session=<id>`. Oturum kimliği biçim olarak
doğrulanır (`[A-Za-z0-9_-]{1,64}`), böylece `~/.claude` altına bozuk bir değer
yazılsa bile `open` beklenmedik bir URL şemasını açamaz.

### Kaynak kullanımı (ölçüldü, M serisi)

| | |
|---|---|
| Boşta | bir çekirdeğin ~%0.9'u, 184–432 MB |
| Dinlerken | 8 çekirdeğin %0.14'ü |
| 5 sn'lik kaydı yazıya çevirme | ~1 sn süre, 0.05–0.12 sn CPU (gerisi GPU) |
| `say` başlangıç gecikmesi | çağrı başına ~1 sn |
| Çok parçalı render | 1.14 sn hazırlık, sonra kesintisiz çalma |

### Yol boyunca çıkan tuzaklar

**Kendi sesini duyuyordu.** Hoparlörle çalışırken mikrofon okunan metni
duyuyor. Gerçek vaka: cevabımda `tamam mahmut` yazıyordu, Mahmut onu sesli
okudu, mikrofon duydu ve **kullanıcının yazmadığı bir mesaj gitti.** Çözüm
mikrofonu kapatmak değil (hoparlörle de konuşabilmek gerekiyor), duyulan metni
okunan metinle **ardışık alt dizi** olarak karşılaştırmak. Sadece "kelimelerin
çoğu geçiyor" demek yetmiyordu: okunan metinde "mahmut" ve "kes" ayrı ayrı
geçerse gerçek komut da yutuluyordu. Koruma okuma bittikten sonra 8 sn daha
sürüyor, çünkü son ses parçası ~1 sn gecikmeli yazıya çevriliyor.

**Okuma cızırtılıydı.** Çal-dinle ile elendi: `afplay` her biçimde temiz
çalıyordu, cızırtı yalnızca kendi blok blok çalma yolumuzda vardı. Whisper
çalışırken o döngü altta kalıp tampon açlığı yaratıyor. Ses %100'ken artık
`afplay` kullanılıyor; blok yolu sadece canlı ses seviyesi değişimi için.
Ayrıca aynı Bluetooth cihazı hem giriş hem çıkış olarak seçilince PortAudio
`-9986` veriyordu; seçilen çıkış zaten sistem varsayılanıysa artık PortAudio
hiç açılmıyor.

**Takipçi sessizce ölüyordu.** `TranscriptWatcher._run` içindeki tek bir
istisna iş parçacığını öldürüyor, mesajlar hiç okunmuyor ve hiçbir yerde iz
kalmıyordu. Artık döngü hatayı loglayıp devam ediyor, ayrıca 10 saniyede bir
nöbetçi iş parçacığının yaşadığını kontrol edip ölmüşse yeniden başlatıyor.

**Whisper'ın `initial_prompt`'u zarar veriyordu.** Ölçüldü: düz konuşmada
hiçbir faydası yok, karışık cümlede Türkçe kelimeyi İngilizce'ye itiyor
("Şu backend'deki" → "Shubach kenddeki"), sessizlikte prompt'un kendisini geri
okuyor. Kapatıldı.

**`6.yi` iki kelimeye bölünüyordu**, 3 kelimelik kalıp hiç tutmuyordu. Kelime
içindeki nokta ve kesme artık bölmüyor (`Mahmut'un` → `mahmutun`), cümle
sonundaki nokta hâlâ ayırıyor.

**`codesign … | grep -q` yanıltıyor.** `grep -q` eşleşince erken çıkıyor,
`codesign` SIGPIPE ile ölüyor ve `set -o pipefail` yüzünden pipeline başarısız
sayılıyor: imza doğruyken "ad-hoc değil" deyip siliyordu.

**`say` ebeveyninden sonra yaşıyor.** Çalmayı bir alt sürece yaptırıyor, sadece
ebeveyni öldürmek sesi kesmiyordu. Artık kendi süreç grubunda çalışıyor ve grup
birden susturuluyor.

**Dock'ta kopyalar birikiyordu.** Bundle `LSUIElement` olmaktan çıkınca her
fazladan kopya kendi karesini açtı. Artık `.app.lock` içindeki pid ile tek
kopya zorlanıyor, tek seferlik CLI modları hiç kare açmıyor.

### Panel'i değiştirirken

`panel.py` içindeki `PAGE` çalışan sürecin belleğinden servis edilir. Sayfayı
düzenledikten sonra uygulamayı yeniden başlatmadan tarayıcıyı yenilemek eski
HTML'i gösterir. Sıra: `./check_panel.sh` → `./stop.sh && open Mahmut.app` →
yenile.

### Bundle ve imza

Launcher `libpython`'a bağlanıp **kendi içinde** `Py_BytesMain` çağırıyor; ayrı
süreç yok, sürecin bundle'ı `Mahmut.app`. Eskiden bundle dışındaki venv
python'u exec ediliyordu ve Dock'ta "Python" görünüyordu.

İmza **ad-hoc** (`codesign --sign -`): hiçbir Developer ID ya da kurum
sertifikası kullanılmaz, keychain'e dokunulmaz. `build_app.sh` bunu her
derlemeden sonra doğrular, ad-hoc değilse imzayı kaldırır.

Ad-hoc imza cdhash tabanlı olduğu için launcher ya da Info.plist değişirse
Erişilebilirlik izni geçersiz olur. `build_app.sh` gerçekten değişiklik yoksa
bundle'a dokunmaz; Python kodu bundle'ın dışında durduğu için kodu istediğin
kadar değiştirebilirsin.

### Testler

```bash
./test_devices.py   # cihaz seçimi kuralları (ses donanımı gerekmez)
./test_sources.py   # hedef, susturma ve rutin tespiti
./test_phrases.py   # komut eşleşmesi: ne tetikler, ne tetiklememeli
./selftest.py       # izinler, mikrofon, model, ses, canlı oturumlar
./check_panel.sh    # panel JavaScript sözdizimi
./verify.sh         # uygulamayı yeniden başlatır ve yazma yolunu dener
```

### Bilinen sınırlar

- Yalnızca Apple Silicon (MLX).
- Hedef uygulama açık olmalı.
- Bundle **taşınabilir değil**: proje yolu ve venv derlemede gömülü, model
  `~/.cache/huggingface` altında. Hazır indirilebilir bir sürüm için
  bağımlılıkların ve modelin .app içine paketlenmesi gerekir.
- Okunan metin durdurma komutunu **aynen ve ardışık** içeriyorsa, o sırada
  söylediğin komut bastırılır. Kısayol ve panel düğmesi her zaman çalışır.

---

## Lisans

[MIT](LICENSE) © Eren Güneş

Bağımsız bir projedir; Anthropic ya da OpenAI ile bir ilişkisi, ortaklığı veya
onayı yoktur. "Claude", "Claude Code", "Codex" ilgili şirketlerin markalarıdır
ve burada yalnızca hangi uygulamayla çalıştığını belirtmek için geçer.
