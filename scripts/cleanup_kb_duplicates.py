"""Compatibility entry point for the KB duplicate cleanup CLI.

Use ``kb_dedup_admin_cli.py`` for new operational work.  This filename is
kept for the historical cleanup command and intentionally exposes the same
three-step scan/validate/apply workflow.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Support both ``python scripts/cleanup_kb_duplicates.py`` and importing this
# compatibility module from tests (where ``scripts/`` is not on sys.path).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from kb_dedup_admin_cli import (  # noqa: F401,E402
    CleanupPlan,
    DuplicateGroup,
    KbRecord,
    ValidationResult,
    apply_cleanup,
    content_hash,
    group_duplicate_records,
    main,
    scan_duplicates,
    validate_cleanup_plan,
)


if __name__ == "__main__":
    import asyncio

    sys.exit(asyncio.run(main()))
