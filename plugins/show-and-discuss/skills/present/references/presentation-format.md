# Presentation format

How to fill `assets/presenter-template.html`. The template's example deck (a
7-slide "dark mode" plan) shows every component in use. Copy patterns from it.

## Authoring contract

```html
<section class="slide" data-title="Approach">          <!-- one per slide, in order -->
  <div class="kicker">How</div>                         <!-- small label above the heading -->
  <h2>Approach</h2>
  <div class="card" data-spot="store">…</div>           <!-- data-spot = pointer target -->
  <aside class="notes">                                  <!-- narration, never shown on the slide -->
    Here is how it fits together. [[spotlight flow]] The toggle writes…
    [[point store]] usePreference saves it locally…
  </aside>
</section>
```

- **`data-title`**: short name shown in the control bar and used by
  `presenter.go("Approach")`.
- **`data-spot`**: unique across the whole deck, kebab-case. Put it on
  whatever you will talk about. Cards, list items, table rows and SVG shapes
  all work.
- **`<aside class="notes">`**: what you will say. Written to be *heard*:
  short sentences, no markdown, no code, numbers rounded the way you'd say them.
- **Cues** `[[verb arg]]` inside notes split narration into *beats*. The cue
  runs, then the text after it is spoken. Verbs:

| Cue | Effect |
|---|---|
| `[[point spot]]` | Animate the pointer to the spot. |
| `[[click spot]]` | Pointer plus a click ripple. Use it for "you press this". |
| `[[spotlight spot]]` | Dim everything except the spot. |
| `[[highlight spot]]` | Pulsing outline, no dimming. |
| `[[scroll bottom]]`, `[[scroll top]]`, `[[scroll 300]]` | Scroll the current slide. |
| `[[clear]]` | Remove pointer, spotlight and highlight. |

A cue applies until the next cue or slide change. Use about 1–4 cues per slide.
A cue on every sentence makes the pointer jittery.

## Components (all theme-aware)

| Need | Markup |
|---|---|
| Title slide | `<div class="title-slide"><div class="kicker">…</div><h1>…</h1><p class="lead">…</p><div class="meta">…</div></div>` |
| Cards in a grid | `<div class="grid"><div class="card"><h3>…</h3><p>…</p></div>…</div>` |
| Ordered slices or steps | `<ol class="steps"><li><strong>Title</strong><span>detail</span></li>…</ol>` |
| Before / after | `<div class="compare"><div><div class="label">Before</div>…</div><div><div class="label">After</div>…</div></div>` |
| UI mock-up | `<div class="mock"><div class="mock-bar"><i></i><i></i><i></i><span class="url">app/path</span></div><div class="mock-body">…real HTML…</div></div>` |
| Diagram | Inline `<svg class="diagram" viewBox="…">` with `.box`, `.box.hl`, `text`, `.sub`, `.edge`, `.arrow` classes (see the Approach slide). |
| Code | `<pre><code>…</code></pre>`. Keep it to about 15 lines; show, don't read aloud. |
| Table | Plain `<table>` with `<thead>`. |
| Status tags | `<span class="pill ok|warn|risk|accent">…</span>` |
| Callout | `<div class="callout"><strong>Note:</strong> …</div>` |
| Simple list | `<ul class="clean"><li>…</li></ul>` |
| Decisions record | `<ul class="clean" data-spot="agreed"><li class="pz-placeholder">Filled in live as we discuss.</li></ul>`, filled by `presenter.agree(text)` |

Mock-ups should look like the real product. Reuse its actual labels, layout
and copy where you know them. Inline `style` is fine for one-off tweaks. Use the
CSS variables (`var(--accent)`, `var(--muted)`, `var(--surface)`, …) rather
than hard-coded colours so dark mode keeps working.

## Outlines by meeting type

Pick one, then cut anything that doesn't earn its place. Every deck ends with a
decisions slide that has the `agreed` list.

**Dev plan (default, 6–8 slides)**
1. Title: what, repo, effort, status pill "awaiting go-ahead"
2. Context: why this, why now (evidence)
3. Current state: how it works today (diagram or code pointer)
4. Approach: the design (diagram), key choices and why
5. Mock-up: what the user will see (UI, CLI output, API shape)
6. Slices: ordered, each shippable, with its tests
7. Risks & open questions (table with levels and mitigations)
8. Decisions needed plus the agreed list

**Slice review (4–5 slides)**: Goal of this slice → what changes (files, before/after) → how it will be tested → risks → decisions.

**Standup (3–4 slides)**: Done since last time → doing next → blockers and asks → decisions.

**Lab meeting / results (6–8 slides)**: Question → why it matters → method → results (figures as SVG or tables) → what it means and caveats → next experiments → decisions.

**Design review (5–7 slides)**: Problem → constraints → options compared (table) → recommendation → mock-up → trade-offs → decisions.

## Narration style

- 40–120 words per slide. The slide carries the detail; the voice carries the
  *why*.
- Open the deck by saying what it is, how long it takes (~30 s per slide), and
  that the user can interrupt by talking.
- Say the recommendation first, then the reasoning.
- End the decisions slide with a direct question.
- Never read code, paths or long numbers aloud. Say "the preferences hook",
  not "src/hooks/usePreference.ts".
