from pathlib import Path

DESKTOP_VIEW = Path(__file__).resolve().parents[2] / "web" / "src" / "views" / "desktop" / "DesktopFileCommentsView.vue"


def test_route_query_handled():
    """DesktopFileCommentsView must read and watch route.query."""
    content = DESKTOP_VIEW.read_text(encoding="utf-8")
    assert "useRoute" in content, "DesktopFileCommentsView must import useRoute"
    assert "route.query" in content, "DesktopFileCommentsView must read route.query"


def test_dark_mode_class():
    """DesktopFileCommentsView must expose its dark-mode class."""
    content = DESKTOP_VIEW.read_text(encoding="utf-8")
    assert "isDark" in content or "theme-dark" in content or "useThemeStore" in content
