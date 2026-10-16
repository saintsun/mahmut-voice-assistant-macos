# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **A light theme in the panel.** The moon button next to the language picker
  switches between light and dark; the choice is kept in that browser, so it
  survives reloads without touching the app's settings. Dark stays the
  default. Only colours change: the surfaces are repainted and the neon
  accents are darkened enough to stay readable on white, while every size and
  position is untouched.

### Fixed

- **"Microphone off" did not release the microphone.** Turning it off only
  cleared a flag: the app ignored the audio, but the PortAudio stream stayed
  open, so macOS kept the orange recording dot lit and the device stayed busy
  for every other app. Off now closes the stream, and the watchdog no longer
  reopens it while the app is off. Turning it back on opens it again.
- **A conversation was sent to Claude without the send phrase.** "over" is a
  send phrase on its own, and fuzzy matching allows one letter of difference
  from four letters up, so the very common Turkish word "ver" matched it: any
  sentence ending in "ver" shipped the buffer. A one-word pattern carries no
  context around it, so it now has to be heard exactly (doubled letters are
  still ignored). "over" on its own is also out of the Turkish command set;
  "tamam over" stays.

- **The app froze while a Bluetooth device reconnected.** A stack sample of a
  hung run showed the main thread blocked inside CoreAudio's own mutex while
  another thread sat in CoreAudio too: the microphone watchdog rebuilt the
  stream on the MAIN thread, and anything else touching PortAudio at that
  moment deadlocked it. The menu, the panel and the reading all stopped and
  the process sat at 0% CPU. Three changes: every call into PortAudio goes
  through one lock, the microphone check runs in its own thread, and the
  queries that only inform a decision give up on the lock after a second or
  two and fall back to their safe default instead of waiting.
- The panel asked CoreAudio for the device list on every poll, about once a
  second. The list is cached for a few seconds now, and while the stream is
  being rebuilt the previous list is served instead of blocking.

- **Over speakers, the reading was heard back and sent to Claude.** The
  microphone picks up our own voice together with the user's, so the
  transcript held the whole list that had just been read plus the one
  sentence the user actually said. The line was neither an echo (it carried
  the user's words) nor usable as it was. The echoed runs are now cut out of
  the heard text and only the rest is handled, so "Test gönderimi" at the end
  of a read-out list is sent on its own. A single word left between two
  echoed runs is dropped as well, because the microphone mishears our own
  voice now and then. With headphones nothing changes, there is no echo
  there.
- The broken start of an echo stayed behind. Demanding an exact run of words
  left the mangled ones in place ("Ses Kontrolü mesajını okuyorum" comes back
  as "6 kontrolü mesajin okuyoru", and three of those four words aligned, not
  four). The heard words are aligned against the spoken ones in order now,
  and a region counts as echo when most of it aligns, so the misheard words
  in between go with it. A couple of shared words still do not silence the
  user: the region has to be at least four words long.

## [1.1.0] - 2026-10-15

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
- Selecting a conversation by name went through the Claude list whatever the
  target was, so with Codex selected no thread could be reached by name. It
  now searches the selected application's list, exact name first.
- Favourites were always saved under the Claude key. Editing the list while
  Codex was selected overwrote the Claude list, and the Codex list stayed as
  it was. Each target now reads and writes its own key.
- Fuzzy matching for Codex had no score floor, so a name that matched nothing
  still switched to whatever ranked first. It uses the same 0.62 threshold as
  Claude sessions now.

### Tests

- `test_sources.py`: 18 cases over targets, muting and routine detection,
  including the two transcripts that caused the bugs above. No app window, no
  audio hardware.

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
