---
name: present
description: Demo what you're about to build before building it, so the user can check you understood the assignment. Builds a slide-deck artifact with a clickable mock of the end result, shows it in the browser with an on-screen pointer, narrates it by voice, and lets the user interrupt by talking. Stops at a "Did I get it right?" checkpoint, and only then (if wanted) goes into the technical plan. Use when the user asks to present, show, demo, walk through or "show and discuss" a plan, feature, design, standup update, lab-meeting result or proposal. When a plan has just been agreed and implementation is about to start, offer this once (do not start it unprompted).
argument-hint: "[what to demo, e.g. 'the dark-mode settings feature']"
---

# Show and discuss

Before building anything, **demo the result** the user will get, as if it
already existed. The goal is to check that you understood the assignment
*before* any code is written. Only once the user confirms do you go into the
technical *how*, and only as deep as they want.

The flow, like a good stand-up or lab-meeting demo:

```
Brief  →  Demo  →  Checkpoint: "Did I get it right?"  →  (optional) Technical  →  Decisions  →  go-ahead
```

The user can interrupt at any time by speaking (or typing). Nothing is built
until they approve. Paths below use `${CLAUDE_SKILL_DIR}`, the directory
containing this file.

## 1. Understand the assignment

- Restate the request in your own words: what the user asked, what you take
  it to mean, and what is out of scope. This is what the demo will test.
- Research enough to make the demo **specific to this project**: real screen
  names, real labels, real commands, real data shapes. Unknowns become
  explicit *assumptions* on the checkpoint slide, not confident fiction.
- Decide what a demo of *this* looks like:

| Work type | The demo shows |
|---|---|
| UI feature | A clickable mock of the screen(s): the pointer clicks, the mock changes state. |
| CLI / tooling | A terminal session revealed line by line: command, output, result. |
| API / backend | Request → response pairs, before/after data, or the user-visible effect. |
| Refactor / infra | Before vs after: what changes for developers or users (speed, steps, errors). |
| Data / research | The result: the chart, table or finding, then what it means. |
| Non-dev (standup, lab meeting) | The outcome or result first; the detail second. |

## 2. Check capabilities and pick a mode

Check all three, then tell the user in **one line** which mode you'll use and,
if something is missing, the one thing that would enable it.

| Capability | How to check |
|---|---|
| **Artifact** | The `Artifact` tool is in your tool list. |
| **Browser** | Tools named `mcp__claude-in-chrome__*`, `mcp__Claude_Browser__*` or `mcp__remote-devices__Claude_Browser__*` exist (or an `enable__…` tool that turns them on). If a matching `chrome-browser` / `built-in-browser` skill is listed, load it before first use. |
| **Voice** | Run `uv run "${CLAUDE_SKILL_DIR}/scripts/voice.py" doctor` (or `python3 …` if `uv` is missing). `"mode": "voice"` means it works. Cloud sessions never have audio. |

| Mode | When | What happens |
|---|---|---|
| **Full** | artifact + browser + voice | Publish, open in the browser, drive the demo, speak each beat, listen for interruptions. |
| **Show** | browser, no voice | As Full, but narration goes in chat (short) and the user replies in chat. Turn captions on. |
| **Share** | artifact, no browser | Publish and give the link. The user clicks through the demo themselves (mocks are interactive) while you narrate slide by slide in chat. |
| **Local** | no artifact tool | Write the deck as a local HTML file the user can open (send it with `SendUserFile` if available); otherwise as Share. |

Never block on a missing capability; degrade and carry on. If `doctor` lists
a fixable problem, mention the fix once. Don't install system packages without
asking.

## 3. Build the deck

1. Copy `${CLAUDE_SKILL_DIR}/assets/presenter-template.html` to a working file
   named after the topic (in the scratchpad directory when the session has one,
   else `.show-and-discuss/` in the project).
2. Replace everything between the `SLIDES:START` and `SLIDES:END` markers, and
   set `<title>` to a 2–4 word name. Don't modify the CSS tokens or the
   presenter `<script>`. Slide-specific `<style>` and inline styles are fine.
3. Structure (details and markup in
   [references/presentation-format.md](references/presentation-format.md)):
   - **Brief** (1 slide, `data-section="Brief"`): *You asked* / *I took that to
     mean* / *Not included*.
   - **Demo** (1–4 slides, `data-section="Demo"`): the end result in use, told
     as the user's story ("you open Settings, pick Dark…"). Make mocks
     interactive with `data-demo-state` / `data-action` and drive them with
     `[[click …]]`, `[[type …]]`, `[[reveal …]]`. No implementation talk here.
   - **Checkpoint** (1 slide, `data-section="Check" data-checkpoint`): *I'll
     build* / *I won't build (yet)* / *Assumptions*, ending with the question
     "Did I get it right?"
   - **Technical** (2–5 slides, `data-section="Technical"`): approach, slices,
     risks. Last slide: decisions needed plus the `agreed` list.
