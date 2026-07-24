"""Regression tests for standard multiline unified diff formatting."""

import difflib

from app.services.drive_version_diff_service import DriveVersionDiffService


def _compute(from_text: str, to_text: str):
    """Run the production helper with stable version labels."""
    return DriveVersionDiffService._compute_text_diff(
        from_text=from_text,
        to_text=to_text,
        from_label="v1",
        to_label="v2",
    )


def test_unified_diff_uses_standard_multiline_headers():
    """Header and hunk markers must not collapse into one compact line."""
    diff, changed_lines, additions, deletions = _compute(
        "hello\nworld\n",
        "hello\nmoon\n",
    )

    compact = "".join(difflib.unified_diff(
        ["hello\n", "world\n"],
        ["hello\n", "moon\n"],
        fromfile="v1",
        tofile="v2",
        lineterm="",
    ))

    assert compact.startswith("--- v1+++ v2@@")
    assert diff.startswith("--- v1\n+++ v2\n@@ ")
    assert "--- v1+++ v2" not in diff
    assert changed_lines == [2]
    assert additions > 0
    assert deletions > 0


def test_multiline_diff_preserves_real_line_boundaries():
    """A multi-hunk payload remains consumable as line-oriented unified diff."""
    from_text = "alpha\nbeta\ngamma\ndelta\nepsilon\nzeta\neta\ntheta\n"
    to_text = "alpha\nBETA\ngamma\ndelta\nepsilon\nzeta\neta\nTHETA\n"

    diff, changed_lines, additions, deletions = _compute(from_text, to_text)
    diff_lines = diff.splitlines()

    assert diff_lines[0] == "--- v1"
    assert diff_lines[1] == "+++ v2"
    assert any(line.startswith("@@ ") for line in diff_lines)
    assert "-beta" in diff_lines
    assert "+BETA" in diff_lines
    assert "-theta" in diff_lines
    assert "+THETA" in diff_lines
    assert diff.endswith("\n")
    assert changed_lines == [2, 8]
    assert additions == len("BETA") + len("THETA")
    assert deletions == len("beta") + len("theta")


def test_identical_and_empty_text_boundaries():
    """Identical and empty inputs produce an empty, well-defined diff."""
    for from_text, to_text in (("same\n", "same\n"), ("", "")):
        diff, changed_lines, additions, deletions = _compute(from_text, to_text)

        assert diff == ""
        assert changed_lines == []
        assert additions == 0
        assert deletions == 0
