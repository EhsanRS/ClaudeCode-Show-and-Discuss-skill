"""End-to-end tests of the presenter runtime in headless Chromium.

Skipped automatically when Playwright or a Chromium build is not installed.
Run with:  uv run --group dev --with playwright pytest tests/test_presenter_browser.py
"""

import pytest
from conftest import SKILL_DIR

playwright_api = pytest.importorskip("playwright.sync_api")
TEMPLATE_URL = (SKILL_DIR / "assets" / "presenter-template.html").as_uri()


@pytest.fixture(scope="module")
def browser():
    with playwright_api.sync_playwright() as pw:
        try:
            b = pw.chromium.launch()
        except Exception as exc:  # noqa: BLE001 — browser binary missing
            pytest.skip(f"Chromium not available: {exc}")
        yield b
        b.close()


@pytest.fixture
def page(browser):
    p = browser.new_page(viewport={"width": 1280, "height": 800})
    errors = []
    p.on("pageerror", lambda e: errors.append(str(e)))
    p.goto(TEMPLATE_URL)
    yield p
    assert errors == [], errors
    p.close()


def test_initial_state(page):
    state = page.evaluate("presenter.state()")
    assert state["number"] == 1
    assert state["total"] == 7
    assert state["notes"]


def test_navigation_by_number_title_and_spot(page):
    assert page.evaluate("presenter.go(3).title") == "Approach"
    assert page.evaluate("presenter.go('Risks').number") == 6
    assert page.evaluate("presenter.go('theme-choice').number") == 4
    assert page.evaluate("presenter.next().number") == 5
    assert page.evaluate("presenter.prev().number") == 4
    assert page.evaluate("presenter.go(99).number") == 7  # clamps


def test_beats_strip_cues_from_captions(page):
    beats = page.evaluate("presenter.beats(3)")
    assert beats[0]["cue"] is None
    assert [b["cue"] for b in beats[1:]] == ["spotlight flow", "point store", "spotlight no-flash"]
    notes = page.evaluate("presenter.go(3).notes")
    assert "[[" not in notes


def test_spotlight_and_pointer_follow_target(page):
    page.evaluate("presenter.run('go 3; spotlight flow; point store')")
    page.wait_for_timeout(900)
    spot = page.locator("#pz-spot").bounding_box()
    target = page.locator('[data-spot="flow"]').bounding_box()
    assert abs(spot["x"] - (target["x"] - 8)) < 2
    assert abs(spot["width"] - (target["width"] + 16)) < 2
    assert "on" in page.get_attribute("#pz-cursor", "class")
    page.evaluate("presenter.clear()")
    assert "on" not in (page.get_attribute("#pz-spot", "class") or "")


def test_hash_deep_link(browser):
    p = browser.new_page()
    p.goto(TEMPLATE_URL + "#4/theme-choice/spotlight")
    state = p.evaluate("presenter.state()")
    assert state["number"] == 4
    assert state["spotlight"] == "theme-choice"
    p.close()


def test_keyboard_navigation(page):
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowRight")
    assert page.evaluate("presenter.state().number") == 3
    page.keyboard.press("End")
    assert page.evaluate("presenter.state().number") == 7
    page.keyboard.press("c")
    assert page.evaluate("presenter.state().captions") is True


def test_agree_escapes_and_replaces_placeholder(page):
    page.evaluate("presenter.go(7); presenter.agree('Use <b>Postgres</b>')")
    html = page.inner_html('[data-spot="agreed"]')
    assert "pz-placeholder" not in html
    assert "&lt;b&gt;Postgres&lt;/b&gt;" in html


def test_post_message_commands(page):
    page.evaluate("window.postMessage({presenter: 'go 5; highlight slice-1'}, '*')")
    page.wait_for_timeout(200)
    assert page.evaluate("presenter.state().number") == 5
    assert page.locator('[data-spot="slice-1"].pz-hl').count() == 1


def test_mobile_has_no_horizontal_scroll(browser):
    p = browser.new_page(viewport={"width": 360, "height": 740})
    p.goto(TEMPLATE_URL)
    for n in range(1, 8):
        p.evaluate(f"presenter.go({n})")
        assert p.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"slide {n} overflows"
    p.close()
