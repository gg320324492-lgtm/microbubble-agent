# R2 Progress

## Status: STARTING

- HEAD: e4dc88de7 (R1 complete)
- Python: 3.12.10
- pytest: 9.1.1
- pytest-asyncio: 1.4.0 (asyncio_mode=auto)

=================================== ERRORS ====================================
____ ERROR collecting tests/desktop_migration/test_export_web_snapshot.py _____
ImportError while importing test module 'E:\microbubble-agent\.claude\worktrees\desktop-conversion-plan-12aa22\tests\desktop_migration\test_export_web_snapshot.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
C:\Users\pc\AppData\Local\Programs\Python\Python312\Lib\importlib\__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests\desktop_migration\test_export_web_snapshot.py:21: in <module>
    from scripts.desktop_migration.export_web_snapshot import (
E   ModuleNotFoundError: No module named 'scripts.desktop_migration.export_web_snapshot'
============================== warnings summary ===============================
app\config.py:320
  E:\microbubble-agent\.claude\worktrees\desktop-conversion-plan-12aa22\app\config.py:320: PydanticDeprecatedSince20: Pydantic V1 style `@validator` validators are deprecated. You should migrate to Pydantic V2 style `@field_validator` validators, see the migration guide for more details. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.13/migration/
    @validator("SECRET_KEY")

app\config.py:6
  E:\microbubble-agent\.claude\worktrees\desktop-conversion-plan-12aa22\app\config.py:6: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.13/migration/
    class Settings(BaseSettings):

C:\Users\pc\AppData\Local\Programs\Python\Python312\Lib\site-packages\sentry_sdk\integrations\starlette.py:60
  C:\Users\pc\AppData\Local\Programs\Python\Python312\Lib\site-packages\sentry_sdk\integrations\starlette.py:60: PendingDeprecationWarning: Please use `import python_multipart` instead.
    import multipart  # type: ignore

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
ERROR tests/desktop_migration/test_export_web_snapshot.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
3 warnings, 1 error in 0.16s

## Step 2 RED

=================================== ERRORS ====================================
____ ERROR collecting tests/desktop_migration/test_export_web_snapshot.py _____
ImportError while importing test module 'E:\microbubble-agent\.claude\worktrees\desktop-conversion-plan-12aa22\tests\desktop_migration\test_export_web_snapshot.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
C:\Users\pc\AppData\Local\Programs\Python\Python312\Lib\importlib\__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests\desktop_migration\test_export_web_snapshot.py:21: in <module>
    from scripts.desktop_migration.export_web_snapshot import (
E   ModuleNotFoundError: No module named 'scripts.desktop_migration.export_web_snapshot'
============================== warnings summary ===============================
app\config.py:320
  E:\microbubble-agent\.claude\worktrees\desktop-conversion-plan-12aa22\app\config.py:320: PydanticDeprecatedSince20: Pydantic V1 style `@validator` validators are deprecated. You should migrate to Pydantic V2 style `@field_validator` validators, see the migration guide for more details. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.13/migration/
    @validator("SECRET_KEY")

app\config.py:6
  E:\microbubble-agent\.claude\worktrees\desktop-conversion-plan-12aa22\app\config.py:6: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.13/migration/
    class Settings(BaseSettings):

C:\Users\pc\AppData\Local\Programs\Python\Python312\Lib\site-packages\sentry_sdk\integrations\starlette.py:60
  C:\Users\pc\AppData\Local\Programs\Python\Python312\Lib\site-packages\sentry_sdk\integrations\starlette.py:60: PendingDeprecationWarning: Please use `import python_multipart` instead.
    import multipart  # type: ignore

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
ERROR tests/desktop_migration/test_export_web_snapshot.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
3 warnings, 1 error in 0.16s

## Step 2 RED

============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0
rootdir: E:\microbubble-agent\.claude\worktrees\desktop-conversion-plan-12aa22
configfile: pytest.ini
plugins: anyio-4.14.1, asyncio-1.4.0, respx-0.23.1
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=function, asyncio_default_test_loop_scope=function
collected 0 items / 1 error

=================================== ERRORS ====================================
____ ERROR collecting tests/desktop_migration/test_export_web_snapshot.py _____
ImportError while importing test module 'E:\microbubble-agent\.claude\worktrees\desktop-conversion-plan-12aa22\tests\desktop_migration\test_export_web_snapshot.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
C:\Users\pc\AppData\Local\Programs\Python\Python312\Lib\importlib\__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests\desktop_migration\test_export_web_snapshot.py:21: in <module>
    from scripts.desktop_migration.export_web_snapshot import (
E   ModuleNotFoundError: No module named 'scripts.desktop_migration.export_web_snapshot'
============================== warnings summary ===============================
app\config.py:320
  E:\microbubble-agent\.claude\worktrees\desktop-conversion-plan-12aa22\app\config.py:320: PydanticDeprecatedSince20: Pydantic V1 style `@validator` validators are deprecated. You should migrate to Pydantic V2 style `@field_validator` validators, see the migration guide for more details. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.13/migration/
    @validator("SECRET_KEY")

app\config.py:6
  E:\microbubble-agent\.claude\worktrees\desktop-conversion-plan-12aa22\app\config.py:6: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.13/migration/
    class Settings(BaseSettings):

C:\Users\pc\AppData\Local\Programs\Python\Python312\Lib\site-packages\sentry_sdk\integrations\starlette.py:60
  C:\Users\pc\AppData\Local\Programs\Python\Python312\Lib\site-packages\sentry_sdk\integrations\starlette.py:60: PendingDeprecationWarning: Please use `import python_multipart` instead.

## Step 4.1 GREEN

============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\pc\AppData\Local\Programs\Python\Python312\python.exe
rootdir: E:\microbubble-agent\.claude\worktrees\desktop-conversion-plan-12aa22
configfile: pytest.ini
plugins: anyio-4.14.1, asyncio-1.4.0, respx-0.23.1
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=function, asyncio_default_test_loop_scope=function
collecting ... collected 7 items

tests/desktop_migration/test_export_web_snapshot.py::test_export_session_starts_with_read_only_tx PASSED [ 14%]
tests/desktop_migration/test_export_web_snapshot.py::test_export_session_rejects_unsafe_queries PASSED [ 28%]
tests/desktop_migration/test_export_web_snapshot.py::test_export_session_allows_safe_queries PASSED [ 42%]
tests/desktop_migration/test_export_web_snapshot.py::test_export_session_rolls_back_on_close PASSED [ 57%]
tests/desktop_migration/test_export_web_snapshot.py::test_export_snapshot_writes_ndjson_and_manifest PASSED [ 71%]
tests/desktop_migration/test_export_web_snapshot.py::test_export_snapshot_strips_forbidden_fields PASSED [ 85%]
tests/desktop_migration/test_export_web_snapshot.py::test_assert_sql_safe_blocks_dml_and_ddl PASSED [100%]

============================== 7 passed in 0.05s ==============================

## Step 4.2 CLI --help

Traceback (most recent call last):
  File "E:\microbubble-agent\.claude\worktrees\desktop-conversion-plan-12aa22\scripts\desktop_migration\export_web_snapshot.py", line 29, in <module>
    from .snapshot_schema import (
ImportError: attempted relative import with no known parent package

## Step 4.1 GREEN (re-run after import fix)
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\pc\AppData\Local\Programs\Python\Python312\python.exe
rootdir: E:\microbubble-agent\.claude\worktrees\desktop-conversion-plan-12aa22
configfile: pytest.ini
plugins: anyio-4.14.1, asyncio-1.4.0, respx-0.23.1
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=function, asyncio_default_test_loop_scope=function
collecting ... collected 7 items

tests/desktop_migration/test_export_web_snapshot.py::test_export_session_starts_with_read_only_tx PASSED [ 14%]
tests/desktop_migration/test_export_web_snapshot.py::test_export_session_rejects_unsafe_queries PASSED [ 28%]
tests/desktop_migration/test_export_web_snapshot.py::test_export_session_allows_safe_queries PASSED [ 42%]
tests/desktop_migration/test_export_web_snapshot.py::test_export_session_rolls_back_on_close PASSED [ 57%]
tests/desktop_migration/test_export_web_snapshot.py::test_export_snapshot_writes_ndjson_and_manifest PASSED [ 71%]
tests/desktop_migration/test_export_web_snapshot.py::test_export_snapshot_strips_forbidden_fields PASSED [ 85%]
tests/desktop_migration/test_export_web_snapshot.py::test_assert_sql_safe_blocks_dml_and_ddl PASSED [100%]

============================== 7 passed in 0.06s ==============================

## Step 4.2 CLI --help
usage: export_web_snapshot [-h] --database-url DATABASE_URL --minio-endpoint
                           MINIO_ENDPOINT --minio-access-key MINIO_ACCESS_KEY
                           --minio-secret-key MINIO_SECRET_KEY --output-dir
                           OUTPUT_DIR --snapshot-id SNAPSHOT_ID

Export the web database to a read-only NDJSON snapshot.

options:
  -h, --help            show this help message and exit
  --database-url DATABASE_URL
                        PostgreSQL DSN. MUST be a read-only role. Do NOT pass
                        the application DSN.
  --minio-endpoint MINIO_ENDPOINT
                        MinIO endpoint URL. MUST use a read-only access key.
  --minio-access-key MINIO_ACCESS_KEY
  --minio-secret-key MINIO_SECRET_KEY
  --output-dir OUTPUT_DIR
                        Local directory to write NDJSON + manifest.
  --snapshot-id SNAPSHOT_ID

## Step 4.2b CLI --help via -m
usage: export_web_snapshot [-h] --database-url DATABASE_URL --minio-endpoint
                           MINIO_ENDPOINT --minio-access-key MINIO_ACCESS_KEY
                           --minio-secret-key MINIO_SECRET_KEY --output-dir
                           OUTPUT_DIR --snapshot-id SNAPSHOT_ID

Export the web database to a read-only NDJSON snapshot.

options:
  -h, --help            show this help message and exit
  --database-url DATABASE_URL
                        PostgreSQL DSN. MUST be a read-only role. Do NOT pass
                        the application DSN.
  --minio-endpoint MINIO_ENDPOINT
                        MinIO endpoint URL. MUST use a read-only access key.
  --minio-access-key MINIO_ACCESS_KEY
  --minio-secret-key MINIO_SECRET_KEY
  --output-dir OUTPUT_DIR
                        Local directory to write NDJSON + manifest.
  --snapshot-id SNAPSHOT_ID

## Step 4.3 release:guard
release:guard failure is from PRE-EXISTING web/dist deletions (colleague unstaged work), NOT R2.
R2 only adds: scripts/desktop_migration/, tests/desktop_migration/, docs/desktop-migration/ (all untracked).
Protected paths in failure list: only web/dist/* (none from R2).
Per plan: report to parent; do NOT modify baseline.

### First 3 + last 5 lines of release-guard-r2.txt:

> microbubble-desktop@0.1.0 release:guard
> node scripts/release/verify-web-unchanged.mjs
...
  - web/dist/assets/useTask-D2L9nHmg.js  (protected: web)
  - web/dist/assets/useUiStore-CBrd80Z3.js  (protected: web)
  - web/dist/assets/validator-BmVnUJ7_.js  (protected: web)
  - web/dist/assets/vnode-srkl-ydU.js  (protected: web)
  - web/dist/index.html  (protected: web)
(total 202 lines, all web/dist/* — pre-existing failures)

## Step 4.4 git

### git log --oneline -3
de750cb93 feat(migration): add read-only web snapshot exporter
e4dc88de7 feat(desktop): add verified mbrp package format
1ae6ad928 release(desktop): establish R0 isolation and reproducible builds

### git show --stat HEAD
commit de750cb93b9da6784f80c04c90278658318c6da3
Author: Agent 6 <claude-fable-5@anthropic.com>
Date:   Wed Aug 26 02:27:02 2026 +0800

    feat(migration): add read-only web snapshot exporter

 docs/desktop-migration/operator-readonly-export.md |  68 ++++++
 scripts/desktop_migration/__init__.py              |   0
 scripts/desktop_migration/export_web_snapshot.py   | 257 ++++++++++++++++++++
 scripts/desktop_migration/requirements.txt         |   8 +
 scripts/desktop_migration/snapshot_schema.py       |  62 +++++
 tests/desktop_migration/__init__.py                |   0
 .../desktop_migration/test_export_web_snapshot.py  | 270 +++++++++++++++++++++
 7 files changed, 665 insertions(+)

### git status --short (R2-relevant only)

## Final Summary

- Commit: de750cb93 feat(migration): add read-only web snapshot exporter
- 7 files changed, 665 insertions(+)
- All 7 tests pass (SKIP_DB_SETUP=1 required due to conftest DB init)
- CLI works both as python -m and direct script invocation
- release:guard fails ONLY on pre-existing web/dist deletions (colleague work, not R2)
- R2 paths: scripts/desktop_migration/, tests/desktop_migration/, docs/desktop-migration/
  none overlap with protected paths (app/, web/, alembic/, docker-compose*, nginx/, .env, desktop/, docs/superpowers/plans/)

## Status: COMPLETE
