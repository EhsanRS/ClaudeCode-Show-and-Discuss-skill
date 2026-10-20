---
name: present
description: Present a plan as a live, narrated walkthrough before acting on it — a slide deck artifact with mock-ups and diagrams, shown in the browser with an on-screen pointer, spoken aloud with voice, and discussed with the user who can interrupt by talking. Use when the user asks to present, show, walk through, pitch, demo or "show and discuss" a plan, design, slice breakdown, standup update, lab-meeting result or proposal. When a development plan has just been agreed and implementation is about to start, offer this once (do not start it unprompted).
argument-hint: "[what to present, e.g. 'the plan for slice 2']"
---

# Show and discuss

Turn the plan into a short presentation, walk the user through it like a
stand-up or lab meeting, and discuss it — **before** any implementation
happens. The user can interrupt at any time by speaking (or typing); questions
get answered, decisions get recorded on the final slide, and nothing is built
until the user gives the go-ahead.

Paths below use `${CLAUDE_SKILL_DIR}` — the directory containing this file.

## The five phases

Work through these in order. Keep the user informed with one short line per
phase; don't narrate tool mechanics.

### 1. Ground the content

- If there is no concrete plan yet, build one first (research the codebase,
  brainstorm with the user, agree on slices). A presentation of a vague plan
  wastes the meeting.
- Decide the format from what the user asked for: **dev plan** (default),
  **slice review**, **standup**, **lab meeting / results**, **design review**.
  Outlines for each are in [references/presentation-format.md](references/presentation-format.md).
- Everything on the slides must be true of this codebase/project — real file
  names, real constraints, real numbers. Mark assumptions as assumptions.

### 2. Check capabilities and pick a mode

Check all three, then tell the user in **one line** which mode you'll use and,
if something is missing, the one thing that would enable it.

| Capability | How to check |
|---|---|
| **Artifact** | The `Artifact` tool is in your tool list. |
| **Browser** | Tools named `mcp__claude-in-chrome__*`, `mcp__Claude_Browser__*` or `mcp__remote-devices__Claude_Browser__*` exist (or an `enable__…` tool that turns them on). If a matching `chrome-browser` / `built-in-browser` skill is listed, load it before first use. |
| **Voice** | Run `uv run "${CLAUDE_SKILL_DIR}/scripts/voice.py" doctor` (or `python3 …` if `uv` is missing). `"mode": "voice"` means it works. Cloud sessions never have audio. |

| Mode | When | What happens |
|---|---|---|
| **Full** | artifact + browser + voice | Publish, open in browser, drive the pointer, speak each beat, listen for interruptions. |
| **Show** | browser, no voice | As Full, but narration goes in chat (short), and the user replies in chat. Turn captions on. |
| **Share** | artifact, no browser | Publish and give the link; walk through slide by slide in chat; user says "next" or asks. |
| **Local** | no artifact tool | Write the deck as a local HTML file the user can open (send it with `SendUserFile` if available); otherwise as Share. |

Never block on a missing capability — degrade and carry on. If `doctor` lists
fixable problems (e.g. `libportaudio2` missing, no TTS engine), mention the fix
once; don't install system packages without asking.

### 3. Build the deck

1. Copy `${CLAUDE_SKILL_DIR}/assets/presenter-template.html` to a working file
   named after the topic (e.g. `<scratchpad>/show-and-discuss/dark-mode-plan.html`;
   use the scratchpad directory when the session has one, else
   `.show-and-discuss/` in the project).
2. Replace everything between the `SLIDES:START` and `SLIDES:END` markers with
   your slides, and set `<title>` to a 2–4 word name. Do not modify the CSS
   tokens or the presenter `<script>` — only add slide-specific inline styles
   if needed.
3. Follow the authoring contract in
   [references/presentation-format.md](references/presentation-format.md):
   one `<section class="slide" data-title>` per slide, narration in
   `<aside class="notes">`, `data-spot` on things you'll point at, and inline
   cues like `[[spotlight flow]]` to sync the pointer with speech.
