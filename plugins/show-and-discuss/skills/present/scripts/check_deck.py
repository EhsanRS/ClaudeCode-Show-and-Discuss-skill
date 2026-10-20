#!/usr/bin/env python3
"""Validate a filled-in presenter deck before it is published.

Usage:  python3 check_deck.py path/to/deck.html [--json]

Checks that every slide has a title and narration notes, that spot names are
unique, that every [[cue]] in the notes names a known verb and an existing
spot, and that the page only loads scripts from allowed CDNs. Exit status is
0 when there are no errors (warnings are allowed), 1 otherwise. Standard
library only, so it runs anywhere Python 3.10+ does.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser

CUE_RE = re.compile(r"\[\[([^\]]+)\]\]")
SPOT_VERBS = {"point", "click", "spotlight", "highlight"}
OTHER_VERBS = {"go", "next", "prev", "scroll", "caption", "captions", "clear", "overview", "theme"}
ALLOWED_SCRIPT_HOSTS = (
    "https://cdnjs.cloudflare.com/",
    "https://cdn.jsdelivr.net/npm/",
    "https://unpkg.com/",
    "https://cdn.tailwindcss.com",
    "https://code.jquery.com/",
)
TEMPLATE_TITLE = "Settings Dark Mode"
REQUIRED_RUNTIME = ("window.presenter", "beats:", "spotlight:", "point:")


@dataclass
class Slide:
    title: str | None
    line: int
    notes: str = ""
    spots: list[str] = field(default_factory=list)


class DeckParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.slides: list[Slide] = []
        self.title = ""
        self.scripts: list[str] = []
        self.inline_script = ""
        self._stack: list[str] = []
        self._slide_depth: int | None = None
        self._notes_depth: int | None = None
        self._in_title = False
        self._in_script = False

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = {k: (v or "") for k, v in attrs_list}
        if tag not in {"br", "img", "input", "meta", "link", "hr", "path", "rect", "circle", "line", "polyline"}:
            self._stack.append(tag)
        depth = len(self._stack)
        classes = attrs.get("class", "").split()
        if tag == "section" and "slide" in classes and self._slide_depth is None:
            self.slides.append(Slide(attrs.get("data-title"), self.getpos()[0]))
            self._slide_depth = depth
        elif tag == "aside" and "notes" in classes and self._slide_depth is not None:
            self._notes_depth = depth
        if "data-spot" in attrs and self.slides and self._slide_depth is not None:
            self.slides[-1].spots.append(attrs["data-spot"])
        if tag == "title":
            self._in_title = True
        if tag == "script":
            if attrs.get("src"):
                self.scripts.append(attrs["src"])
            else:
                self._in_script = True

    def handle_startendtag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = {k: (v or "") for k, v in attrs_list}
        if "data-spot" in attrs and self.slides and self._slide_depth is not None:
            self.slides[-1].spots.append(attrs["data-spot"])

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag == "script":
            self._in_script = False
        if tag in self._stack:
            while self._stack:
                depth = len(self._stack)
                popped = self._stack.pop()
                if self._notes_depth == depth:
                    self._notes_depth = None
                if self._slide_depth == depth:
                    self._slide_depth = None
                if popped == tag:
                    break

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        if self._in_script:
            self.inline_script += data
        if self._notes_depth is not None and self.slides:
            self.slides[-1].notes += data


def check(html: str) -> dict:
    parser = DeckParser()
    parser.feed(html)
    errors: list[str] = []
    warnings: list[str] = []

    title = parser.title.strip()
    if not title:
        errors.append("page has no <title>")
    elif title == TEMPLATE_TITLE:
        warnings.append("<title> is still the template's example title")
    elif not 1 <= len(title.split()) <= 6:
        warnings.append(f"<title> should be a short name (2–4 words), got {title!r}")

    if not parser.slides:
        errors.append('no <section class="slide"> elements found')

    seen: dict[str, int] = {}
    for number, slide in enumerate(parser.slides, start=1):
        for spot in slide.spots:
            if spot in seen:
                errors.append(f"spot {spot!r} on slide {number} duplicates slide {seen[spot]}")
            else:
                seen[spot] = number

    for number, slide in enumerate(parser.slides, start=1):
        where = f"slide {number} (line {slide.line})"
        if not slide.title:
            warnings.append(f"{where} has no data-title")
        notes = re.sub(r"\s+", " ", slide.notes).strip()
        if not notes:
            errors.append(f'{where} has no <aside class="notes"> narration')
            continue
        spoken = CUE_RE.sub("", notes).strip()
        if len(spoken.split()) > 220:
            warnings.append(f"{where} narration is {len(spoken.split())} words — aim for under ~150")
        for cue in CUE_RE.findall(notes):
            parts = cue.strip().split(None, 1)
            verb = parts[0].lower() if parts else ""
            arg = parts[1].strip() if len(parts) > 1 else ""
            if verb in SPOT_VERBS:
                if not arg:
                    errors.append(f"{where}: cue [[{cue}]] needs a spot name")
                elif arg not in seen:
                    errors.append(f"{where}: cue [[{cue}]] refers to unknown spot {arg!r}")
                elif seen[arg] != number:
                    warnings.append(f"{where}: cue [[{cue}]] points at a spot on slide {seen[arg]}")
            elif verb not in OTHER_VERBS:
                errors.append(f"{where}: unknown cue verb in [[{cue}]]")

    for src in parser.scripts:
        if not src.startswith(ALLOWED_SCRIPT_HOSTS):
            errors.append(f"external script not on an allowed CDN: {src}")
    missing = [token for token in REQUIRED_RUNTIME if token not in parser.inline_script]
    if missing:
        errors.append(f"presenter runtime script is missing or modified (no {', '.join(missing)})")

    return {
        "ok": not errors,
        "title": title,
        "slides": [{"number": i, "title": s.title, "spots": s.spots} for i, s in enumerate(parser.slides, start=1)],
        "errors": errors,
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("path")
    ap.add_argument("--json", action="store_true", help="print the full report as JSON")
    args = ap.parse_args(argv)
    with open(args.path, encoding="utf-8") as fh:
        report = check(fh.read())
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        status = "OK" if report["ok"] else "FAILED"
        print(f"{status}: {report['title'] or '(untitled)'} — {len(report['slides'])} slides")
        for msg in report["errors"]:
            print(f"  error:   {msg}")
        for msg in report["warnings"]:
            print(f"  warning: {msg}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
