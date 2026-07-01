"""purge_test_user_data.py — 纯函数单测 (无 DB / 无 async fixture 依赖, 任意环境可跑)

跑法:
    docker exec microbubble-agent-app-1 bash -c "cd /app && python -m pytest tests/test_purge_test_user_data.py -v"

覆盖 (14+ case):
- filter_testbot_ids 防御性 user_id 过滤
- filter_testbot_knowledge_paths 防御性 created_by 过滤 + dedup + 空值跳过
- serialize_row datetime 序列化 + ARRAY 序列化 + exclude 字段
- build_minio_orphan_log 失败日志结构
- purge_test_user_data 常量稳定性 (TEST_USER_ID / TEST_USER_NAME)
"""

import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

# 让脚本可独立导入 (本地或容器)
# 本地: scripts/ 与 tests/ 同级 → parent.parent / "scripts"
# 容器: scripts/ 通常拷到 /tmp/ → /tmp
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
if Path("/tmp/purge_test_user_data.py").exists():
    sys.path.insert(0, "/tmp")

from purge_test_user_data import (  # noqa: E402
    BACKUP_PREFIX,
    TEST_USER_ID,
    TEST_USER_NAME,
    build_minio_orphan_log,
    filter_testbot_ids,
    filter_testbot_knowledge_paths,
    serialize_row,
)


# ── 常量稳定性 ──────────────────────────────────────────────────────
def test_constants_stable():
    """测试账号常量锁住 (脚本 + ensure_test_user.py + conftest.py 三方一致)."""
    assert TEST_USER_ID == 59
    assert TEST_USER_NAME == "xiaoqi_testbot"
    assert BACKUP_PREFIX == "purge_test_user_backup"


# ── filter_testbot_ids: 防御性 user_id 过滤 ─────────────────────────
def test_filter_testbot_ids_basic():
    """仅保留 user_id == 59 的行 (user_id_field=user_id)."""
    rows = [
        SimpleNamespace(user_id=59, name="testbot"),
        SimpleNamespace(user_id=2, name="user2"),
        SimpleNamespace(user_id=59, name="testbot2"),
    ]
    out = filter_testbot_ids(rows, "user_id")
    assert len(out) == 2
    assert all(r.user_id == 59 for r in out)


def test_filter_testbot_ids_created_by_field():
    """created_by 字段名可配 (防 Pydantic 字段漂移)."""
    rows = [
        SimpleNamespace(created_by=59, name="t1"),
        SimpleNamespace(created_by=59, name="t2"),
        SimpleNamespace(created_by=2, name="real"),
    ]
    out = filter_testbot_ids(rows, "created_by")
    assert len(out) == 2


def test_filter_testbot_ids_empty():
    """空输入透传."""
    assert filter_testbot_ids([], "user_id") == []
    assert filter_testbot_ids([], "created_by") == []


def test_filter_testbot_ids_no_match():
    """全不是测试账号 → 空 list."""
    rows = [
        SimpleNamespace(user_id=2),
        SimpleNamespace(user_id=3),
    ]
    assert filter_testbot_ids(rows, "user_id") == []


def test_filter_testbot_ids_missing_field():
    """缺字段的行 (None) → 跳过 (防御性)."""
    rows = [
        SimpleNamespace(),  # 无 user_id
        SimpleNamespace(user_id=59),
    ]
    out = filter_testbot_ids(rows, "user_id")
    assert len(out) == 1


# ── filter_testbot_knowledge_paths: 防御性 + dedup + 空值 ─────────────
def test_knowledge_paths_basic():
    """created_by=59 + file_path 非空 → 提取."""
    rows = [
        SimpleNamespace(created_by=59, file_path="uploads/a.bin"),
        SimpleNamespace(created_by=2, file_path="uploads/real.bin"),  # 真实用户跳过
        SimpleNamespace(created_by=59, file_path="uploads/b.bin"),
    ]
    out = filter_testbot_knowledge_paths(rows)
    assert out == ["uploads/a.bin", "uploads/b.bin"]


def test_knowledge_paths_dedup():
    """同 path 多条 → 仅一次 (MinIO remove_object 幂等)."""
    rows = [
        SimpleNamespace(created_by=59, file_path="uploads/x.bin"),
        SimpleNamespace(created_by=59, file_path="uploads/x.bin"),
        SimpleNamespace(created_by=59, file_path="uploads/x.bin"),
    ]
    out = filter_testbot_knowledge_paths(rows)
    assert out == ["uploads/x.bin"]


def test_knowledge_paths_skip_empty():
    """file_path None / 空字符串 → 跳过."""
    rows = [
        SimpleNamespace(created_by=59, file_path=None),
        SimpleNamespace(created_by=59, file_path=""),
        SimpleNamespace(created_by=59, file_path="uploads/a.bin"),
    ]
    out = filter_testbot_knowledge_paths(rows)
    assert out == ["uploads/a.bin"]


