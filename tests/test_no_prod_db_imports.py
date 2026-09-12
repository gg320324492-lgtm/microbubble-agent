"""守卫: tests/ 禁止直连生产库 (2026-09-12 生产库测试迁移沉淀)

`from app.core.database import async_session / engine` 和
`settings.DATABASE_URL.replace(...)` 都绑定生产 microbubble 库,
测试跑一次污染一次 (历史 debris 实证: 生产库 knowledge id=540
"comment test file", drive tests 留下的测试 folder/comment)。

正确姿势:
- session: `from tests.conftest import test_async_session as async_session`
- engine:  `from tests.conftest import get_test_engine`
- 自建 engine: `from tests.conftest import get_test_database_url`
  (默认 db:5432/microbubble_test 隔离库, TEST_DATABASE_URL 可覆盖)

允许名单 (不改, 有正当理由):
- test_database_lazy_init.py: 测 app.core.database 惰性初始化本身
  (docstring 引用该 import 语句, monkeypatch mock, 不连真库)
- tests/e2e/test_anchor_scripts_smoke.py: 把 settings.DATABASE_URL
  monkeypatch 成 sqlite, 专测脚本逻辑
- tests/integration/test_hnsw_bench_real.py: INTEGRATION=1 PoC 基准,
  连 localhost:5432 且默认 skip (真跑时由 scripts/bench_hnsw_params.py 自建 engine)
"""
import re
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent

# 相对 tests/ 的路径; 目录用 (parts) 元组, 文件用名字
ALLOWLIST = {
    ("test_database_lazy_init.py",),
    ("e2e", "test_anchor_scripts_smoke.py"),
    ("integration", "test_hnsw_bench_real.py"),
    ("test_no_prod_db_imports.py",),  # 本文件 docstring 自引用
}

# 非注释行里的生产库触点:
# 1. import 生产 session 工厂 / 生产 engine
# 2. settings.DATABASE_URL (自建 engine 回退生产 URL 的唯一途径)
IMPORT_RE = re.compile(
    r"^\s*from\s+app\.core\.database\s+import\s+[^\n]*\b(async_session|engine)\b",
    re.M,
)
PROD_URL_RE = re.compile(r"settings\.DATABASE_URL")


def _strip_comment_lines(src: str) -> str:
    """剥掉每行 '#' 及其后内容 (含行尾注释), 防注释/docstring 里的历史提法误报。

    靶子 (import 语句 / url 赋值) 不会包含 '#' 字符串, 全行截断安全。
    docstring 里的历史提法由各文件改写 (已随 2026-09-12 迁移处理)。
    """
    return "\n".join(line.split("#", 1)[0] for line in src.splitlines())


def test_no_test_hits_production_db():
    offenders = []
    for p in sorted(TESTS_DIR.rglob("*.py")):
        rel = p.relative_to(TESTS_DIR)
        rel_key = tuple(rel.parts)
        if rel_key in ALLOWLIST or (rel.name,) in ALLOWLIST:
            continue
        src = _strip_comment_lines(p.read_text(encoding="utf-8", errors="replace"))
        hits = []
        if IMPORT_RE.search(src):
            hits.append("imports app.core.database async_session/engine")
        if PROD_URL_RE.search(src):
            hits.append("uses settings.DATABASE_URL")
        if hits:
            offenders.append(f"  - {rel.as_posix()} ({'; '.join(hits)})")
    assert not offenders, (
        "\n以下测试文件直连生产库, 请改用 tests.conftest 的测试库工厂:\n"
        + "\n".join(offenders)
        + "\n迁移方式见 tests/conftest.py 头部注释 (2026-09-12 生产库测试迁移)"
    )
