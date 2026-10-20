# Presentation format

How to fill `assets/presenter-template.html`. Its example deck (an 8-slide
"dark mode for Settings" demo) shows every component in use. Copy patterns
from it.

## Deck structure: demo first

| Section | Slides | Purpose | `data-section` |
|---|---|---|---|
| Brief | 1 | *You asked* / *I took that to mean* / *Not included* | `Brief` |
| Demo | 1–4 | The finished result in use, as the user will experience it | `Demo` |
| Checkpoint | 1 | *I'll build* / *I won't build* / *Assumptions*, then "Did I get it right?" | `Check` plus the `data-checkpoint` attribute |
| Technical | 2–5 | How: approach, slices, risks, then decisions plus the `agreed` list | `Technical` |

The demo is told from the user's point of view ("you open Settings, pick
Dark, and…"). Implementation words such as *hook*, *table* or *endpoint*
belong in the Technical section.

## Authoring contract

```html
<section class="slide" data-title="Switching theme" data-section="Demo">   <!-- one per slide -->
  <div class="kicker">Demo · what you'll get</div>
  <h2>Pick a theme, see it instantly</h2>
  …
  <aside class="notes">                                    <!-- narration, never shown on the slide -->
    Here's the Settings page. [[click opt-dark]] Pick Dark, and it switches straight away.
  </aside>
</section>
```

- **`data-title`**: short name shown in the control bar; `presenter.go("Switching theme")` works.
- **`data-section`**: shown as a tag in the control bar and returned by `presenter.state()`.
- **`data-spot`**: unique across the deck, kebab-case. Put it on whatever
  you'll talk about or interact with (cards, buttons, rows, SVG shapes).
- **`<aside class="notes">`**: written to be *heard*: short sentences, no
  markdown, no code, numbers rounded the way you'd say them.

## Cues

`[[verb arg]]` inside the notes splits narration into *beats*. The cue runs,
then the text after it is spoken.

| Cue | Effect |
|---|---|
| `[[point spot]]` | Animate the pointer to the spot. |
| `[[click spot]]` | Pointer plus click ripple, then runs the spot's `data-action` (if any). |
| `[[type spot Some text]]` | Pointer to an input (or any element) and types the text. |
| `[[state root value]]` | Set a demo root's state directly. |
| `[[reveal spot]]` / `[[reveal spot all]]` | Show the next (or every) hidden `data-reveal` item inside the spot. |
| `[[spotlight spot]]` | Dim everything except the spot. |
| `[[highlight spot]]` | Pulsing outline, no dimming. |
| `[[scroll bottom]]`, `[[scroll top]]`, `[[scroll 300]]` | Scroll the current slide. |
| `[[clear]]` | Remove pointer, spotlight and highlight. |
| `[[reset]]` | Restore the current slide's demo: initial states, typed text, hidden reveals. |

Use about 1–5 cues per slide. Demo slides can use more, since the actions are
the content.

## Interactive demos

The mocks are real HTML, so they can behave like the real thing. They work
both when Claude drives them and when the user clicks them in a shared link.

```html
<div class="mock-body demo-app" data-spot="app" data-demo-state="light">   <!-- demo root -->
  <button class="demo-option" data-spot="opt-dark"
          data-action="app=dark" data-active-when="dark">Dark</button>      <!-- click → app becomes "dark" -->
  <p data-when="dark"><span class="toast">✓ Saved</span></p>             <!-- visible only in "dark" -->
  <p data-when="light system">…</p>                                      <!-- visible in either state -->
</div>
```

| Attribute | Meaning |
|---|---|
| `data-demo-state="v"` | Makes the element a demo root with current state `v` (also needs a `data-spot`). The initial value is restored by `[[reset]]`. |
| `data-when="a b"` | Inside a root: shown only in states `a` or `b`. |
| `data-active-when="a"` | Inside a root: gets the `.is-active` class in state `a`. |
| `data-action="root=v"` | Clicking sets `root` to state `v`. Comma-separate to set several roots. |
| `data-reveal` | Hidden while presenting until a `[[reveal …]]` cue shows it (always visible when the user browses or prints). |

Style state changes with a slide-local `<style>` block, e.g.
`.demo-app[data-demo-state="dark"] { background: #16181c; color: #eee; }`.
Keep states few (2–4) and the flow linear: the demo has to be followed by ear.

**Terminal or API demos** use `data-reveal` lines:

```html
<div class="terminal" data-spot="term">
  <div class="cmd" data-reveal>acme deploy --preview</div>
  <div class="out" data-reveal>Building… 42 files changed</div>
  <div class="ok" data-reveal>✓ Preview ready at https://pr-118.acme.dev</div>
</div>
```

Narrate with `[[reveal term]]` before each line ("you run deploy with
preview…").

## Components (all theme-aware)

| Need | Markup |
|---|---|
| Title / brief | `<div class="title-slide"><div class="kicker">…</div><h1>…</h1><p class="lead">…</p></div>` |
| Cards in a grid | `<div class="grid"><div class="card"><h3>…</h3><p>…</p></div>…</div>` |
| UI mock-up frame | `<div class="mock"><div class="mock-bar"><i></i><i></i><i></i><span class="url">app/path</span></div><div class="mock-body">…</div></div>` |
| Option buttons | `<button class="demo-option" data-action="…" data-active-when="…">` |
| Toast / confirmation | `<span class="toast">✓ Saved</span>` |
| Terminal | `<div class="terminal">` with `.cmd` / `.out` / `.ok` / `.err` lines |
| Before / after | `<div class="compare"><div><div class="label">Before</div>…</div><div><div class="label">After</div>…</div></div>` |
| Ordered slices | `<ol class="steps"><li><strong>Title</strong><span>detail</span></li>…</ol>` |
| Diagram | Inline `<svg class="diagram">` with `.box`, `.box.hl`, `text`, `.sub`, `.edge`, `.arrow` |
| Code | `<pre><code>…</code></pre>`. About 15 lines max; Technical section only. |
| Table, status tags, callout, list | `<table>`, `<span class="pill ok|warn|risk|accent">`, `<div class="callout">`, `<ul class="clean">` |
| Decisions record | `<ul class="clean" data-spot="agreed"><li class="pz-placeholder">Filled in live as we discuss.</li></ul>`, filled by `presenter.agree(text)` |

Use the CSS variables (`var(--accent)`, `var(--muted)`, `var(--surface)`, …)
rather than hard-coded colours for slide chrome, so dark mode keeps working.
Hard-coded colours *inside* a mock are fine when they depict the product.

## Outlines by occasion

- **Feature or change (default)**: Brief → Demo of the main flow (1–2) → Demo
  of an edge case or "it remembers / it's fast / it fails gracefully" (1) →
  Checkpoint → How it works → Slices → Risks → Decisions.
- **Slice review**: Brief (this slice) → Demo of what this slice adds →
  Checkpoint → What changes (before/after) → Tests → Decisions.
- **Standup**: Brief (the goal) → Demo of what's done since last time →
  Checkpoint ("is this on track?") → Next and blockers → Decisions.
- **Lab meeting / results**: Brief (the question) → The result (figure or
  table) → What it means → Checkpoint ("does this answer the question?") →
  Method → Caveats → Next experiments.
- **Design review**: Brief → Demo of the recommended design → Checkpoint →
  Options considered → Trade-offs → Decisions.

## Narration style

- 40–120 words per slide. The slide carries the detail; the voice carries the story.
- Speak the demo in the second person and present tense: "you pick Dark, and
  it switches".
- End the checkpoint with a direct question, then stop talking.
- Never read code, paths or long numbers aloud.
