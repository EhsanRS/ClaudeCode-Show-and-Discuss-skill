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
    assert state["total"] == 8
    assert state["section"] == "Brief"
    assert state["checkpoint"] is False
    assert state["notes"]


def test_navigation_by_number_title_and_spot(page):
    assert page.evaluate("presenter.go(5).title") == "How it works"
    assert page.evaluate("presenter.go('Risks').number") == 7
    assert page.evaluate("presenter.go('theme-choice').number") == 2
    assert page.evaluate("presenter.next().number") == 3
    assert page.evaluate("presenter.prev().number") == 2
    assert page.evaluate("presenter.go(99).number") == 8  # clamps


def test_beats_strip_cues_from_captions(page):
    beats = page.evaluate("presenter.beats(5)")
    assert beats[0]["cue"] is None
    assert [b["cue"] for b in beats[1:]] == ["spotlight flow", "point store", "spotlight no-flash"]
    notes = page.evaluate("presenter.go(5).notes")
    assert "[[" not in notes


def test_spotlight_and_pointer_follow_target(page):
    page.evaluate("presenter.run('go 5; spotlight flow; point store')")
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
    p.goto(TEMPLATE_URL + "#2/theme-choice/spotlight")
    state = p.evaluate("presenter.state()")
    assert state["number"] == 2
    assert state["spotlight"] == "theme-choice"
    p.close()


def test_keyboard_navigation(page):
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowRight")
    assert page.evaluate("presenter.state().number") == 3
    page.keyboard.press("End")
    assert page.evaluate("presenter.state().number") == 8
    page.keyboard.press("c")
    assert page.evaluate("presenter.state().captions") is True


def test_agree_escapes_and_replaces_placeholder(page):
    page.evaluate("presenter.go(8); presenter.agree('Use <b>Postgres</b>')")
    html = page.inner_html('[data-spot="agreed"]')
    assert "pz-placeholder" not in html
    assert "&lt;b&gt;Postgres&lt;/b&gt;" in html


def test_post_message_commands(page):
    page.evaluate("window.postMessage({presenter: 'go 6; highlight slice-1'}, '*')")
    page.wait_for_timeout(200)
    assert page.evaluate("presenter.state().number") == 6
    assert page.locator('[data-spot="slice-1"].pz-hl').count() == 1


def test_mobile_has_no_horizontal_scroll(browser):
    p = browser.new_page(viewport={"width": 360, "height": 740})
    p.goto(TEMPLATE_URL)
    for n in range(1, 9):
        p.evaluate(f"presenter.go({n})")
        assert p.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"slide {n} overflows"
    p.close()


# ── Demo-first structure and interactive demos ──────────────────────────────

APP_STATE = "document.querySelector('[data-spot=app]').getAttribute('data-demo-state')"


def test_outline_is_demo_first_with_checkpoint(page):
    outline = page.evaluate("presenter.outline()")
    sections = [s["section"] for s in outline]
    assert sections[0] == "Brief"
    assert sections.index("Demo") < sections.index("Check") < sections.index("Technical")
    assert [s["number"] for s in outline if s["checkpoint"]] == [4]


def test_click_cue_runs_demo_action(page):
    page.evaluate("presenter.go(2); presenter.run('click opt-dark')")
    page.wait_for_timeout(900)
    assert page.evaluate(APP_STATE) == "dark"
    assert page.is_visible("[data-when=dark]")
    assert "is-active" in page.get_attribute("[data-spot=opt-dark]", "class")
    page.evaluate("presenter.run('click opt-system')")
    page.wait_for_timeout(900)
    assert not page.is_visible("[data-when=dark]")
    assert page.is_visible("[data-when=system]")


def test_user_can_click_the_mock(page):
    page.evaluate("presenter.go(2)")
    page.click("[data-spot=opt-dark]")
    assert page.evaluate(APP_STATE) == "dark"


def test_state_cue_and_reset(page):
    page.evaluate("presenter.go(2); presenter.run('state app dark')")
    assert page.evaluate(APP_STATE) == "dark"
    page.evaluate("presenter.reset()")
    assert page.evaluate(APP_STATE) == "light"


def test_reveal_only_hides_while_presenting(page):
    def visibility():
        return page.evaluate("getComputedStyle(document.querySelector('[data-spot=phone]')).visibility")

    page.evaluate("presenter.go(3)")
    assert visibility() == "visible"  # someone browsing the link sees everything
    page.evaluate("presenter.beats()")  # Claude starts presenting
    assert visibility() == "hidden"
    page.evaluate("presenter.run('reveal devices')")
    assert visibility() == "visible"
    assert page.evaluate("getComputedStyle(document.querySelector('[data-spot=no-flash-demo]')).visibility") == "hidden"
    page.evaluate("presenter.run('reveal devices')")
    assert (
        page.evaluate("getComputedStyle(document.querySelector('[data-spot=no-flash-demo]')).visibility") == "visible"
    )
    page.evaluate("presenter.reset()")
    assert visibility() == "hidden"


def test_type_fills_text_and_reset_restores(page):
    page.evaluate("presenter.go(1); presenter.run('type title Hello there')")
    page.wait_for_timeout(800)
    assert page.inner_text("[data-spot=title]") == "Hello there"
    page.evaluate("presenter.reset()")
    assert page.inner_text("[data-spot=title]") == "Dark mode for Settings"


def test_hash_click_runs_action(browser):
    p = browser.new_page()
    p.goto(TEMPLATE_URL + "#2/opt-dark/click")
    p.wait_for_timeout(900)
    assert p.evaluate(APP_STATE) == "dark"
    p.close()


def test_control_bar_shows_section(page):
    page.evaluate("presenter.go(4)")
    assert page.text_content("#pz-title .section-tag") == "Check"
