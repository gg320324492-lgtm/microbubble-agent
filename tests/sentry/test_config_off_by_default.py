"""W87-B-1: Sentry is opt-in and never initializes without an explicit DSN."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_sentry_dsn_defaults_to_none(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)

    from app.config import Settings

    assert Settings(_env_file=None).SENTRY_DSN is None


def test_main_import_does_not_initialize_sentry_without_dsn():
    """Import app.main in a clean process so module cache cannot create a false PASS."""
    env = os.environ.copy()
    env.pop("SENTRY_DSN", None)
    env["SKIP_DB_SETUP"] = "1"
    code = """
from unittest.mock import patch
with patch('sentry_sdk.init') as init:
    import app.main
    assert init.call_count == 0, init.call_args_list
"""

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, (
        "app.main imported with SENTRY_DSN unset but sentry_sdk.init was called "
        f"or import failed.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_explicit_dsn_initializes_once():
    """Positive control: the guard must not accidentally disable configured reporting."""
    env = os.environ.copy()
    env["SENTRY_DSN"] = "https://public@example.invalid/1"
    env["SKIP_DB_SETUP"] = "1"
    code = """
from unittest.mock import patch
with patch('sentry_sdk.init') as init:
    import app.main
    assert init.call_count == 1, init.call_args_list
    kwargs = init.call_args.kwargs
    assert kwargs['dsn'] == 'https://public@example.invalid/1'
    assert kwargs['send_default_pii'] is False
    assert kwargs['traces_sample_rate'] == 0.1
"""

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, (
        "Configured SENTRY_DSN did not initialize exactly once."
        f"\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
