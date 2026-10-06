#!/usr/bin/env bash
# qa-bench D7 baseline gate.
#
# This command is intentionally runnable both locally and in GitHub Actions:
#
#   bash scripts/ci_qa_bench_baseline.sh
#
# The nine-file suite is the historical 78-test contract: 71 pass and 7 skip.
# Redis is required by two transcript-buffer tests; set REDIS_URL when running
# outside the CI service container (for example, redis://localhost:6379/0).
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
mkdir -p logs
LOG_FILE="logs/ci-baseline-$(date +%Y%m%d).log"
: > "$LOG_FILE"

# Keep all command output in the dated log while preserving it in CI output.
exec > >(tee -a "$LOG_FILE") 2>&1

BASELINE_FILES=(
  tests/test_meeting_transcript_buffer.py
  tests/test_orphan_meeting_cleanup_audio_chunks.py
  tests/test_meeting_recording_user_agent.py
  tests/test_meeting_recording_audio_chunk_auth.py
  tests/test_meeting_recording_cancel.py
  tests/test_chat_history_tasks.py
  tests/test_chat_share_cleanup.py
  tests/test_kb_dedup_admin_cli.py
  tests/scripts/test_kb_dedup_admin_cli_e2e.py
)
EXPECTED_PASS=71
EXPECTED_SKIP=7
FAILED=0

run_check() {
  local name="$1"
  shift
  printf '\n=== %s ===\n' "$name"
  if "$@"; then
    echo "PASS: $name"
  else
    echo "FAIL: $name"
    FAILED=1
  fi
}

# tests/test_baseline_audit.py is ARCHIVED (tests/ARCHIVED.md; module-level
# pytest.skip added by the 2026-09-30 S1.2 R4 sweep). Its own audit assertions
# therefore no longer execute, so both invocations below expect the archived
# shape instead of running the assertions:
#   - bare `python <file>` raises Skipped at import -> exit 1
#   - `python -m pytest <file>` collects nothing -> exit 5 (NO_TESTS_COLLECTED)
#
# The nine-file contract below is NOT affected: all nine files it guards are
# live (none carries a module-level skip), so the 71 PASS + 7 SKIP conservation
# gate still has real assertions behind it.
#
# Both archived invocations stay fail-loud for genuine breakage:
#   - bare run: exit 0 accepted; exit 1 accepted ONLY if stderr shows the
#     pytest "Skipped:" sentinel (a real syntax/import error exits 1 too, but
#     without that sentinel, so it still breaks the gate).
#   - pytest run: exit 5 accepted ONLY when the summary reports a skip. A file
#     that was wrongly deleted or renamed also yields exit 5, but reports
#     "no tests ran" instead, so it is not mistaken for an archived skip.
ARCHIVED_AUDIT="tests/test_baseline_audit.py"

run_check "baseline audit module archived" bash -c '
  out=$(env SKIP_DB_SETUP=1 python "'"$ARCHIVED_AUDIT"'" 2>&1); rc=$?
  printf "%s\n" "$out"
  if [ "$rc" -eq 0 ]; then exit 0; fi
  if [ "$rc" -eq 1 ] && printf "%s" "$out" | grep -q "^Skipped:"; then
    echo "OK: archived via module-level pytest.skip (expected)"
    exit 0
  fi
  echo "FAIL: unexpected bare-run exit $rc (not the archived-skip sentinel)"
  exit 1
'

run_check "baseline audit assertions archived" bash -c '
  out=$(env SKIP_DB_SETUP=1 python -m pytest "'"$ARCHIVED_AUDIT"'" \
    -q --disable-warnings 2>&1); rc=$?
  printf "%s\n" "$out"
  if [ "$rc" -eq 5 ] && printf "%s" "$out" | grep -Eq "[0-9]+ skipped"; then
    echo "OK: module-level skip, nothing collected (expected)"
    exit 0
  fi
  echo "FAIL: unexpected pytest exit $rc (expected 5 + a skipped summary)"
  exit 1
'

printf '\n=== nine-file baseline (%s PASS + %s SKIP) ===\n' "$EXPECTED_PASS" "$EXPECTED_SKIP"
set +e
BASELINE_OUTPUT=$(env SKIP_DB_SETUP=1 python -m pytest "${BASELINE_FILES[@]}" \
  -q --disable-warnings 2>&1)
BASELINE_STATUS=$?
set -e
printf '%s\n' "$BASELINE_OUTPUT"

if [ "$BASELINE_STATUS" -ne 0 ]; then
  echo "FAIL: baseline pytest exited with status $BASELINE_STATUS"
  FAILED=1
fi

if ! grep -Eq "(^|[^0-9])${EXPECTED_PASS} passed([^0-9]|$)" <<<"$BASELINE_OUTPUT"; then
  echo "FAIL: expected exactly ${EXPECTED_PASS} passed tests"
  FAILED=1
fi
if ! grep -Eq "(^|[^0-9])${EXPECTED_SKIP} skipped([^0-9]|$)" <<<"$BASELINE_OUTPUT"; then
  echo "FAIL: expected exactly ${EXPECTED_SKIP} skipped tests"
  FAILED=1
fi
if grep -Eq '[0-9]+ failed|[0-9]+ error' <<<"$BASELINE_OUTPUT"; then
  echo "FAIL: baseline output contains failed/error tests"
  FAILED=1
fi

printf '\n=== app import ===\n'
set +e
APP_OUTPUT=$(env SKIP_DB_SETUP=1 python -c "import app; print('app import OK')" 2>&1)
APP_STATUS=$?
set -e
printf '%s\n' "$APP_OUTPUT"
if [ "$APP_STATUS" -ne 0 ] || ! grep -Fxq "app import OK" <<<"$APP_OUTPUT"; then
  echo "FAIL: app import check"
  FAILED=1
else
  echo "PASS: app import check"
fi

if [ "$FAILED" -ne 0 ]; then
  echo "D7 baseline gate FAILED; see $LOG_FILE"
  exit 1
fi

echo "D7 baseline gate PASSED: ${EXPECTED_PASS} passed + ${EXPECTED_SKIP} skipped"
echo "Log: $LOG_FILE"
