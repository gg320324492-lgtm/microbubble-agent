# qa-bench D7 baseline CI automation

**Date**: 2026-07-24
**Scope**: CI and verification tooling only; no production application code changed.
**Anchor**: W68 route 12 B-3, baseline conservation anchor 150.

## 1. Purpose

The qa-bench D5 workflow measures the large question bank and enforces its 80% quality threshold. That gate does not, by itself, prove that the project's small regression baseline is still intact. D7 adds a separate, deterministic contract for the historical nine-file test set.

The contract is:

- 71 tests must pass.
- 7 tests must remain skipped.
- No test may fail or error.
- The baseline audit definition must pass.
- `import app` must succeed.

The expected total is therefore 78 collected tests. The seven skipped cases are the database-backed KB dedup E2E cases in the baseline file list; they are intentionally retained as skips under `SKIP_DB_SETUP=1`.

## 2. Files delivered

| File | Responsibility |
| --- | --- |
| `.github/workflows/qa-bench-baseline.yml` | Independent PR/manual D7 workflow |
| `scripts/ci_qa_bench_baseline.sh` | Local and CI fail-loud baseline runner |
| `.github/workflows/qa-bench-ci.yml` | D7 audit step added beside the D5 gate |
| `docs/qa-bench-d7-baseline-ci.md` | This operating procedure |
| `memory/w68-route-12-b3-d7-baseline-ci-2026-07-24.md` | Durable W68 memory and rules |

## 3. Workflow triggers

`qa-bench-baseline.yml` runs for pull requests when they are:

- opened;
- reopened; or
- synchronized with new commits.

It also supports `workflow_dispatch` for an operator-run verification. The workflow does not run on every push, because the pull-request events cover the review gate and avoid duplicate work on feature branches.

The job uses Python 3.11 and a Redis 7 service container. Redis is needed because the transcript-buffer tests verify actual LIST behavior (`RPUSH`, `LRANGE`, and `LTRIM`). The job sets `SKIP_DB_SETUP=1`, so it does not initialize PostgreSQL, seed users, or touch an application database.

## 4. Dependency installation

The workflow first installs `tests/qa-bench/requirements.txt`, matching the existing qa-bench runners. It then installs the small baseline runtime set needed by the nine selected test files. This is intentionally narrower than the repository's GPU/ASR-heavy production requirements: D7 is a fast structural regression check, not a model benchmark.

The baseline runtime list includes pytest and pytest-asyncio, FastAPI, SQLAlchemy, asyncpg, Redis, Celery, MinIO, Pydantic settings, authentication helpers, Alembic, pgvector, NumPy, and HTTPX. Pinning the versions to the repository's existing requirements prevents the audit from depending on an accidental global environment.

## 5. Baseline audit sequence

The standalone workflow performs these checks in order:

1. `python tests/test_baseline_audit.py` — preserve the historical direct command and ensure module execution itself is valid.
2. `python -m pytest tests/test_baseline_audit.py -q` — execute the 39 audit assertions.
3. `bash scripts/ci_qa_bench_baseline.sh` — run the nine-file contract and app import check.
4. `python -c "import app; print('app import OK')"` — explicit package import smoke test, shown as a separate CI step.

The shell script repeats the audit assertions and then parses the nine-file pytest summary. It requires exact `71 passed` and `7 skipped` markers. Any non-zero pytest result, `failed` marker, or `error` marker sets the gate's failure flag. The script always writes a dated log under `logs/ci-baseline-YYYYMMDD.log` and exits 1 on any mismatch.

## 6. Relationship to the D5 workflow

The existing `.github/workflows/qa-bench-ci.yml` remains responsible for its test database stack, D5 1000-question run, report artifact, and 80% pass-rate gate. D7 is added after the D5 report upload and before the existing 80% assertion step.

