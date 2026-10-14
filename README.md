<div align="center">

<img src="https://raw.githubusercontent.com/saintsun/mahmut-voice-assistant-macos/main/assets/icon.png" width="128" alt="Mahmut">

# Mahmut: Voice Assistant

**Work with Claude Code and GPT Codex by talking.**

It turns your speech into text, types it into the app, and reads the replies
back out loud. Everything runs on your machine — no audio ever leaves it.

![platform](https://img.shields.io/badge/platform-macOS%2013%2B-111?style=flat-square)
![chip](https://img.shields.io/badge/chip-Apple%20Silicon-111?style=flat-square)
![cost](https://img.shields.io/badge/cost-free-00c853?style=flat-square)
![license](https://img.shields.io/badge/license-MIT-111?style=flat-square)

***English** · [Türkçe](README.tr.md)*

*v1.0.0 — [changelog](CHANGELOG.md)*

</div>

---

## Install — one command

Open Terminal (⌘ + Space → type "Terminal" → Enter), paste the line below and
press Enter:

```bash
curl -fsSL https://raw.githubusercontent.com/saintsun/mahmut-voice-assistant-macos/main/install.sh | bash
```

That is all. The command downloads and installs everything it needs:

| | |
|---|---|
| Project files | into `~/Mahmut` (git is not required) |
| Homebrew, PortAudio, FFmpeg, Python | installed if missing |
| Speech recognition model | 1.5 GB — the longest step |
| The app | built and launched |

It takes 10–15 minutes, mostly downloading. Answer **E** (yes) if it asks.

**Requirements:** an Apple Silicon Mac (M1/M2/M3/M4) and macOS 13 or newer,
plus the Claude Code or Codex desktop app.
*Is my Mac supported:*  > About This Mac > if "Chip" says "Apple M…", yes.

<details>
<summary>I would rather not use the Terminal</summary>

[Download the ZIP](https://github.com/saintsun/mahmut-voice-assistant-macos/archive/refs/heads/main.zip),
double-click to unpack it, then double-click **`Kur.command`** inside the
folder. If it will not open, right-click the file → **Open** → **Open** again.
</details>

### After installing: two permissions

macOS asks for two permissions; both are required.

**Microphone** — click **Allow** the first time you speak.

**Accessibility** — needed to paste the text into the app's window. The
settings pane opens by itself at the end of the install; if it does not:

```bash
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
```

Find **Mahmut** in the list and turn the switch **on**. If it is not listed,
press `+` and add `~/Mahmut/Mahmut.app`. Then restart it once:

```bash
cd ~/Mahmut && ./stop.sh && open Mahmut.app
```

### Your first message

Open Claude Code, enter a conversation, then:

1. Say **"Mahmut start"** — it starts listening
2. Say what you want: *"Fix the bug in that function and add tests"*
3. Say **"okay Mahmut"** — the message is sent

It reads the reply aloud. To stop the reading say **"Mahmut quiet"** or press
**⌥⌘K**.

> English and Turkish command sets both ship with the app. Pick yours under
> **Settings → Command set**, and change the name it answers to under
> **Settings → Wake name**.

---

## What it does

- **You talk, it types** — even while you work in another window. The message
  is sent when you say the sign-off phrase, never when you go quiet.
- **It reads replies aloud**, skipping code blocks and announcing which
  conversation they came from.
- **It follows several conversations** — "select Admin Panel Mahmut" switches
  to one, "reply Mahmut" writes back to whoever spoke last.
- **Free and fully local.** No API key, no account, no subscription. After the
  install it does not even need an internet connection.

| | |
|---|---|
| ![Control panel](https://raw.githubusercontent.com/saintsun/mahmut-voice-assistant-macos/main/docs/screenshots/kontrol.png) | ![Command list](https://raw.githubusercontent.com/saintsun/mahmut-voice-assistant-macos/main/docs/screenshots/komutlar.png) |
| ![Command editor](https://raw.githubusercontent.com/saintsun/mahmut-voice-assistant-macos/main/docs/screenshots/modal.png) | ![Settings](https://raw.githubusercontent.com/saintsun/mahmut-voice-assistant-macos/main/docs/screenshots/ayarlar.png) |

---

## Do this first: teach it your voice

**Right after installing, teach the commands in your own voice.** Do not skip
this step; speech recognition will not catch your pronunciation on the first
try.

1. Click the menu bar icon → **Panel**
2. Go to the **Commands** tab
3. Press **Edit** next to a command
4. Press 🎙 and say the command **the way you actually say it**
5. What it heard appears on screen; if it looks right, press **Add**

Do this for the five commands you use most (start, stop, quiet, send, reply).
It takes five minutes and the hit rate improves noticeably.

The same screen is where you add your own phrasings. Want "Howdy Mahmut" to
wake it up? Open the **Wake** command and add it — by typing, or by saying it.

---

## Everyday use

| You say | What happens |
|---|---|
| **"Mahmut start"** | starts listening |
| *(talk)* **"okay Mahmut"** | what you said is sent as a message |
| **"cancel Mahmut"** | clears the buffer, nothing is sent |
| **"Mahmut quiet"** | stops the reading |
| **"Mahmut stop"** | stops listening (reading continues) |
| **"reply Mahmut"** | switches to whoever spoke last and writes there |
| **"select Admin Panel Mahmut"** | switches to that conversation |
| **"list Mahmut"** | reads your saved conversations by number |
| **"first one Mahmut"** | opens number 1 from that list |
| **⌥⌘K** | stops the reading, from any application |

Every command accepts several phrasings. You can see them all in the panel and
add your own.

---

## The control panel

Menu bar icon → **Panel**, or open `http://127.0.0.1:8765` in a browser.

| Tab | What is in it |
|---|---|
| **Control** | listening and reading switches, volume, recently heard |
| **Commands** | command patterns, your conversation list, open conversations |
| **Settings** | wake name, microphone, speaker, language, voice, shortcut, target app |

**Recently heard** is the most useful box: it shows what was heard and what it
did. When a command does not land you will see why, and the **+** next to a row
adds that misrecognition to the command.

---

## Claude Code or Codex?

Both are supported. Pick one under **Settings → Coding app**.

The panel shows both: the selected one is live, the other sits below it, dimmed
and inert.

**With Codex selected**, conversations are listed under their project name. A
thread called "Reklam" inside the project "Kunaz" appears as **"Kunaz
Reklam"** — and that is how you say it out loud. Only project conversations go
into the default list; loose ones under "Recents" can be added by hand.

Each app keeps its own list and settings, so switching back and forth breaks
nothing.

---

## If something does not work

**It hears nothing.** Check the menu bar icon: ⚪️ off, 😴 asleep, 🔴 listening.
If it is asleep, say the start command. If the microphone bar in the panel does
not move while you speak, pick a different microphone in Settings.

**It hears you but commands do not land.** Do the "teach it your voice" step
above. The **Recently heard** box shows exactly what it understood.

**Messages are not sent.** The Accessibility permission is probably missing:

```bash
cd ~/Mahmut && ./selftest.py
```

**It does not read replies.** Is **Control → Reading** switched on? That
conversation may also be muted — check the speaker icon in **Open
conversations**.

**The sound crackles.** Set the volume to 100%; below that a different playback
path is used, which can crackle on some Bluetooth headsets.

**Stop everything:**

```bash
cd ~/Mahmut && ./stop.sh
```

**Update:**

```bash
cd ~/Mahmut && git pull && ./setup.sh
```

Updating is safe: your settings, your list and the spellings you taught it are
all preserved.

---

## Cost and privacy

- **Nothing to pay.** No API key, no account, no subscription.
- **Audio never leaves the machine.** Recognition runs on the Apple Silicon
  GPU. The only download is the model, during install.
- The app touches only: the microphone, Accessibility (to type), and
  Claude's/Codex's own conversation files (to read).
- The control panel binds to `127.0.0.1` only and is unreachable from outside.
- The app is **compiled on your machine**, not downloaded as a binary, so
  Gatekeeper never complains and no developer certificate is involved.

---

## Settings

Everything the panel changes is stored in `config.json`. The common ones:

```jsonc
{
  "audio": { "prefer": "headset", "device": null, "output_device": null },
  "stt":   { "language": "tr" },
  "tts":   { "voice": "Yelda", "enabled": true },
  "shortcuts": { "stop_reading": "cmd+alt+k" },
  "ui":    { "panel_port": 8765 }
}
```

**Change the wake name:** Settings → Wake name. Every command moves to the new
name. Short English words are misheard far more often; pick something longer
and distinctive.

**Start at login:**

```bash
cd ~/Mahmut && ./install_autostart.sh
```

---

## For developers

Everything below is technical: how it works, what was measured, and the traps
found along the way.

### The flow

```
mic → energy VAD → MLX Whisper → glossary repair → buffer
                                  buffer ends with the send phrase → ⌘V + Enter

~/.claude/projects/**.jsonl  ─┐
~/.codex/sessions/**.jsonl   ─┴→ watcher → markdown stripper → say → speakers
```

- **VAD** is energy based: adaptive noise floor, pre-roll and a
  minimum-voiced-frames gate. The model only runs on actual speech.
- **Hallucination filtering:** Whisper invents text on silence. A blacklist, a
  compression-ratio check (above 2.4 means it looped) and a prompt-echo check.
- **Matching** folds accents to ASCII, collapses repeated letters, tolerates
  one wrong letter from four letters up, and splits merged words. Spellings
  containing digits get no tolerance (`5inci` ≠ `1inci`).
- **Typing** writes to the clipboard, brings the target forward — *verified*
  through `CGWindowList`, because `NSRunningApplication` values go stale —
  sends ⌘V + Enter and hands focus back.
- **Reading** strips code blocks, tables and paths, splits the text into
  language runs, renders them in parallel and concatenates with ffmpeg.

### How Codex is read

| source | contents |
|---|---|
| `~/.codex/state_5.sqlite` → `threads` | name, `cwd`, `rollout_path` (transcript) |
| `~/.codex/.codex-global-state.json` → `local-projects` | project name and `rootPaths` |
| same file → `projectless-thread-ids` | threads that belong to NO project |

The database's own `project_id` column is always empty, so the owning project
is found by matching a thread's `cwd` against each project's `rootPaths`; the
longest matching root wins. Threads listed in `projectless-thread-ids` stay out
of any project even when their path sits inside one.

Switching uses `codex://threads/<id>`, reading uses the thread's rollout file.
The watcher understands both formats: Claude's
`assistant/message/content[text]` and Codex's
`response_item/payload/content[output_text]`.

On the Claude side, switching is `claude://code/continue?session=<id>` and
reopening a closed conversation is `claude://code/resume?session=<id>`. Session
ids are format-validated (`[A-Za-z0-9_-]{1,64}`), so a malformed value under
`~/.claude` cannot make `open` launch an unexpected URL scheme.

### Resource usage (measured, M-series)

| | |
|---|---|
| Idle | ~0.9% of one core, 184–432 MB |
| Listening | +0.14% across 8 cores |
| Transcribing 5 s of audio | ~1 s wall, 0.05–0.12 s CPU (the rest is GPU) |
| `say` startup latency | ~1 s per call |
| Multi-segment render | 1.14 s preparation, then gapless playback |

### Traps found along the way

**It heard itself.** Through speakers the microphone picks up the reading. Real
case: a reply contained the send phrase, Mahmut read it aloud, the mic heard it
and **sent a message the user never spoke.** The fix is not muting the mic (you
must be able to talk while using speakers) but comparing the heard text with
what is being spoken as a *contiguous subsequence*. A simple word-overlap ratio
was not enough: with the two words of a stop command appearing separately in
the text being read, the genuine command was swallowed too. The guard stays
active for 8 s after playback, because the last audio chunk is transcribed
about a second late.

**Playback crackled.** Eliminated by playing and listening: `afplay` was clean
in every form, and the crackle only appeared in our own block-by-block path —
that loop starves while Whisper runs. At full volume `afplay` is used now; the
block path is only for live volume changes. Also, selecting the same Bluetooth
device for both input and output made PortAudio raise `-9986`; when the chosen
output is already the system default, PortAudio is no longer opened at all.

**The watcher died silently.** A single exception inside
`TranscriptWatcher._run` killed the thread: messages were never read and
nothing was logged. The loop now logs and continues, and a watchdog restarts
the thread if it dies.

**Whisper's `initial_prompt` hurt.** Measured: no benefit on plain speech, it
pushed native words towards English in mixed sentences, and it read itself back
on silence. Disabled.

**`6.yi` tokenized as two words**, so a three-word pattern never matched.
Word-internal periods and apostrophes no longer split tokens, while
sentence-ending punctuation still does.

**`codesign … | grep -q` lies.** `grep -q` exits early, `codesign` dies of
SIGPIPE and `set -o pipefail` reports failure — the check called a valid
ad-hoc signature invalid and stripped it.

**`say` outlives its parent.** It hands playback to a child process, so killing
the parent did not stop the sound. The speaker now runs in its own process
group and kills the group.

**Dock tiles multiplied.** Once the bundle was no longer `LSUIElement`, every
extra instance added its own tile. A pid lock file now enforces a single
instance and one-shot CLI modes never register a tile.

### Editing the panel

`PAGE` in `panel.py` is served from the running process's memory. Refreshing
the browser without restarting the app shows the old HTML. The order is:
`./check_panel.sh` → `./stop.sh && open Mahmut.app` → refresh.

### Bundle and signing

The launcher links against `libpython` and calls `Py_BytesMain` **in process**,
so the process belongs to `Mahmut.app`. It used to exec the venv python from
outside the bundle, which made the Dock show "Python".

The signature is **ad-hoc** (`codesign --sign -`): no Developer ID or company
certificate is used and the keychain is never touched. `build_app.sh` verifies
this after every build and strips the signature if it is not ad-hoc.

Ad-hoc signatures are cdhash based, so changing the launcher or Info.plist
invalidates the Accessibility grant. `build_app.sh` leaves the bundle alone
when nothing actually changed, and the Python code lives outside it, so you can
edit code freely.

### Tests

```bash
./test_devices.py   # device selection rules (no audio hardware needed)
./selftest.py       # permissions, microphone, model, voice, live sessions
./check_panel.sh    # panel JavaScript syntax
./verify.sh         # restarts the app and exercises the typing path
```

### Known limits

- Apple Silicon only (MLX).
- The target application must be running.
- The bundle is **not relocatable**: the project path and virtualenv are
  compiled in, and the model lives in `~/.cache/huggingface`. A downloadable
  build would need the dependencies and model packaged inside the `.app`.
- If the text being read contains your stop command verbatim and in order, a
  spoken stop is suppressed at that moment. The shortcut and the panel button
  always work.

---

## License

[MIT](LICENSE) © Eren Güneş

An independent project, not affiliated with, endorsed by, or connected to
Anthropic or OpenAI. "Claude", "Claude Code" and "Codex" are trademarks of
their respective owners and appear here only to say which applications this
tool works with.
