"""tests/realenv/conftest.py — W98 P3-A 真环境 e2e fixtures.

派工 v10 §2.2: 真环境不可达时, 必含 pytest.skip 守护.
- DATABASE_URL 未设置 → 全部真环境 e2e 自动 SKIP
- REDIS_URL 未设置 → 全部真环境 e2e 自动 SKIP

启用真环境:
    export DATABASE_URL=postgresql://postgres:password@localhost:5432/microbubble
    export REDIS_URL=redis://localhost:6379/0
    python -m pytest tests/realenv -v

设计:
- fixtures 全部 lazy: 真连接失败时跳过, 不污染其它测试
- 每个真环境测试用 `realenv_marker` 标记, --collect-only 可清晰看到 SKIP
- 真表结构由 alembic 093 维护 (本任务不动 alembic, 沿用 W98 base 093)

5 件套守恒:
- alembic 1 head = 093 (沿用, 不动)
- 真环境 e2e SKIP guard (本任务核心)
- 0 production code (不动 app/ web/src/ alembic/)
- 不动 frontend (PWA build 沿用基线)
- 锚点范式 (W98 +11, 1 commit)
"""
import os
from typing import Optional

import pytest

# ----------------------------------------------------------------------------
# 守护: 真环境可达性
# ----------------------------------------------------------------------------

DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")
REDIS_URL: Optional[str] = os.getenv("REDIS_URL")

REALENV_DB_AVAILABLE = bool(DATABASE_URL)
REALENV_REDIS_AVAILABLE = bool(REDIS_URL)

# 跳过原因常量 (复用, 避免 typo)
SKIP_NO_DB = "DATABASE_URL 未设置, 真环境 e2e 已 SKIP. 启用: export DATABASE_URL=postgresql://..."
SKIP_NO_REDIS = "REDIS_URL 未设置, 真环境 e2e 已 SKIP. 启用: export REDIS_URL=redis://..."

# 综合判断: SKIP_DB_SETUP=1 或缺 DATABASE_URL+REDIS_URL → 全部 SKIP
REALENV_SHOULD_SKIP = (
    bool(os.getenv("SKIP_DB_SETUP"))
    or not REALENV_DB_AVAILABLE
    or not REALENV_REDIS_AVAILABLE
)
SKIP_REALENV_REASON = (
    "SKIP_DB_SETUP=1 (mock 测试模式)"
    if os.getenv("SKIP_DB_SETUP")
    else f"真环境不可达 (DATABASE_URL={'OK' if REALENV_DB_AVAILABLE else 'UNSET'}, REDIS_URL={'OK' if REALENV_REDIS_AVAILABLE else 'UNSET'})"
)


# ----------------------------------------------------------------------------
# 标记: 全部真环境 e2e 用 realenv_marker 标记
# ----------------------------------------------------------------------------

realenv_marker = pytest.mark.realenv
realenv_skip_all = pytest.mark.skipif(REALENV_SHOULD_SKIP, reason=SKIP_REALENV_REASON)


def pytest_collection_modifyitems(config, items):
    """为所有 tests/realenv/ 下的测试统一加 skipif.

    注意: 此函数在 conftest 加载时立即生效, 无需每个测试文件手动标记.
    """
    for item in items:
        if "tests/realenv/" in str(item.fspath):
            item.add_marker(realenv_skip_all)
            item.add_marker(realenv_marker)


# ----------------------------------------------------------------------------
# 真环境 fixtures (按需启用, 默认 SKIP)
# ----------------------------------------------------------------------------

@pytest.fixture(scope="session")
def realenv_database_url() -> str:
    """DATABASE_URL fixture. 不可达时 SKIP."""
    if not REALENV_DB_AVAILABLE:
        pytest.skip(SKIP_NO_DB)
    return DATABASE_URL  # type: ignore[return-value]


@pytest.fixture(scope="session")
def realenv_redis_url() -> str:
    """REDIS_URL fixture. 不可达时 SKIP."""
    if not REALENV_REDIS_AVAILABLE:
        pytest.skip(SKIP_NO_REDIS)
    return REDIS_URL  # type: ignore[return-value]


@pytest.fixture
def realenv_session_id() -> str:
    """测试用唯一 session_id (per-test, 避免污染)."""
    import uuid
    return f"w98-p3a-realenv-{uuid.uuid4().hex[:12]}"


@pytest.fixture
def realenv_user_id() -> int:
    """固定 user_id (与现有 mock 测试对齐 = 1)."""
    return 1