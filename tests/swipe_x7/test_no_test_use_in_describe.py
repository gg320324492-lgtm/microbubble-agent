"""W90-X-7 guard: spec must not call `test.use(...)` inside a `test.describe(...)` block.

Background
----------
- W89-X-14 reported ``Cannot use({ defaultBrowserType }) in a describe group`` for
  ``web/tests/e2e/mobile_swipe_gesture.spec.js`` when run under Playwright 1.61+.
- W89-X-21 confirmed the cause was a pre-existing bug: the spec called
  ``test.use({ ...devices['iPhone 13'], hasTouch, isMobile })`` from inside three
  ``test.describe(...)`` blocks. The acceptable places for ``test.use(...)`` are:
    1. file scope (top-level, outside any describe) — only in Playwright >= 1.62
    2. inside ``projects[].use`` of ``playwright.config.js`` (always legal)
- For the current project (Playwright 1.61+ with config-only device injection),
  the right fix is: move device profile to a dedicated ``projects[]`` entry, then
  delete every ``test.use(...)`` from the spec. This test enforces that rule by
  walking the spec source and rejecting any ``test.use(...)`` that lives inside a
  ``test.describe(...)`` block.

The test covers ``web/tests/e2e/mobile_swipe_gesture.spec.js`` explicitly (the file
W89-X-14/W89-X-21 inspected). It can be extended to other Playwright specs later.
"""
from __future__ import annotations

from pathlib import Path
import re

SPEC_CANDIDATES = [
    Path("web/tests/e2e/mobile_swipe_gesture.spec.js"),
    Path("web/tests/visual/e2e/mobile_swipe_gesture.spec.js"),
]


def _find_spec() -> Path:
    for p in SPEC_CANDIDATES:
        if p.exists():
            return p
    raise AssertionError(
        "mobile_swipe_gesture spec not found at any of: "
        + ", ".join(str(p) for p in SPEC_CANDIDATES)
    )


def _iter_describe_blocks(text: str) -> list[tuple[int, str]]:
    """Return ``(start_line_1based, body)`` for every top-level describe block.

    We treat the line containing ``test.describe(`` as the block opener, and the
    next blank section break (``test.describe(`` of the following block, or end
    of file) as the boundary. We then narrow the body to the matched ``{ ... }``
    via a small brace counter, so the inspection window contains only lines
    physically inside the describe callback.
    """
    lines = text.splitlines()
    opens: list[int] = [
        i
        for i, l in enumerate(lines)
        if "test.describe(" in l and not l.lstrip().startswith("//")
    ]
    blocks: list[tuple[int, str]] = []
    for k, start in enumerate(opens):
        # Walk forward to find the matching close, balancing braces.
        depth = 0
        seen_open = False
        end = start
        for j in range(start, len(lines)):
            for ch in lines[j]:
                if ch == "{":
                    depth += 1
                    seen_open = True
                elif ch == "}":
                    depth -= 1
            if seen_open and depth == 0:
                end = j
                break
        body = "\n".join(lines[start + 1 : end])
        blocks.append((start + 1, body))
    return blocks


def test_no_test_use_in_describe() -> None:
    spec = _find_spec()
    text = spec.read_text(encoding="utf-8")

    for start_line, body in _iter_describe_blocks(text):
        for offset, line in enumerate(body.splitlines(), start=1):
            if re.search(r"\btest\.use\s*\(", line):
                raise AssertionError(
                    f"{spec}:{start_line + offset}: test.use(...) called inside "
                    f"a test.describe(...) block (W89-X-14/W89-X-21 pre-existing "
                    f"bug). Move device config to playwright.config.js projects[] "
                    f"instead.\n  offending line: {line.strip()}"
                )


def test_no_top_level_test_use() -> None:
    """Top-level ``test.use(...)`` outside any describe is also rejected.

    Playwright 1.61 (the version hoisted at the repo root) raises the same
    "Playwright Test did not expect test.use() to be called here" error whether
    the call lives at file scope or inside a describe — the only accepted home
    is ``projects[].use`` in ``playwright.config.js``. We enforce the same rule
    so future contributors don't reintroduce the pattern.

    The check targets calls with no leading whitespace (``test.use(`` in column
    0) **and** that live outside every ``test.describe(...)`` block, so that
    nested/indented calls inside ``test.describe(...)`` are flagged by
    ``test_no_test_use_in_describe`` instead of by this assertion.
    """
    spec = _find_spec()
    text = spec.read_text(encoding="utf-8")
    lines = text.splitlines()
    describe_ranges = [
        (start, start + body.count("\n") + 1)
        for start, body in _iter_describe_blocks(text)
    ]
    for idx, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("//"):
            continue
        if not re.match(r"^test\.use\s*\(", stripped):
            continue
        # Is this line outside every describe block?
        if any(start <= idx <= end for start, end in describe_ranges):
            continue
        raise AssertionError(
            f"{spec}:{idx + 1}: top-level `test.use(...)` is not portable across "
            f"Playwright versions. Move device config to "
            f"playwright.config.js projects[] instead.\n  offending line: "
            f"{line.strip()}"
        )
