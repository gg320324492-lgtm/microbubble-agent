"""回归守卫: conftest 的测试库 URL 绝不能指向生产库。

2026-10-15 生产事故的直接防线。`tests/conftest.py` 的 setup_db / db fixture
每次都执行 `DROP SCHEMA public CASCADE` —— 它清空的是**连上去那个库**的 public
schema。事故当夜 microbubble 库被清空, 全站 /members /meetings /auth/me 一律
500, 靠当日 02:00 的备份才救回。

旧实现只有一行 `.replace("/microbubble", "/microbubble_test")` 当防线, 而
`str.replace` 匹配不上时**静默返回原串** ⇒ URL 直接沿用生产库地址。
现改为「显式取库名 + 三道 fail-loud 闸」, 本文件锁住那个行为。

⚠️ 本文件**不得**归档 (CLAUDE.md 铁律: 守门类测试不得归档)。
2026-10-15 补: 原守卫 test_guard_conftest_test_url_differs_from_production 位于
tests/test_fin1_backup_share_block.py, 而那个文件 2026-09-30 因「断言对象老化」
被整档 `pytest.skip(allow_module_level=True)` —— **连带把这条活契约也关掉了**。
本文件是它的替代, 且**不依赖 DB 连接**(纯字符串逻辑), 所以任何环境都能跑。
"""
import os
import re
from pathlib import Path

import pytest

CONFTEST = Path(__file__).resolve().parent / "conftest.py"


def _load_guards(fake_prod_url: str):
    """从 conftest 抽出两个守卫函数, 注入假的 settings (避免 import app 包)"""
    src = CONFTEST.read_text(encoding="utf-8")
    start = src.index("def _assert_safe_test_db")
    end = src.index("TEST_DB_URL = _derive_test_db_url()")
    ns = {"os": os, "_settings": type("S", (), {"DATABASE_URL": fake_prod_url})}
    exec(src[start:end], ns)  # noqa: S102 - 测试内加载自有代码, 非外部输入
    return ns["_derive_test_db_url"]


PROD = "postgresql://u:p@db:5432/microbubble"
PROD_ASYNC = PROD.replace("postgresql://", "postgresql+asyncpg://")
BASE = PROD_ASYNC.rsplit("/", 1)[0]


def test_derives_test_db_from_settings():
    """无 env 时应派生出 microbubble_test"""
    os.environ.pop("TEST_DATABASE_URL", None)
    derive = _load_guards(PROD)
    assert derive() == BASE + "/microbubble_test"


@pytest.mark.parametrize("db_name", [
    "microbubble_test",
    "microbubble_test_ag2",      # 本仓 CI 实际用的库
    "microbubble_restore_verify_9",
])
def test_allows_isolated_test_dbs(db_name):
    """隔离测试库名必须放行(含 CI 用的 *_test_ag2)"""
    derive = _load_guards(PROD)
    os.environ["TEST_DATABASE_URL"] = BASE + "/" + db_name
    try:
        assert derive().endswith("/" + db_name)
    finally:
        os.environ.pop("TEST_DATABASE_URL", None)


@pytest.mark.parametrize("db_name,why", [
    ("microbubble",   "等于生产库"),
    ("MicroBubble",   "大小写不同 —— 旧 .replace 的盲区, 会静默沿用生产 URL"),
    ("postgres",      "库名不是 microbubble"),
    ("appdata",       "完全不含 test"),
    ("",              "空串: 静默回落派生分支会掩盖配置错误"),
])
def test_blocks_unsafe_db_names(db_name, why):
    """指向生产库 / 库名可疑 / 空串 —— 一律必须 fail-loud"""
    derive = _load_guards(PROD)
    os.environ["TEST_DATABASE_URL"] = BASE + "/" + db_name
    try:
        with pytest.raises(RuntimeError):
            derive()
    finally:
        os.environ.pop("TEST_DATABASE_URL", None)


def test_blocks_unknown_settings_db_name():
    """settings.DATABASE_URL 库名不是 microbubble 时不做任何猜测, 直接报错"""
    derive = _load_guards("postgresql://u:p@db:5432/some_other_db")
    os.environ.pop("TEST_DATABASE_URL", None)
    with pytest.raises(RuntimeError, match="非 microbubble"):
        derive()


def test_conftest_still_drops_schema_cascade():
    """锁定「fixture 会 DROP SCHEMA public CASCADE」这个前提。

    若将来有人改成不 DROP 了, 本文件其余断言的意义要重新评估 —— 显式记下来,
    避免有人只删掉 DROP 却以为守卫还有意义。
    """
    src = CONFTEST.read_text(encoding="utf-8")
    assert re.search(r"DROP SCHEMA public CASCADE", src), \
        "conftest 不再 DROP SCHEMA public CASCADE —— 请重新评估本守卫的前提"
