"""tests/rag 局部 conftest — docs-only e2e 无需数据库

覆盖父级 tests/conftest.py 的 autouse `setup_db` fixture (function-scope, 每个
test drop_all/create_all 需要真 PostgreSQL)。PR10 docs e2e 是纯文件/git 断言,
本机无 DB 时也必须能跑 (据实上报铁律: 真跑, 不纸面 PASS)。

后续 PR1-PR9 若在 tests/rag/ 下新增需 DB 的测试, 应显式使用 `db` fixture
(其内部自带 SKIP_DB_SETUP 守护), 不受本覆盖影响。
"""
import pytest


@pytest.fixture(scope="function", autouse=True)
def setup_db():
    """no-op 覆盖: docs e2e 不建表不连库。"""
    yield
