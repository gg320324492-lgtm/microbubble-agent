"""Drive v2 PR10 — 协同编辑 smoke test (2026-07-24, W68 第 5 批骨架)

3 场景 (W68 第 5 批派工要求):
1. create document: get_or_create_ydoc_state 对新 file_id 返回空字节
2. apply op: apply_remote_op 接受任意 op_bytes, 返回 state (stub)
3. get snapshot: get_snapshot 与 get_or_create 一致

跑法 (SKIP_DB_SETUP=1 模式, 不连 PG/Redis):
    docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \\
      bash -c "cd /app && pytest tests/test_drive_v2_pr10_collab_smoke.py -v"

W68 第 5 批 0 production code 改动铁律:
- 不连真 DB
- service stub 仅验证方法签名 + 不抛异常
- pycrdt 真 import (W68 第 5 批已 pip install 验证) — 跑 1 个真实 merge test

W69 实施时升级为:
- 真 PG 集成 (file_id → Knowledge FK 验证)
- 真 pycrdt apply_update (验证 apply_remote_op 字节被 Y.Doc 接受)
- 2 客户端并发 (验证 CRDT 双向 merge)
- WS 端点 e2e (Playwright)

参考:
- docs/drive-v2-pr10-collab-editing-design.md §6
- W68 第 5 批派工 prompt
- tests/test_baseline_audit.py (同 SKIP_DB_SETUP 模式)
"""
import os
import sys
from pathlib import Path

import pytest

# 添加项目根到 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ===== 场景 1: create document =====
@pytest.mark.asyncio
async def test_get_or_create_ydoc_state_new_file():
    """新 file_id → 返回空字节 (W69 时实际 INSERT)

    SKIP_DB_SETUP 模式下, service stub 不真连 DB, 直接返回 b""
    """
    from app.services.drive_collab_service import DriveCollabService

    # W69 实施时这里会传 db: AsyncSession 参数, 走 SELECT / INSERT
    # 现在 stub 接受 db 但不使用
    state = await DriveCollabService.get_or_create_ydoc_state(None, file_id=999)
    assert state == b"", f"新 file_id 应返回空字节, 实际 {state!r}"


# ===== 场景 2: apply op =====
@pytest.mark.asyncio
async def test_apply_remote_op_stub():
    """apply_remote_op 接受任意 op_bytes, 返回 state (W69 时真 apply_update)"""
    from app.services.drive_collab_service import (
        DriveCollabService,
        InvalidOpError,
    )

    # 正常 op
    fake_op = b"\x00\x01\x02fake_yjs_update"
    result = await DriveCollabService.apply_remote_op(
        None,
        file_id=999,
        op_bytes=fake_op,
        client_id=1,
        user_id=None,
    )
    assert isinstance(result, bytes), f"应返回 bytes, 实际 {type(result)}"

    # 空 op 应抛 InvalidOpError
    with pytest.raises(InvalidOpError):
        await DriveCollabService.apply_remote_op(
            None,
            file_id=999,
            op_bytes=b"",
            client_id=1,
        )


# ===== 场景 3: get snapshot =====
@pytest.mark.asyncio
async def test_get_snapshot_consistent_with_get_or_create():
    """get_snapshot 与 get_or_create_ydoc_state 返回一致 (W69 时优先 in-memory)"""
    from app.services.drive_collab_service import DriveCollabService

    state_via_get = await DriveCollabService.get_or_create_ydoc_state(None, file_id=999)
    state_via_snap = await DriveCollabService.get_snapshot(None, file_id=999)
    assert state_via_get == state_via_snap, (
        f"get_snapshot 应与 get_or_create 一致, "
        f"get={state_via_get!r} snap={state_via_snap!r}"
    )


