# Driving the presentation in the browser

The deck exposes `window.presenter`. Every method returns `presenter.state()`,
so one JavaScript evaluation both acts and reports back:

```js
presenter.state()      // {number, total, title, notes, spots, captions, spotlight, overview}
presenter.outline()    // every slide: {number, title, spots, notes}
presenter.beats()      // current slide's narration beats: [{cue, text}]  (beats(n) for slide n)
presenter.go(3)        // or go("Approach") or go("spot-name")
presenter.next(); presenter.prev()
presenter.point("store")            // animated pointer
presenter.point("store", {click: true})
presenter.spotlight("flow")         // dim everything else
presenter.highlight("risk-contrast")
presenter.scrollTo("bottom")        // "top" | "bottom" | pixels | spot
presenter.captions(true)            // show the current slide's notes as subtitles
presenter.caption("Any text")       // show custom subtitle; caption(null) hides
presenter.agree("Keep scope to Settings only")   // add to the decisions list
presenter.clear()                   // remove pointer/spotlight/highlight
presenter.overview(true)            // all slides stacked (for reading); false to return
presenter.theme("dark")             // "light" | "dark" | null (follow system)
presenter.run("go 4; spotlight theme-choice")    // same verbs as cues, ;-separated
```

## Which browser tool

Use whichever is available. Load its skill first if one is listed
(`chrome-browser` for Claude in Chrome, `built-in-browser` for the desktop
app's pane).

| Tool family | Open the page | Run presenter commands |
|---|---|---|
| Claude in Chrome (`mcp__claude-in-chrome__*`) | Navigate a new tab to the URL | Its JavaScript tool: `presenter.run("…")` |
| Desktop browser pane (`mcp__Claude_Browser__*`, `mcp__remote-devices__Claude_Browser__*`) | Navigate the pane | Its evaluate/JavaScript tool, if present |
| Any tool without JavaScript evaluation | Navigate | Use **hash URLs** (below) and keyboard keys |

Tool names change between versions, so pick the tool by its description
(navigate, run JavaScript, press key) rather than an exact name.

## Step 1: confirm the API is reachable

After opening the page, evaluate `typeof presenter !== "undefined" && presenter.state()`.

- **Returns state**: drive the published artifact directly. Done.
- **`presenter` undefined**: the artifact is likely rendered inside a
  cross-origin frame the tool can't script. Use the local copy instead:

```bash
# serve the deck's folder on loopback only; remember the PID to stop it later
python3 -m http.server 8765 --bind 127.0.0.1 --directory "<deck folder>" >/dev/null 2>&1 &
```

Then open `http://127.0.0.1:8765/<deck file>.html`. Keep the artifact link
for the user to share and read later, and stop the server (`kill <PID>`) at
wrap-up.

## Step 2 (fallback): drive with hash URLs and keys

If no JavaScript evaluation is possible, navigate to the same page with a hash:

| URL suffix | Effect |
|---|---|
| `#3` | Go to slide 3 |
| `#3/store` | Slide 3, pointer on `store` |
| `#3/flow/spotlight` | Slide 3, spotlight `flow` |
| `#3/risk-contrast/highlight` | Slide 3, highlight |

Keys: `→`/`Space` next, `←` previous, `Home`/`End`, `C` captions, `O` overview,
`Esc` clear.

## Tips

- Turn captions on (`presenter.captions(true)`) in **Show** mode, and when the
  user is in a noisy place, so the narration is readable as well as audible.
- Before speaking a beat, run its cue. The pointer animates for about 0.7 s,
  which gives the eye time to land before the words start.
- After the user asks about something specific, `point`/`spotlight` it while
  answering.
- If the user scrolls or clicks around themselves, call `presenter.state()`
  before the next beat to see where they are. Don't yank them back mid-read;
  ask "Shall I continue from slide N?"
