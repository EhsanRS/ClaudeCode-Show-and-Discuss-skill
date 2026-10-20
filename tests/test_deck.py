"""Tests for the presenter template and the deck validator."""

import json
from pathlib import Path

import check_deck
from conftest import SKILL_DIR

TEMPLATE = SKILL_DIR / "assets" / "presenter-template.html"
ROOT = Path(__file__).resolve().parents[1]


def template():
    return TEMPLATE.read_text(encoding="utf-8")


def test_template_is_valid():
    report = check_deck.check(template())
    assert report["ok"], report["errors"]
    assert len(report["slides"]) >= 5


def test_template_follows_artifact_contract():
    html = template()
    assert ':root:not([data-theme="light"])' in html
    assert ':root[data-theme="dark"]' in html
    assert "prefers-color-scheme: dark" in html
    assert 'name="viewport"' in html
    assert "<script src" not in html  # fully self-contained


def test_template_has_slide_markers():
    html = template()
    assert html.count("══ SLIDES:START") == 1
    assert html.count("══ SLIDES:END") == 1
    assert html.index("══ SLIDES:START") < html.index("══ SLIDES:END")


def test_duplicate_spot_is_an_error():
    html = template().replace('data-spot="meaning"', 'data-spot="ask"')
    report = check_deck.check(html)
    assert not report["ok"]
    assert any("duplicates" in e for e in report["errors"])


def test_unknown_cue_target_is_an_error():
    report = check_deck.check(template().replace("[[point store]]", "[[point nowhere]]"))
    assert any("unknown spot 'nowhere'" in e for e in report["errors"])


def test_unknown_cue_verb_is_an_error():
    report = check_deck.check(template().replace("[[point store]]", "[[dance store]]"))
    assert any("unknown cue verb" in e for e in report["errors"])


def test_missing_notes_is_an_error():
    html = template().replace('<aside class="notes">Thanks for joining.', '<aside class="nope">Thanks for joining.', 1)
    report = check_deck.check(html)
    assert any("no <aside" in e for e in report["errors"])


def test_disallowed_script_is_an_error():
    html = template().replace("</head>", '<script src="https://evil.example/x.js"></script></head>')
    assert any("allowed CDN" in e for e in check_deck.check(html)["errors"])


def test_allowed_cdn_script_passes():
    html = template().replace(
        "</head>", '<script src="https://cdnjs.cloudflare.com/ajax/libs/mermaid/10.9.1/mermaid.min.js"></script></head>'
    )
    assert check_deck.check(html)["ok"]


def test_cli_exit_codes(tmp_path, capsys):
    good = tmp_path / "good.html"
    good.write_text(template(), encoding="utf-8")
    assert check_deck.main([str(good), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    bad = tmp_path / "bad.html"
    bad.write_text("<html><title>x</title></html>", encoding="utf-8")
    assert check_deck.main([str(bad)]) == 1


def test_manifests_are_consistent():
    marketplace = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    plugin = json.loads((ROOT / "plugins" / "show-and-discuss" / ".claude-plugin" / "plugin.json").read_text())
    entry = next(p for p in marketplace["plugins"] if p["name"] == plugin["name"])
    assert (ROOT / entry["source"]).resolve() == (ROOT / "plugins" / "show-and-discuss").resolve()
    assert marketplace["owner"]["name"]
    import voice

    assert plugin["version"] == voice.__version__


def test_action_must_target_a_demo_root():
    report = check_deck.check(template().replace('data-action="app=dark"', 'data-action="nope=dark"'))
    assert any("'nope', which has no data-demo-state" in e for e in report["errors"])


def test_malformed_action_is_an_error():
    report = check_deck.check(template().replace('data-action="app=dark"', 'data-action="app"'))
    assert any("must look like 'root=value'" in e for e in report["errors"])


def test_state_cue_needs_demo_root_and_value():
    html = template().replace("[[click opt-dark]]", "[[state ask dark]] [[state app]]")
    errors = check_deck.check(html)["errors"]
    assert any("'ask' has no data-demo-state" in e for e in errors)
    assert any("[[state app]] needs a value" in e for e in errors)


def test_type_and_reveal_arguments():
    html = template().replace("[[click opt-dark]]", "[[type opt-dark]] [[reveal devices twice]]")
    errors = check_deck.check(html)["errors"]
    assert any("needs text to type" in e for e in errors)
    assert any("reveal takes a spot" in e for e in errors)


def test_missing_checkpoint_and_demo_are_warnings():
    html = template().replace(" data-checkpoint", "").replace('data-section="Demo"', 'data-section="Other"')
    report = check_deck.check(html)
    assert report["ok"]
    assert any("checkpoint" in w for w in report["warnings"])
    assert any('data-section="Demo"' in w for w in report["warnings"])


def test_report_includes_sections():
    slides = check_deck.check(template())["slides"]
    assert slides[0]["section"] == "Brief"
    assert [s["number"] for s in slides if s["checkpoint"]] == [4]