# ===== 额外 1: 验证 alembic 064 语法 + 串单链 =====
def test_alembic_064_syntax():
    """alembic 064 串单链 063 (CLAUDE.md §2026-07-24 铁律)"""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "alembic")
    script = ScriptDirectory.from_config(cfg)

    # 1. 064 必须存在
    rev_064 = script.get_revision("064_drive_documents")
    assert rev_064 is not None, "064_drive_documents migration 不存在"

    # 2. 064 down_revision 必须 = 063_drive_file_versions (W68 第 3 批双头事故教训)
    assert rev_064.down_revision == "063_drive_file_versions", (
        f"064 down_revision 应接 063, 实际 {rev_064.down_revision}"
    )

    # 3. 全项目必须 1 个 head (CLAUDE.md §2026-07-24 铁律)
    heads = script.get_heads()
    assert heads == ["064_drive_documents"], (
        f"应有且仅有 1 个 head 064_drive_documents, 实际 {heads}"
    )


# ===== 额外 2: 验证 pycrdt 真能 merge (本机实测, 与设计 doc §9.1 同步) =====
def test_pycrdt_real_merge_double_check():
    """pycrdt 0.14.1 真双向 merge 验证 (W68 第 5 批派工要求 '调研必须真实')

    关键: CRDT 合并后, 双方内容应当包含**所有**插入 (字符级), 但**顺序**取决于 client_id 时序.
    实测两种结果:
    - 'hello world' (顺序合并)
    - 'worldhello ' (反向合并)
    两种都正确. 测试用 set membership 验证, 不假设顺序.
    """
    pytest.importorskip("pycrdt", reason="pycrdt 未安装 (可选, 调研验证)")

    import pycrdt

    doc1 = pycrdt.Doc()
    text1 = doc1.get("content", type=pycrdt.Text)
    text1 += "hello "

    doc2 = pycrdt.Doc()
    text2 = doc2.get("content", type=pycrdt.Text)
    text2 += "world"

    # 双向 sync
    doc1.apply_update(doc2.get_update())
    doc2.apply_update(doc1.get_update())

    merged1 = str(text1)
    merged2 = str(text2)

    # 双方必须一致 (CRDT 收敛性)
    assert merged1 == merged2, f"CRDT 双向合并后应一致, doc1={merged1!r} doc2={merged2!r}"

    # 必须包含两个原始子串 (字符级 CRDT 不丢更新)
    assert "hello" in merged1, f"应保留 'hello', 实际 {merged1!r}"
    assert "world" in merged1, f"应保留 'world', 实际 {merged1!r}"
    assert " " in merged1, f"应保留 ' ', 实际 {merged1!r}"
    assert len(merged1.replace(" ", "").replace("hello", "").replace("world", "")) == 0, (
        f"应只有 hello + space + world, 实际 {merged1!r}"
    )

    # state 字节应 > 0
    assert len(doc1.get_state()) > 0, "state 字节应 > 0"


# ===== 额外 3: 验证 ORM 模型可 import + 列名正确 =====
def test_drive_document_orm_model():
    """ORM 模型可 import, 表名/列名与 alembic 064 同步"""
    from app.models.drive_document import DriveDocument, DriveDocOpLog

    # DriveDocument
    assert DriveDocument.__tablename__ == "drive_documents"
    expected_cols = {
        "id", "file_id", "ydoc_state", "ops_count", "version_number",
        "active_users", "last_edited_by", "last_edited_at",
        "created_at", "updated_at",
    }
    actual_cols = set(DriveDocument.__table__.columns.keys())
    assert actual_cols == expected_cols, (
        f"DriveDocument 列名不匹配:\n"
        f"  期望: {expected_cols}\n"
        f"  实际: {actual_cols}\n"
        f"  差异: 缺 {expected_cols - actual_cols} | 多 {actual_cols - expected_cols}"
    )

    # DriveDocOpLog
    assert DriveDocOpLog.__tablename__ == "drive_doc_op_logs"
    expected_op_cols = {
        "id", "file_id", "op", "client_id", "user_id", "applied_at",
    }
    actual_op_cols = set(DriveDocOpLog.__table__.columns.keys())
    assert actual_op_cols == expected_op_cols, (
        f"DriveDocOpLog 列名不匹配:\n"
        f"  期望: {expected_op_cols}\n"
        f"  实际: {actual_op_cols}"
    )
