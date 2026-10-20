# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-10-20

### Changed
- **Demo first.** Presentations are now structured as Brief → Demo →
  "Did I get it right?" checkpoint → optional Technical walkthrough → Decisions,
  so the user can confirm Claude understood the assignment before any
  technical discussion. `SKILL.md`, the reference guides and the example deck
  were rewritten around this flow.

### Added
- Interactive demo mocks: `data-demo-state`, `data-when`, `data-active-when`,
  `data-action` and `data-reveal`, plus `[[click]]` running actions,
  `[[state]]`, `[[type]]`, `[[reveal]]` and `[[reset]]` cues and matching
  `presenter.*` methods.
- Slide sections (`data-section`) shown in the control bar, and checkpoint
  slides (`data-checkpoint`) reported by `presenter.state()`.
- Hash routes `#n/spot/click` and `#n/spot/reveal`.
- Terminal and toast components for CLI/API demos.
- Validator checks for demo actions, new cue arguments, and missing
  checkpoint or demo slides.

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

[Unreleased]: https://github.com/EhsanRS/ClaudeCode-Show-and-Discuss-skill/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/EhsanRS/ClaudeCode-Show-and-Discuss-skill/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/EhsanRS/ClaudeCode-Show-and-Discuss-skill/releases/tag/v0.1.0