4. Narration: 40–120 spoken words per slide in `<aside class="notes">`, with
   `[[cues]]` to sync the pointer and demo actions with speech.
5. Validate: `python3 "${CLAUDE_SKILL_DIR}/scripts/check_deck.py" <file>`.
   Fix every error; consider the warnings.

## 4. Publish and open

- **Publish** with the `Artifact` tool (`file_path` = the deck, `icon` =
  `slides`, a one-sentence `description`). The template already satisfies the
  artifact page contract; keep it that way. If the tool requires loading a
  design skill first, load it, but keep the template's structure.
- **Open** it in the browser and confirm the presenter API is reachable. See
  [references/browser-driving.md](references/browser-driving.md). If the
  published page can't be scripted, serve the local copy on `127.0.0.1` and
  drive that; share the artifact link for later.

## 5. Present: brief and demo

Open with one sentence: "I'll show you what I'm planning to build, so you can
tell me if I understood. Interrupt any time by just talking." Then for each
slide:

1. `presenter.go(n)`, then `presenter.beats()`, which returns `{cue, text}` pairs.
   (Fetching beats switches the page to live mode, so `data-reveal` items stay
   hidden until revealed.)
2. For each beat: run the cue (`presenter.run(cue)`), then speak the text:
   `uv run "${CLAUDE_SKILL_DIR}/scripts/voice.py" say "<text>"`
   (Bash timeout ≥ 300000 ms). Batch consecutive beats without cues into one
   `say` call.
3. Act on the JSON result:

| `status` | Meaning | Do |
|---|---|---|
| `finished` | Spoke it all; nobody talked | Next beat or slide. |
| `interrupted` | User spoke over the narration | Handle `transcript` (below), then resume with `remaining_text` or skip it if the discussion covered it. |
| `question` | User spoke right after the beat | Handle `transcript`. |
| `error` | Audio failed | Switch to **Show** mode for the rest; tell the user once. |

**Handling what the user said.** Classify the transcript:

- **Question**: answer in 1–3 spoken sentences (`say` again; it can be
  interrupted too), pointing at or re-running the relevant part of the demo.
  If answering needs research, say "Let me check that," do it, then answer.
- **"That's not what I meant" / correction**: this is the point of the demo.
  Thank them, restate the corrected understanding, and record it with
  `presenter.agree("…")`. If it changes the demo materially, say you'll revise
  it after the checkpoint.
- **Decision** ("use Postgres", "drop the phone part"): restate it and record
  it with `presenter.agree("…")`.
- **Navigation** ("go back", "show that again", "skip to the tech"): do it.
  To replay a demo slide, run `presenter.reset()`, then present its beats again.
- **Empty or garbled**: "Sorry, I didn't catch that. Could you say it again?"
  then `voice.py listen`.
- After answering, `voice.py listen --timeout 4`. Silence means carry on.

## 6. Checkpoint: "Did I get it right?"

When `presenter.state().checkpoint` is true, present the slide, then **stop
and wait** for the user: `voice.py listen --timeout 20` (in other modes, end
your turn). Then:

- **Yes / mostly yes**: record any tweaks with `presenter.agree`, then ask
  "Do you want me to walk through how I'd build it, or shall we skip to the
  decisions?" Go through the Technical slides, or jump to the last one, as they
  choose.
- **No / significantly off**: don't continue into the technical part. Discuss
  until you understand, update the Brief and Demo slides, run `check_deck.py`,
  republish to the same artifact, and re-present the demo.

## 7. Technical walkthrough (optional, on request)

Present the Technical slides the same way, at the depth the user asks for.
This is where implementation detail belongs: architecture, slices, tests,
risks. Tie it back to the demo ("that instant switch you saw comes from…").

## Wrap-up (always)

1. On the last slide, summarise what was agreed, aloud and on screen.
2. Update the deck so it reflects the agreed version (corrected demo,
   decisions on the last slide) and republish to the **same** artifact (same
   `file_path`). The link becomes the record of the meeting.
3. Update the written plan (plan file, TODO list, or chat summary).
4. Ask for an explicit go-ahead. **Do not start implementing until the user
   approves.** Stop any local server you started.

## Ground rules

- Demo first, technical second. If you catch yourself explaining *how* during
  the demo, move it to the Technical section.
- Keep it a conversation: short beats, plain spoken English, never read code
  aloud.
- Never put secrets, tokens or personal data in slides or narration. With an
  ElevenLabs key set, narration text is sent to ElevenLabs; with
  `SHOW_DISCUSS_STT=scribe`, the user's audio is too.
- Voice settings, troubleshooting and costs:
  [references/voice.md](references/voice.md).
