<div align="center">

<img src="assets/icon.png" width="128" alt="Mahmut">

# Mahmut: Voice Assistant

**Talk to Claude Code. Hear it answer.**

A macOS menu bar app that turns speech into messages for Claude Code and reads
replies back aloud — code blocks excluded. Everything runs on-device.

![platform](https://img.shields.io/badge/platform-macOS%2013%2B-111?style=flat-square)
![chip](https://img.shields.io/badge/chip-Apple%20Silicon-111?style=flat-square)
![python](https://img.shields.io/badge/python-3.11%20%E2%80%93%203.13-111?style=flat-square)
![license](https://img.shields.io/badge/license-MIT-111?style=flat-square)

***English** · [Türkçe](README.tr.md)*

</div>

---

## Quickstart

```bash
git clone https://github.com/saintsun/mahmut-voice-assistant-macos mahmut
cd mahmut
./setup.sh
```

Or skip the terminal entirely: open the folder in Finder and double-click
**`Kur.command`**.

The installer handles Homebrew, PortAudio, FFmpeg, Python, the virtualenv, the
Whisper model and the app bundle, then opens the Accessibility settings pane so
you can grant permission. When it finishes:

```bash
open Mahmut.app      # starts in the menu bar
./selftest.py        # verifies permissions, microphone, model and voice
```

Then say **"Mahmut start"** and begin talking.

---

## How a session looks

```
🎙  "Let's refactor the payment service. The retry logic duplicates
     the backoff from the queue consumer — extract it into a shared
     helper and add a test for the exponential case. Okay Mahmut."

    → typed into Claude Code and sent

🔊  "Message from Payments API."
🔊  "I extracted the backoff into retry.py and added three test cases.
     Code block."

🎙  "Reply Mahmut. Also cover the jitter path. Okay Mahmut."

    → sent to Payments API, which is brought to the front automatically
```

Nothing is ever sent on silence. You talk for as long as you like and close
with a sign-off phrase, so pauses and corrections never leak into the message.

---

## Features

**Input**

- Background listening while you work in any other window
- On-device transcription with MLX Whisper (`whisper-large-v3-turbo`)
- Send only on an explicit sign-off phrase — *"okay Mahmut"*
- Mixed-language speech: a sentence in one language with technical terms in
  another is transcribed and read back correctly
- Voice command sets you can extend by speaking, not by editing code

**Output**

- Replies read aloud with code blocks, tables, paths and markdown stripped
- Each reply announced by conversation: *"Message from Payments API."*
- Parallel replies queue instead of overlapping
- Scheduled-task output is never read

**Conversations**

- All live Claude Code sessions are watched at once
- *"select Admin Panel Mahmut"* switches conversations; closed ones are
  reopened through a deep link
- *"reply Mahmut"* targets whichever conversation last spoke
- Numbered favourites: *"list Mahmut"* → *"first one Mahmut"*

**Control**

- Local web panel: switches, volume, 200-row transcript archive, favourites,
  command editing, settings — localized in English and Turkish
- Global shortcut (⌥⌘K) to stop reading from anywhere
- Voice-triggered keyboard shortcuts for other applications
- Optional start at login

---

## Requirements

| | |
|---|---|
| Hardware | Apple Silicon (M-series) — MLX runs on the GPU |
| OS | macOS 13 or newer |
| App | Claude Code desktop app |
| Disk | ~1.5 GB for the Whisper model |

Installed automatically if missing: Homebrew, `portaudio`, `ffmpeg`,
`python@3.13`.

---

## Installation

### 1. Get the code

```bash
git clone https://github.com/saintsun/mahmut-voice-assistant-macos mahmut
cd mahmut
```

### 2. Run the installer

Double-click **`Kur.command`** in Finder, or run `./setup.sh`. It will:

1. install Homebrew if missing (with your confirmation)
2. install `portaudio`, `ffmpeg` and `python@3.13`
3. create the virtualenv and install `requirements.txt`
4. download the Whisper model (~1.5 GB, first run only)
5. build and launch `Mahmut.app`
6. open the Accessibility settings pane
7. offer to install the start-at-login agent

For automation, `MAHMUT_UNATTENDED=1 ./setup.sh` skips all prompts and windows.

### 3. Grant permissions

Two permissions are required, both under **System Settings → Privacy &
Security**:

- **Microphone** — requested on first launch
- **Accessibility** — required to type into another application. If no prompt
  appears, add `Mahmut.app` manually with `+`.

### Updating

```bash
git pull && ./setup.sh
```

Re-running the installer is safe: installed packages are left alone,
`config.json` is preserved (only missing keys are added), and the bundle is
rebuilt only when it actually changed — so permissions are not reset.

### Code signing

No Apple Developer account, Developer ID or organization certificate is used,
and the keychain is never touched. The app is ad-hoc signed
(`codesign --sign -`, `TeamIdentifier=not set`), and `build_app.sh` verifies
this after every build, stripping the signature if it is not ad-hoc.

The app is compiled on your machine rather than downloaded, so Gatekeeper's
"unidentified developer" dialog never appears. If you downloaded a ZIP instead
of cloning, macOS may set the quarantine flag; `Kur.command` clears it, and if
the first double-click is still blocked, right-click → **Open** once.

---

## Usage

Start listening by saying **"Mahmut start"** or using the menu bar switch.

| Command | Action |
|---|---|
| *"… okay Mahmut"* | send the buffered text to Claude Code |
| *"Mahmut cancel"* | clear the buffer without sending |
| *"Mahmut quiet"* | stop the current reading |
| *"Mahmut stop"* | stop listening (reading continues) |
| *"Mahmut start"* | resume listening |
| *"reply Mahmut"* | switch to the conversation that last spoke, then send |
| *"select Admin Panel Mahmut"* | switch Claude Code to that conversation |
| *"list Mahmut"* | read the numbered favourites list |
| *"first one Mahmut"* | select item 1 from the list |
| **⌥⌘K** | stop reading, from any application |

Every phrase is configurable, and each command accepts many variants.

### The wake name

The default wake name is **Mahmut** — a deliberately non-English, two-syllable
word. Short English wake words are misrecognized constantly in accented or
mixed-language speech. Change it under **Settings → Wake name**; all command
patterns migrate to the new name automatically.

### Mixed-language speech

A sentence such as

> "Şu **backend**'deki **race condition**'ı **fix** ettim, **deploy**
> edebiliriz."

is transcribed as spoken. When read back, the English terms are pronounced by
an English voice inside the Turkish sentence, without the stop-start artifacts
of switching voices mid-sentence: segments are rendered in parallel and
concatenated with FFmpeg, separated by real silence.

A glossary repairs roughly 120 technical terms that transcription reliably
mangles (`"mayigration"` → `migration`), suffix-aware so grammatical endings
survive.

### Teaching it your commands

Transcription will mishear short commands — a two-word utterance carries almost
no context. Rather than fighting this, the panel lets you extend the command
sets by voice: open **Commands → Edit**, press 🎙, say the command as you
normally would, review the transcription and add it.

Two mechanisms are available:

- **Word alignment** — the sentence is aligned with an existing pattern and
  only the differing word is added to that word's spelling set, so the
  correction applies to every pattern containing that word.
- **Whole phrase** — if the word count matches no pattern, the sentence is
  added as a new pattern.

English and Turkish language packs ship as static defaults and can be restored
at any time from **Settings → Command set → Load / Reset**.

---

## Control panel

`http://127.0.0.1:8765/` — also available from the menu bar.

A single-page interface with three tabs:

- **Control** — listening and reading switches, volume, current buffer, the
  live transcript archive (200 rows, each labelled with the command it
  triggered), favourites and application shortcuts
- **Commands** — the full command table; **Edit** opens a dialog showing every
  pattern, removable spelling chips, a field to add a pattern and a microphone
  button to add one by speaking
- **Settings** — wake name, panel port, stop-reading shortcut, target
  application, speech language, command set and reading voice

Status messages appear as colour-coded toasts in the top-right corner. The
**pause** control freezes the running system while you edit commands, so test
phrases do not trigger real actions.

If the configured port is in use, the panel moves to the next free port
automatically. You can also set it in Settings: type a port, availability is
checked immediately, and saving moves the panel live — the open page follows.

---

## Configuration

All settings live in `config.json`, created on first run and editable from the
panel. Frequently adjusted keys:

```jsonc
{
  "audio":     { "prefer": "headset", "device": null },
  "stt":       { "model": "mlx-community/whisper-large-v3-turbo",
                 "language": "tr" },
  "tts":       { "voice": "Yelda", "enabled": true,
                 "duck_mic_while_speaking": "auto" },
  "shortcuts": { "stop_reading": "cmd+alt+k" },
  "ui":        { "panel_port": 8765 }
}
```

### Microphone selection

Built-in microphones record considerably quieter than headsets (measured peak
~0.006 versus ~0.08), which costs recognition accuracy, so `audio.prefer`
defaults to `headset`. Note that Bluetooth headsets switch to the HFP profile
when their microphone opens, which degrades playback quality — set
`"prefer": "builtin"` if that matters more to you.

If a headset is disconnected mid-session, PortAudio keeps serving a stale
device list and the application goes deaf. This is detected (5 seconds of exact
digital silence, or a 45-second idle check), PortAudio is re-initialized, and
the new device is announced.

---

## How it works

```
mic → energy VAD → MLX Whisper → glossary → matcher ─┬→ command
                                                     └→ buffer → clipboard → ⌘V + Enter

~/.claude/projects/**.jsonl → watcher → markdown stripper → say → speakers
```

- **Voice activity detection** is energy-based with an adaptive noise floor,
  pre-roll and a minimum-voiced-frames gate, so transient noise never reaches
  the model. The model only runs when speech was actually detected.
- **Hallucination filtering** — transcription invents text on near-silence.
  Output is discarded based on a blacklist of recurring phantom phrases, a
  compression-ratio check (above 2.4 indicates a loop) and a prompt-echo check.
- **Matching** folds accented characters to ASCII, collapses repeated letters,
  allows an edit distance of 1 on words of four or more characters, and splits
  merged words.
- **Injection** writes to the clipboard, brings the target to the front
  (verified through `CGWindowListCopyWindowInfo`, since `NSRunningApplication`
  values are cached and go stale without a run loop), sends ⌘V and Enter, then
  restores the previously focused application.
- **Reading** strips code blocks, tables, paths and emphasis markers, splits
  text into language runs, renders them in parallel and concatenates them so a
  bilingual sentence plays as one continuous utterance.

### Performance

Measured on an M-series machine:

| | |
|---|---|
| Idle | ~0.9% of one core, 184–432 MB resident |
| Listening | +0.14% across 8 cores |
| Transcribing a 5-second clip | ~1 s wall time, 0.05–0.12 s CPU (GPU-bound) |
| `say` startup latency | ~1 s per call |
| Multi-segment render | 1.14 s preparation, then gapless playback |

---

## Security and privacy

**No API keys or credentials.** Mahmut never calls Claude's API; it types into
the window exactly as you would (clipboard, ⌘V, Enter). There is no key in the
repository or in `config.json`, no access to your account, and no reading of
session cookies.

**No outbound traffic.** The application code contains no network calls; speech
is transcribed on-device. The only download is the model, fetched during
installation.

**Access required:**

| | Purpose |
|---|---|
| Microphone | transcribing speech |
| Accessibility | typing into the target window, sending application shortcuts |
| `~/.claude/projects/**.jsonl` | reading incoming replies (read-only) |
| `~/.claude/sessions/*.json` | names and identifiers of open conversations |

Accessibility is a powerful permission — it allows an application to send
keystrokes anywhere. The entire codebase is open, and `inject.py` is the only
file that uses it.

**The local panel** binds to `127.0.0.1` only. Because a browser page can send
a preflight-free `text/plain` POST to a local address, requests carrying a
foreign `Origin` header are rejected with HTTP 403.

**Data stored on disk**, all excluded from version control: `config.json`
(settings and conversation names), `.state.json` (recent transcripts and a
200-row archive), `.app.log`, `.muted.json`.

**Code hygiene:** no `shell=True`, `eval`, `exec` or `pickle`; all
`subprocess` calls use list arguments; only a numeric process id is
interpolated into AppleScript; session identifiers in `claude://` deep links
are format-validated before use.

---

## Implementation notes

A few problems worth recording. The [Turkish README](README.tr.md) documents
these in full.

**The application heard itself.** Through speakers rather than headphones, the
microphone picks up the reading. In one case a reply containing a sign-off
phrase was read aloud, transcribed, and sent a message the user never spoke.
Muting the microphone during playback would prevent stopping a reading by
voice, so the heard text is instead matched against what is currently being
spoken — as a *contiguous subsequence*, because a simple word-overlap ratio
also suppressed genuine commands. The guard remains active for 8 seconds after
playback, since the final audio chunk is transcribed about a second late.

**Bluetooth playback crackled while listening.** Not a bug in the app: as long
as a microphone stream is open and input and output are the same wireless
device, macOS drops from A2DP to HFP and playback becomes narrowband. Shazam
behaves the same way. The fix is to *close* the input stream while speaking
(not merely mute it) and reopen it afterwards — `release_mic_while_speaking`
defaults to `auto`, which only does this when input and output are the same
wireless device. The cost is that a spoken stop command is not heard during
playback; the global shortcut and the panel button always work.

**Whisper's `initial_prompt` was harmful.** Measured: no benefit on plain
speech, corruption of mixed-language sentences, and self-echo on silence. It is
disabled.

**Tokenization split ordinals.** `6.yi` became two tokens, so a three-word
pattern never matched. Word-internal periods and apostrophes no longer split
tokens, while sentence-ending punctuation still does.

**`codesign … | grep -q` reports false negatives.** `grep -q` exits early,
`codesign` receives SIGPIPE, and `set -o pipefail` marks the pipeline as
failed — the check declared a valid ad-hoc signature invalid and stripped it.

**`say` outlives its parent process.** It spawns a child, so terminating the
parent left audio playing. The speaker now runs in its own process group.

**Dock tiles multiplied.** Once the bundle was no longer `LSUIElement`, every
additional launch added a Dock icon. A PID lock file now causes a second
instance to exit immediately, and one-shot CLI modes never register a tile.

---

## Troubleshooting

```bash
./selftest.py      # permissions, microphone, model, voice, live sessions
./verify.sh        # restarts the app and types a test line into Claude Code
./stop.sh          # stops the app and any orphaned say/afplay processes
./run.sh           # run in the terminal to see tracebacks
tail -f .app.log   # live log
```

**Accessibility permission not recognized after a rebuild.** Ad-hoc signatures
are cdhash-based, so rebuilding the launcher invalidates the grant. Remove the
stale entry with `-` and add the application again — toggling it off and on is
not sufficient. Alternatively:

```bash
tccutil reset Accessibility com.erengunes.mahmut
```

**Panel buttons do nothing.** The panel's JavaScript lives inside a Python
string where a stray escape silently breaks it. `./check_panel.sh` runs
`node --check` against it. Note that the page is served from the running
process: restart the application after editing `panel.py`.

---

## Limitations

- Apple Silicon only (MLX).
- The target application must be running for a message to be delivered.
- Reading replies works with Claude Code only, whose transcripts are the
  source. A GPT Codex target appears in Settings but is disabled: sending would
  likely work, reading has no equivalent source.
- The bundle is not relocatable — the project path and virtualenv are compiled
  in, and the model lives in `~/.cache/huggingface`. Distributing a prebuilt
  binary would require packaging dependencies and the model inside the `.app`.
- If the text being read contains your stop phrase verbatim and in order, a
  spoken stop command is suppressed at that moment. The panel and menu bar
  controls always work.

---

## License

[MIT](LICENSE) © Eren Güneş

This is an independent project. It is not affiliated with, endorsed by, or
connected to Anthropic. "Claude" and "Claude Code" are trademarks of Anthropic
and are used here only to identify the application this tool works with.
