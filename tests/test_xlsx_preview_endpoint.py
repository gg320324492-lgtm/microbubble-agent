"""XLSX 预览 — 端点状态机测试 (临时拆分文件, 任务 2 实现端点后合回 test_xlsx_preview.py)

覆盖: 端点 .xls 400 / 非 xlsx 400 / 缓存命中 / 误差文件。
原因: get_xlsx_preview_status 由任务 2 实现, 放主文件会让整个模块收集失败
(ImportError), 连 worker/切片可过的用例也跑不了 — 故按任务预案临时拆分。
DB fixture: conftest db (TEST_DATABASE_URL); 缓存走 monkeypatch 的根目录。
"""
import json
import uuid as _uuid

import pytest

from app.api.v1 import drive_files
from app.api.v1.drive_files import (
    _xlsx_cache_key,
    get_xlsx_preview_status,
)
from app.models.knowledge import Knowledge
from app.models.member import Member


async def _mk_member(db, tag):
    u = _uuid.uuid4().hex[:8]
    m = Member(
        username=f"xp_{tag}_{u}", name=tag, password_hash="h",
        role="member", grade="测试", is_active=True, wechat_id=f"wx_xp_{tag}_{u}",
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


async def _mk_file(db, owner, file_name, updated_at=None):
    k = Knowledge(
        content="", title=file_name, storage_mode="drive", file_name=file_name,
        file_path=f"drive-test/{file_name}", created_by=owner.id, visibility="team",
    )
    if updated_at is not None:
        k.updated_at = updated_at
    db.add(k)
    await db.commit()
    await db.refresh(k)
    return k


@pytest.mark.asyncio
async def test_xls_rejected_400(db):
    """.xls 老格式 → 400 (v1 不支持)"""
    u = await _mk_member(db, "u")
    f = await _mk_file(db, u, "old.xls")
    with pytest.raises(Exception) as ei:
        await get_xlsx_preview_status(file_id=f.id, max_rows=8, db=db, current_user=u)
    assert getattr(ei.value, "status_code", None) == 400


@pytest.mark.asyncio
async def test_non_xlsx_rejected_400(db):
    """非表格扩展名 → 400"""
    u = await _mk_member(db, "u")
    f = await _mk_file(db, u, "doc.docx")
    with pytest.raises(Exception) as ei:
        await get_xlsx_preview_status(file_id=f.id, max_rows=8, db=db, current_user=u)
    assert getattr(ei.value, "status_code", None) == 400


@pytest.mark.asyncio
async def test_endpoint_cache_hit(db, tmp_path, monkeypatch):
    """ready.json 已存在 → 直接切片返回, 不再触发 worker"""
    u = await _mk_member(db, "u")
    f = await _mk_file(db, u, "exp.xlsx")
    root = tmp_path / "xr"
    monkeypatch.setattr(drive_files, "_XLSX_PREVIEW_ROOT", root)
    key = _xlsx_cache_key(f.updated_at)
    d = root / ("%d_%s" % (f.id, key))
    d.mkdir(parents=True)
    (d / "ready.json").write_text(json.dumps({"sheets": [{
        "name": "S", "total_rows": 260, "truncated": True,
        "rows": [[str(i)] for i in range(200)]}]}, ensure_ascii=False), encoding="utf-8")
    resp = await get_xlsx_preview_status(file_id=f.id, max_rows=8, db=db, current_user=u)
    assert resp["status"] == "ready"
    assert len(resp["sheets"][0]["rows"]) == 8
    assert resp["sheets"][0]["name"] == "S"


@pytest.mark.asyncio
async def test_endpoint_error_file(db, tmp_path, monkeypatch):
    """error.txt 已存在 → status=error 带消息 (前端回落占位)"""
    u = await _mk_member(db, "u")
    f = await _mk_file(db, u, "bad.xlsx")
    root = tmp_path / "xr"
    monkeypatch.setattr(drive_files, "_XLSX_PREVIEW_ROOT", root)
    d = root / ("%d_%s" % (f.id, _xlsx_cache_key(f.updated_at)))
    d.mkdir(parents=True)
    (d / "error.txt").write_text("BadZipFile: File is not a zip file", encoding="utf-8")
    resp = await get_xlsx_preview_status(file_id=f.id, max_rows=8, db=db, current_user=u)
    assert resp["status"] == "error"
    assert "BadZipFile" in resp["message"]
