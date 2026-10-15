# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **GPT Codex support.** Codex is now a selectable target next to Claude Code.
  Conversations come from the app's own local state
  (`~/.codex/state_5.sqlite` for threads, `.codex-global-state.json` for
  projects), switching uses the `codex://threads/<id>` deep link, and replies
  are read from the thread's rollout transcript.
- Codex threads are named after their project: a thread "Reklam" inside the
  project "Kunaz" is listed as **Kunaz Reklam**. The database's own
  `project_id` is always empty, so the owning project is found by matching the
  thread's `cwd` against each project's `rootPaths`; threads listed in
  `projectless-thread-ids` stay out of any project even when their path sits
  inside one.
- Default favourites for Codex are the project conversations only; loose
  "Recents" can be added by hand.
- The panel shows **both** applications: the selected one is live and the
  other appears below it, dimmed and inert, so you can see what is on the
  other side before switching.
- The transcript watcher understands both formats, Claude Code's
  `assistant/message/content[text]` and Codex's
  `response_item/payload/content[output_text]`.
- **Uninstaller.** `./uninstall.sh` (or double-clicking `Kaldir.command`)
  stops the app, removes the bundle, the Python environment and the launch
  agent, resets the Microphone and Accessibility entries, and asks separately
  about `config.json`, the 1.5 GB speech model and the folder itself.
  `--all` and `--keep` skip the questions. Homebrew packages are never
  removed, because other programs use them.
- The installer opens the panel at the end, because teaching it your own
  pronunciations is the first thing to do and that happens there.

### Fixed

- **Muted conversations were read out loud anyway.** The watcher follows every
  live session and hands each new assistant text straight to the speaker, but
  nothing checked the mute list on the way, so scheduled tasks (routines) and
  conversations muted by hand were spoken. The check now sits in the single
  place every reply passes through, and a muted conversation no longer becomes
  the "reply" target either.
- A routine attached to an existing conversation was not recognised. The
  marker was looked for in the first 256 KB of the transcript only, which in a
  long conversation is far before the scheduled run. Both ends of the file are
  scanned now, so recurring check-ins inside an old conversation are caught.

## [1.0.0] - 2026-10-14

First release. A macOS menu bar app that turns speech into Claude Code
messages and reads replies back aloud, entirely on-device.

### Speech in

- Background listening with energy VAD (adaptive noise floor, pre-roll,
  minimum-voiced-frames gate), so the model only runs on actual speech
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
  transcript archive, favourites, command editing, settings, English/Turkish
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
