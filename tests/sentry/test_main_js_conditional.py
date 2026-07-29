"""W87-B-1: static hard gates for conditional browser reporting and SW bridge."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MAIN_JS = (REPO_ROOT / "web/src/main.js").read_text(encoding="utf-8")
SENTRY_UTIL = (REPO_ROOT / "web/src/utils/sentry.js").read_text(encoding="utf-8")
SW_JS = (REPO_ROOT / "web/src/sw.js").read_text(encoding="utf-8")


def test_vite_dsn_guard_exists():
    assert "if (import.meta.env.VITE_SENTRY_DSN && !import.meta.env.DEV)" in MAIN_JS
    assert "Sentry.init({" in MAIN_JS


def test_dev_mode_is_rejected_twice():
    assert "!import.meta.env.DEV" in MAIN_JS
    assert "if (import.meta.env.DEV) return null" in MAIN_JS
    assert "beforeSend(event)" in MAIN_JS


def test_no_pii_and_low_trace_sample():
    assert "sendDefaultPii: false" in MAIN_JS
    assert "tracesSampleRate: 0.1" in MAIN_JS


def test_reporting_helpers_are_noops_until_initialized():
    assert "window.__SENTRY_INITIALIZED__ === true" in SENTRY_UTIL
    assert SENTRY_UTIL.count("if (!isSentryInitialized()) return") == 2
    assert "window.__SENTRY_INITIALIZED__ = true" in MAIN_JS


def test_sw_failure_bridge_is_connected():
    assert "type: 'SW_INSTALL_FAILED'" in SW_JS
    assert "event.data?.type === 'SW_INSTALL_FAILED'" in MAIN_JS
    assert "reportMessage('SW install failed', 'warning')" in MAIN_JS


def test_sw_only_posts_failure_from_catch_block():
    catch_index = SW_JS.index("catch (e)", SW_JS.index("self.addEventListener('install'"))
    message_index = SW_JS.index("type: 'SW_INSTALL_FAILED'")
    install_end = SW_JS.index("// v28 step 33", message_index)
    assert catch_index < message_index < install_end