The D7 step runs inside the already-started `app-test` container. This matters because that image has the complete application runtime and the container can resolve the test stack's internal services. It uses `SKIP_DB_SETUP=1` and executes `tests/test_baseline_audit.py` plus its pytest assertions. The D5 and D7 checks therefore remain independent: a question-bank result cannot hide a baseline drift, and baseline success cannot waive the 80% quality threshold.

Both steps use `if: always()` where cleanup/reporting requires it. A missing app-test container still causes the D7 command to fail visibly; teardown runs afterward.

## 7. Failure notification

The standalone workflow grants only the permissions needed to read the repository and comment on pull requests. On failure it runs a best-effort notification step:

- If an organization-specific `gh notification` extension is available, it attempts to create a PR failure notification.
- Otherwise, for a pull-request event, it falls back to `gh pr comment` with the expected-count message.
- If `SLACK_WEBHOOK_URL` is configured as a repository secret, it posts a JSON `{text: ...}` payload with the repository, commit, and workflow run URL.
- Missing Slack configuration is logged and does not conceal the original failing test.

Notification failures are intentionally not allowed to turn a failed test into a false success or to mask the original diagnostic. The test step remains authoritative.

## 8. Local usage

From the repository root:

```bash
bash scripts/ci_qa_bench_baseline.sh
```

For the transcript-buffer tests, Redis must be reachable at `REDIS_URL` (the default is `redis://localhost:6379/0`). A local Docker example is:

```bash
docker run --rm -d --name qa-baseline-redis -p 6379:6379 redis:7-alpine
REDIS_URL=redis://localhost:6379/0 bash scripts/ci_qa_bench_baseline.sh
```

Stop the temporary Redis container after the check if it was started without `--rm`.

## 9. Expected output

A healthy run ends with:

```text
71 passed, 7 skipped
app import OK
D7 baseline gate PASSED: 71 passed + 7 skipped
```

The audit module itself currently reports 39 passed assertions. That number is an audit-of-the-baseline number; it is not a replacement for the nine-file 71/7 execution contract.

## 10. Troubleshooting

### Redis connection refused

Set `REDIS_URL` to a reachable service. In GitHub Actions, the Redis service is exposed on localhost:6379. In the existing D5 test stack, run the baseline inside `app-test` so its service DNS and dependencies are available.

### Counts drift

Do not edit the expected numbers to make CI green. First inspect the pytest output and run:

```bash
SKIP_DB_SETUP=1 python -m pytest tests/test_baseline_audit.py -v
```

Then compare `BASELINE_9_FILES` in `tests/test_baseline_audit.py` and `tests/conftest.py`, the stale-file patterns, and the baseline documentation. A count change requires a deliberate review and a new conservation record.

### Import error

Run the app import command directly and preserve the traceback in the CI artifact. Check that the baseline runtime dependency list still matches the imports used by the nine files. Do not add production-code workarounds to the D7 automation.

### Slack did not receive a message

Check that the repository secret is named exactly `SLACK_WEBHOOK_URL` and that the webhook accepts JSON POST requests. Notification is best effort; the workflow log and uploaded dated log remain the source of truth.

## 11. Deployment and repository operations

D7 is a GitHub Actions change and does not require a database migration, Docker image rebuild, Nginx change, or production restart. The operator must still:

1. Push the branch and open/review the pull request.
2. Confirm the D7 workflow appears in the Actions tab.
3. Configure `SLACK_WEBHOOK_URL` if Slack alerts are required.
4. Verify one successful PR run reports 71 passed and 7 skipped.
5. Intentionally inspect a failing run only through a safe test change or a workflow manual run; never weaken the expected counts.
6. Keep D5's 80% gate and D7's baseline gate as separate required checks in branch protection.

No production code path is changed by this work. The only modified workflow is the D5 CI definition, and its new step is test-only.

## 12. Conservation decision

The 71 PASS + 7 SKIP baseline is a cross-theme invariant, not a casual target. D7 makes that invariant run on every pull request, records evidence in an artifact, and emits a failure notification without changing the application. This closes the gap identified after D6: quality-gate CI now has an automated baseline audit and an explicit import smoke test.
