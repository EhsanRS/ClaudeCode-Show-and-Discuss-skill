# Architecture and design decisions

This document records *why* the skill is built the way it is, so future
changes can keep or deliberately revisit those choices.

## Goals

1. Before implementing, Claude **demos the intended result** (artifact),
   **walks through** it (browser, pointer) and **discusses** it (voice,
   interruptible). The aim is to confirm it understood the assignment first,
   and only then go into technical detail.
2. Work on every Claude Code surface (CLI, desktop, web), at the best fidelity
   each one allows.
3. Free and private by default; paid services optional.
4. Never implement before the user approves.

## Constraints we designed around

These reflect Claude Code's capabilities at the time of writing (v2.1.x):

| Constraint | Consequence |
|---|---|
| Claude Code has no text-to-speech output and no voice barge-in. `/voice` is push-to-talk dictation, CLI/VS Code only. | Voice is implemented in a bundled helper script that Claude calls through Bash. |
| The browser tools (Claude in Chrome, the desktop browser pane) can navigate, click and run JavaScript, but have no presentation pointer or highlighting. | The deck draws its own pointer, spotlight and captions, exposed as `window.presenter`. |
| Artifacts may be rendered inside a frame that the browser tool can't script. | The deck also works from a local file or loopback server, and through hash URLs and keys with no JavaScript at all. |
| Cloud sessions have no audio device and no browser tool. | Modes degrade in steps: Full → Show → Share → Local. |

## Decisions

### D1: Presenter logic lives in the page, not in the browser tool
A single self-contained HTML file carries its own runtime. Claude only issues
short commands (`presenter.run("go 3; spotlight flow")`). It looks the same in
every browser tool and in a shared link, and needs no extension. The page also
works on its own for anyone reading it later (keyboard, overview mode, print).

### D2: Narration and cues are authored together
Notes contain inline cues (`[[point store]]`), and `presenter.beats()` splits
them into `{cue, text}` pairs. This keeps what is said and what is pointed at
in one place, and is validated by `check_deck.py` before publishing.

### D3: Voice is a local helper with pluggable engines
- **TTS:** ElevenLabs when `ELEVENLABS_API_KEY` is set (natural), else the
  system voice (free, offline). ElevenLabs is requested as raw PCM so no audio
  decoder is required. On failure the helper falls back to the system voice
  mid-call.
- **STT:** local faster-whisper by default (private, free), ElevenLabs Scribe
  as an opt-in.
- **Barge-in:** an energy-based voice-activity detector runs on the mic while
  narration plays. Speech must be sustained for ~240 ms (ignores clicks and
  coughs). The threshold is doubled during playback to resist speaker bleed;
  the noise floor is calibrated at start-up and drifts while quiet. A ~600 ms
  pre-roll buffer keeps the first word of the question.
- **Interface:** one JSON object per call on stdout, so Claude can branch on
  `status` reliably.

*Alternatives considered:* the browser Web Speech API (quality and permissions
vary by browser and frame; there's no channel back to Claude without polling);
an ElevenLabs Conversational Agent (a second "brain" separate from Claude, and
paid minutes); `/voice` dictation (push-to-talk, so no barge-in).

*Known limitation:* without headphones, loud speakers can still trigger
barge-in. `SHOW_DISCUSS_SENSITIVITY` tunes this. Real echo cancellation is a
possible future improvement.

### D4: Graceful degradation over hard requirements
The skill checks for capabilities and picks a mode. It never stops just because
voice or a browser is missing. The content and the discussion loop matter most;
voice and pointer make them better.

### D5: Demo first, technical second
Early versions presented the *build plan* (approach, slices, risks). Feedback:
that tests whether the plan is sound, but not whether Claude understood the
request, and that is the more common and more expensive failure. The deck is
therefore structured as Brief → Demo → Checkpoint → Technical:

- The **demo** shows the end result from the user's point of view, using
  interactive mocks (`data-demo-state`, `data-action`, `[[click]]`, `[[type]]`,
  `[[reveal]]`) rather than descriptions.
- The **checkpoint** (`data-checkpoint`) is a hard stop: Claude waits for the
  user, and if the understanding is wrong, it revises and re-demos instead of
  continuing.
- The **technical** section is optional and goes as deep as the user wants.

Mocks are plain HTML with declarative state, so the same demo works when Claude
drives it, when the user clicks it in a shared link, and through hash URLs
(`#2/opt-dark/click`) for browser tools without JavaScript.

### D6: An explicit approval gate
The skill ends by republishing the deck with the agreed decisions and asking
for a go-ahead. It may *offer* to present when a plan is agreed, but never
starts presenting, or implementing, on its own.

## Repository layout

```
.claude-plugin/marketplace.json          # this repo is a plugin marketplace
plugins/show-and-discuss/
  .claude-plugin/plugin.json             # plugin manifest (version lives here and in voice.py)
  skills/present/
    SKILL.md                             # the workflow
    references/                          # loaded on demand by Claude
    assets/presenter-template.html       # deck + presenter runtime
    scripts/voice.py                     # TTS / barge-in / STT helper (PEP 723 deps)
    scripts/check_deck.py                # deck validator (stdlib only)
tests/                                   # pytest: unit, validator, headless-browser
```
