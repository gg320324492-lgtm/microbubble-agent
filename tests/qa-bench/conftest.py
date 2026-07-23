"""W68 D6 Phase 1 tests/qa-bench/ local conftest.

Strategy: prepend the qa-bench directory to sys.path so that the
``run_d5_dry.py`` / ``inprocess_runner.py`` modules can import each
other without polluting the import graph.  We deliberately do NOT
override the root ``SKIP_DB_SETUP`` here -- the smoke tests do that
themselves at module load time so the root conftest sees the flag.
"""

from __future__ import annotations

import sys
from pathlib import Path

_QA_BENCH_DIR = Path(__file__).resolve().parent
if str(_QA_BENCH_DIR) not in sys.path:
    sys.path.insert(0, str(_QA_BENCH_DIR))