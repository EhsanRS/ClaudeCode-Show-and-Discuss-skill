# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-10-20

### Added
- `present` skill: ground the plan, check capabilities, build the deck, publish
  it as an artifact, walk through it in the browser, discuss, and wrap up with
  an explicit approval gate.
- Four presentation modes with graceful degradation: Full, Show, Share, Local.
- Presenter template: themed slide deck with pointer, spotlight, highlight,
  captions, narration beats with inline cues, live decision recording, hash
  deep-links, keyboard controls and overview/print modes.
- `voice.py`: interruptible narration (ElevenLabs or system voice), local
  Whisper or ElevenLabs Scribe transcription, `doctor` and `calibrate`.
- `check_deck.py`: deck validator.
- Test suite (unit, validator, headless Chromium) and CI on Linux, macOS and Windows.

[Unreleased]: https://github.com/EhsanRS/ClaudeCode-Show-and-Discuss-skill/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/EhsanRS/ClaudeCode-Show-and-Discuss-skill/releases/tag/v0.1.0