def test_knowledge_paths_skip_non_testbot():
    """created_by != 59 一律跳过 (即便 file_path 非空)."""
    rows = [
        SimpleNamespace(created_by=2, file_path="uploads/real.bin"),
        SimpleNamespace(created_by=None, file_path="uploads/orphan.bin"),
        SimpleNamespace(created_by=59, file_path="uploads/test.bin"),
    ]
    out = filter_testbot_knowledge_paths(rows)
    assert out == ["uploads/test.bin"]


# ── serialize_row: datetime / ARRAY / exclude ─────────────────────────
def test_serialize_row_datetime_isoformat():
    """datetime 字段 → ISO 字符串 (JSON 兼容)."""
    row = SimpleNamespace(
        id=1,
        title="t",
        created_at=datetime(2026, 7, 1, 14, 0, 0),
        content="c",
    )
    row.__table__ = SimpleNamespace(columns=[
        SimpleNamespace(name="id"),
        SimpleNamespace(name="title"),
        SimpleNamespace(name="created_at"),
        SimpleNamespace(name="content"),
    ])
    out = serialize_row(row)
    assert out["created_at"] == "2026-07-01T14:00:00"
    assert out["id"] == 1
    assert out["title"] == "t"


def test_serialize_row_array_to_list():
    """ARRAY / 可迭代字段 → list (JSON 兼容)."""
    row = SimpleNamespace(id=1, tags=["a", "b", "c"], key_concepts=[])
    row.__table__ = SimpleNamespace(columns=[
        SimpleNamespace(name="id"),
        SimpleNamespace(name="tags"),
        SimpleNamespace(name="key_concepts"),
    ])
    out = serialize_row(row)
    assert out["tags"] == ["a", "b", "c"]
    assert out["key_concepts"] == []


def test_serialize_row_exclude_field():
    """exclude 集合内字段不写入 (防 embedding 大对象爆备份)."""
    row = SimpleNamespace(id=1, title="t", embedding=[0.1] * 1024)
    row.__table__ = SimpleNamespace(columns=[
        SimpleNamespace(name="id"),
        SimpleNamespace(name="title"),
        SimpleNamespace(name="embedding"),
    ])
    out = serialize_row(row, exclude={"embedding"})
    assert "embedding" not in out
    assert out["id"] == 1
    assert out["title"] == "t"


def test_serialize_row_none_safe():
    """None 值透传 (datetime/ARRAY/embedding 都允许 None)."""
    row = SimpleNamespace(id=1, file_path=None, embedding=None)
    row.__table__ = SimpleNamespace(columns=[
        SimpleNamespace(name="id"),
        SimpleNamespace(name="file_path"),
        SimpleNamespace(name="embedding"),
    ])
    out = serialize_row(row)
    assert out["file_path"] is None
    assert out["embedding"] is None


# ── build_minio_orphan_log: 失败日志结构 ─────────────────────────────
def test_minio_orphan_log_structure():
    """失败日志包含 failed_at / reason / items 三字段."""
    failures = [("uploads/a.bin", "NoSuchKey"), ("uploads/b.bin", "AccessDenied")]
    log = build_minio_orphan_log(failures)
    assert "failed_at" in log
    assert "reason" in log
    assert "items" in log
    assert len(log["items"]) == 2
    assert log["items"][0]["path"] == "uploads/a.bin"
    assert log["items"][0]["error"] == "NoSuchKey"


def test_minio_orphan_log_empty():
    """空 failures 列表 → items 为空 (不报错)."""
    log = build_minio_orphan_log([])
    assert log["items"] == []
    assert log["reason"].startswith("MinIO")


# ── 端到端纯函数链 (端到端验证: 不用 DB) ──────────────────────────
def test_pure_chain_testbot_only():
    """完整链路: tasks rows → filter_testbot_ids → filter_testbot_knowledge_paths.

    验证: 真实用户 rows + 测试用户 rows 混合时, 仅测试用户进入清理流程.
    """
    task_rows = [
        SimpleNamespace(id=275, created_by=59, title="实验对照1"),
        SimpleNamespace(id=201, created_by=2, title="画专利装置图"),  # 真实用户 → 跳过
        SimpleNamespace(id=280, created_by=59, title="整理纪要"),
    ]
    testbot_tasks = filter_testbot_ids(task_rows, "created_by")
    assert len(testbot_tasks) == 2  # 275, 280
    assert {t.id for t in testbot_tasks} == {275, 280}

    # reminders 关联 (假设 task_id 都来自 testbot_tasks)
    task_ids = [t.id for t in testbot_tasks]
    assert task_ids == [275, 280]

    # knowledge 同样过滤
    kb_rows = [
        SimpleNamespace(created_by=59, file_path="uploads/test.bin"),
        SimpleNamespace(created_by=2, file_path="uploads/real.bin"),
        SimpleNamespace(created_by=59, file_path=None),  # 跳过 None
    ]
    paths = filter_testbot_knowledge_paths(kb_rows)
    assert paths == ["uploads/test.bin"]