4. Aim for **5–9 slides** and **40–120 spoken words per slide**. Mock-ups are
   real HTML inside `.mock`; diagrams are inline SVG using the `diagram` classes.
5. Validate: `python3 "${CLAUDE_SKILL_DIR}/scripts/check_deck.py" <file>`.
   Fix every error; consider the warnings.

### 4. Publish and open

- **Publish** with the `Artifact` tool (`file_path` = the deck, `icon` = `slides`,
  a one-sentence `description`). The template already satisfies the artifact
  page contract (title, theme tokens, dark mode, mobile layout, no external
  scripts); keep it that way. If the tool requires loading a design skill first,
  load it, but keep the template's structure.
- **Open** it in the browser and confirm the presenter API is reachable — see
  [references/browser-driving.md](references/browser-driving.md). If the
  published page can't be scripted (it sits in a cross-origin frame), serve the
  local copy on `127.0.0.1` and drive that instead; share the artifact link for
  later reading.

### 5. Present and discuss

Open with one sentence: what this is, how long it takes, and that the user can
interrupt any time by talking. Then for each slide:

1. `presenter.go(n)` and fetch `presenter.beats()` — a list of
   `{cue, text}`.
2. For each beat: run the cue (`presenter.run(cue)`), then speak the text:
   `uv run "${CLAUDE_SKILL_DIR}/scripts/voice.py" say "<text>"`
   (Bash timeout ≥ 300000 ms). Batch consecutive beats without cues into one
   `say` call.
3. Read the JSON result and act on it:

| `status` | Meaning | Do |
|---|---|---|
| `finished` | Spoke it all, nobody talked | Next beat / slide. |
| `interrupted` | User spoke over the narration | Handle `transcript` (below). Afterwards resume with `remaining_text`, or skip it if the discussion covered it. |
| `question` | User spoke right after the beat | Handle `transcript`. |
| `error` | Audio failed | Switch to **Show** mode for the rest; tell the user once. |

**Handling what the user said** — classify the transcript:

- **Question** → answer in 1–3 spoken sentences (`say` again — it can be
  interrupted too). Point at or spotlight the relevant spot. If answering needs
  research (reading code, running a command), say "Let me check that," do it,
  then answer.
- **Change request / decision** ("let's not do slice 3", "use Postgres") →
  acknowledge it, restate it in one sentence, and record it live with
  `presenter.agree("Keep scope to Settings only")`. Keep a running list of
  decisions.
- **Navigation** ("go back", "skip to risks", "next", "stop") → do it.
- **Empty or garbled transcript** → "Sorry, I didn't catch that — could you say
  it again?" then `voice.py listen`.
- **Done with the question?** After answering, `voice.py listen --timeout 4`;
  silence means carry on.

In **Show/Share/Local** modes the same loop runs over chat: post the narration
for a slide (tight — the slide carries the detail), move the pointer, and end
your turn so the user can reply with a question, a change, or "next".

## Wrap-up (always)

1. On the last slide, summarise the decisions aloud and on screen.
2. Update the deck file's final slide with the agreed decisions and
   republish it to the **same** artifact (same `file_path`), so the link is a
   record of the meeting.
3. Update the written plan (plan file, TODO list, or chat summary) to reflect
   the changes.
4. Ask for an explicit go-ahead. **Do not start implementing until the user
   approves.** Stop any local server you started.

## Ground rules

- Keep it a conversation, not a lecture: short beats, plain spoken English,
  no reading of code aloud (show it, describe it).
- Never put secrets, tokens or personal data in slides or narration — with an
  ElevenLabs key set, narration text is sent to ElevenLabs; with
  `SHOW_DISCUSS_STT=scribe`, the user's audio is too.
- Be honest on the slides: unknowns go in "Risks & open questions", not in
  confident prose.
- Voice settings, troubleshooting and costs: [references/voice.md](references/voice.md).
