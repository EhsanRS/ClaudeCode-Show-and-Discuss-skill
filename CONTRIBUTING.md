# Contributing

Thanks for helping improve Show and Discuss. This guide covers the development
setup, how to test a change, and the conventions the project follows.

## Setup

You need [uv](https://docs.astral.sh/uv/) and Python 3.10+.

```bash
git clone https://github.com/EhsanRS/ClaudeCode-Show-and-Discuss-skill.git
cd ClaudeCode-Show-and-Discuss-skill
uv run --group dev pytest          # creates the dev environment on first run
```

## Checks

```bash
uv run --group dev ruff check .
uv run --group dev ruff format --check .
uv run --group dev pytest                                   # unit + validator tests
uv run --group dev --with playwright pytest tests/test_presenter_browser.py   # needs Chromium
claude plugin validate . && claude plugin validate ./plugins/show-and-discuss
```

For the browser tests, install Chromium once with
`uv run --with playwright playwright install chromium`.

## Trying your changes in Claude Code

Load the plugin from your working copy for one session:

```bash
claude --plugin-dir ./plugins/show-and-discuss
```

Then run `/show-and-discuss:present` on a small plan. Use `/reload-plugins`
after editing. To test the voice helper on its own:

```bash
uv run plugins/show-and-discuss/skills/present/scripts/voice.py doctor
uv run plugins/show-and-discuss/skills/present/scripts/voice.py say "Testing. Interrupt me by talking."
```

## Conventions

- **Presenter template:** keep it self-contained (no external requests), keep
  colours in the CSS tokens with light and dark values, and keep the
  `window.presenter` API backwards compatible. Add a browser test for new API.
- **voice.py:** standard library plus the dependencies declared in its PEP 723
  header. Heavy imports stay inside functions so `doctor` and the tests run
  without audio libraries. Every command prints exactly one JSON object.
- **SKILL.md:** keep it short and procedural; put details in `references/`.
- **Versioning:** bump `version` in `plugin.json` and `__version__` in
  `voice.py` together (a test enforces this), and add a CHANGELOG entry.
- **Commits:** small, focused, with a message that explains *why*.
