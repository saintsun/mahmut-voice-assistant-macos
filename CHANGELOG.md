# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0] — 2026-10-14

First release. A macOS menu bar app that turns speech into Claude Code
messages and reads replies back aloud, entirely on-device.

### Speech in

- Background listening with energy VAD (adaptive noise floor, pre-roll,
  minimum-voiced-frames gate) — the model only runs on actual speech
- On-device transcription with MLX Whisper (`whisper-large-v3-turbo`)
- Messages are sent **only** on an explicit sign-off phrase, never on silence
- Hallucination filtering: phantom-phrase blacklist, compression-ratio check,
  prompt-echo check
- Mixed-language speech with a ~120-term technical glossary, suffix aware
- Command sets extendable by voice: word alignment or whole-phrase capture
- Word-internal periods and apostrophes no longer split tokens (`6.yi`,
  `Mahmut'un`); digit spellings for ordinals 1–10
- Fuzzy matching disabled for digit-bearing tokens (`5inci` ≠ `1inci`)

### Speech out

- Replies read aloud with code blocks, tables, paths and markdown stripped
- Announced per conversation, parallel replies queue instead of overlapping
- Bilingual sentences rendered in parallel and concatenated with FFmpeg
- Scheduled-task output is never read
- Self-voice guard: text matching what is currently being spoken is ignored
  as a contiguous subsequence, for 8 s after playback ends

### Conversations

- All live Claude Code sessions watched at once; the watcher thread survives
  errors and is restarted by a watchdog if it dies
- Switch by name, reply to the last speaker, numbered favourites list
- Closed conversations reopened through `claude://` deep links, with the
  session id format-validated

### Control

- Local web panel (`127.0.0.1:8765`): switches, volume, paginated 200-row
  transcript archive, favourites, command editing, settings — English/Turkish
- Global stop-reading shortcut, default ⌥⌘K
- Microphone and speaker selection: automatic (headset preferred) or an
  explicit device that survives headset changes
- Panel port is configurable and falls back to the next free port
- Voice-triggered keyboard shortcuts for other applications
- Start at login through a LaunchAgent

### Packaging

- Python runs inside the bundle (embedded `Py_BytesMain`), so the Dock shows
  the app's own name and icon
- Ad-hoc signed only; no Developer ID or organization certificate is used and
  `build_app.sh` verifies this after every build
- Single-instance lock; one-shot CLI modes never register a Dock tile
- One-click installer (`Kur.command`) and `./setup.sh`

### Audio notes

- Playback uses `afplay` at full volume; the block-by-block path is reserved
  for live volume changes (it starved under Whisper load and crackled)
- Choosing an output that is already the system default no longer opens
  PortAudio, avoiding `-9986` when the same Bluetooth device is in use for
  input

[1.0.0]: https://github.com/saintsun/mahmut-voice-assistant-macos/releases/tag/v1.0.0
