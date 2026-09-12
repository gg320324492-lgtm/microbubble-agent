"""XLSX 预览 (2026-09-07 选型 D) — worker 解析规则 + 切片纯函数 + 端点状态机测试

覆盖: worker 截断(200 行×6 列)/单元格 24 字符裁剪/空表/truncated 语义/200 行边界,
_slice_xlsx_sheets 切片, updated_at 变化 → key 轮换,
端点 .xls/非 xlsx 400 / ready.json 缓存命中 / error.txt / MinIO 下载失败→error+锁释放。
不依赖 MinIO: worker 直接喂临时文件; 端点下载路径 monkeypatch file_service。
DB fixture: conftest db (TEST_DATABASE_URL); 缓存走 monkeypatch 的根目录。
"""
import json
import uuid as _uuid
from datetime import timedelta

import pytest
from fastapi import HTTPException
from openpyxl import Workbook

from app.api.v1 import drive_files
from app.api.v1.drive_files import (
    _clip_cell,
    _slice_xlsx_sheets,
    _xlsx_cache_dir,
    _xlsx_cache_key,
    _xlsx_preview_worker,
    get_xlsx_preview_status,
)
from app.models.knowledge import Knowledge
from app.models.member import Member


async def _mk_member(db, tag):
    u = _uuid.uuid4().hex[:8]
    m = Member(
        username=f"xp_{tag}_{u}", name=tag, password_hash="h",
        role="member", grade="测试", is_active=True    )
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


def _write_xlsx(path, rows_by_sheet):
    wb = Workbook()
    for i, (name, rows) in enumerate(rows_by_sheet.items()):
        ws = wb.active if i == 0 else wb.create_sheet()
        ws.title = name
        for r in rows:
            ws.append(r)
    wb.save(path)


def test_worker_truncation_and_clipping(tmp_path):
    """worker: 30 行文件全量缓存, 70 列截前 60 列, 40 字符单元格裁到 24"""
    p = tmp_path / "in.xlsx"
    long_cell = "X" * 40
    head = [long_cell, "列B", "列C", "列D", "列E", "列F", "列G"] + [f"列{i}" for i in range(8, 71)]
    _write_xlsx(p, {
        "数据": [head]
               + [[long_cell, j, "", None, 1.5, True, "g"] + [f"c{k}" for k in range(63)]
                  for j in range(29)],
        "空表": [],
    })
    cache_dir = tmp_path / "cache"
    _xlsx_preview_worker(1, str(p), cache_dir, "k")
    data = json.loads((cache_dir / "ready.json").read_text(encoding="utf-8"))
    s1, s2 = data["sheets"]
    assert s1["name"] == "数据"
    assert s1["total_rows"] == 30
    assert len(s1["rows"]) == 30
    assert all(len(r) == 60 for r in s1["rows"])         # 70 列 → 前 60 列
    assert s1["rows"][1][0] == "X" * 24                  # 单元格 24 字符裁剪
    assert s1["rows"][0][1] == "列B"
    assert s1["rows"][0][59] == "列60"                    # 第 60 列在缓存内
    assert s1["truncated"] is False                      # 30 行未超 200 缓存上限
    assert s2["rows"] == [] and s2["truncated"] is False  # 空表不算截断


def test_worker_caps_200_rows(tmp_path):
    """worker: 301 行文件只缓存前 200 行, truncated=True"""
    p = tmp_path / "big.xlsx"
    _write_xlsx(p, {"大表": [["h1", "h2"]] + [[i, i] for i in range(300)]})
    cache_dir = tmp_path / "cache"
    _xlsx_preview_worker(2, str(p), cache_dir, "k")
    data = json.loads((cache_dir / "ready.json").read_text(encoding="utf-8"))
    s = data["sheets"][0]
    assert len(s["rows"]) == 200
    assert s["total_rows"] == 301
    assert s["truncated"] is True


def test_slice_max_rows():
    """端点切片: max_rows 截 rows, truncated 按 total_rows 重算"""
    sheets = [{"name": "s", "total_rows": 260, "truncated": True,
               "rows": [[str(i)] for i in range(200)]}]
    cut = _slice_xlsx_sheets(sheets, 8)
    assert len(cut[0]["rows"]) == 8 and cut[0]["truncated"] is True
    cut_all = _slice_xlsx_sheets(sheets, 200)
    assert len(cut_all[0]["rows"]) == 200 and cut_all[0]["truncated"] is True
    exact = _slice_xlsx_sheets(
        [{"name": "e", "total_rows": 8, "truncated": False,
          "rows": [[str(i)] for i in range(8)]}], 200)
    assert exact[0]["truncated"] is False                # 8 行全量缓存 → 未截断


@pytest.mark.asyncio
async def test_cache_key_rotates_with_updated_at(db):
    """updated_at 变化 → key 变化 → 旧缓存自动失效"""
    u = await _mk_member(db, "u")
    f1 = await _mk_file(db, u, "a.xlsx")
    f2 = await _mk_file(db, u, "b.xlsx", updated_at=f1.updated_at + timedelta(hours=1))
    assert _xlsx_cache_key(f1.updated_at) != _xlsx_cache_key(f2.updated_at)


# === 端点状态机 (任务 2 合回) ===


@pytest.mark.asyncio
async def test_xls_rejected_400(db):
    """.xls 老格式 → 400 (v1 不支持)"""
    u = await _mk_member(db, "u")
    f = await _mk_file(db, u, "old.xls")
    with pytest.raises(HTTPException) as ei:
        await get_xlsx_preview_status(file_id=f.id, max_rows=8, db=db, current_user=u)
    assert ei.value.status_code == 400


@pytest.mark.asyncio
async def test_non_xlsx_rejected_400(db):
    """非表格扩展名 → 400"""
    u = await _mk_member(db, "u")
    f = await _mk_file(db, u, "doc.docx")
    with pytest.raises(HTTPException) as ei:
        await get_xlsx_preview_status(file_id=f.id, max_rows=8, db=db, current_user=u)
    assert ei.value.status_code == 400


@pytest.mark.asyncio
async def test_endpoint_cache_hit(db, tmp_path, monkeypatch):
    """ready.json 已存在 → 直接切片返回, 不再触发 worker"""
    u = await _mk_member(db, "u")
    f = await _mk_file(db, u, "exp.xlsx")
    monkeypatch.setattr(drive_files, "_XLSX_PREVIEW_ROOT", tmp_path / "xr")
    key = _xlsx_cache_key(f.updated_at)
    d = _xlsx_cache_dir(f.id, key)
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
    monkeypatch.setattr(drive_files, "_XLSX_PREVIEW_ROOT", tmp_path / "xr")
    d = _xlsx_cache_dir(f.id, _xlsx_cache_key(f.updated_at))
    d.mkdir(parents=True)
    (d / "error.txt").write_text("BadZipFile: File is not a zip file", encoding="utf-8")
    resp = await get_xlsx_preview_status(file_id=f.id, max_rows=8, db=db, current_user=u)
    assert resp["status"] == "error"
    assert "BadZipFile" in resp["message"]


# === 任务 2 新增: 下载失败/200 行边界/单元格裁剪 ===


@pytest.mark.asyncio
async def test_endpoint_download_failure_writes_error_and_releases_lock(db, tmp_path, monkeypatch):
    """MinIO 下载失败 → status=error + error.txt + 锁释放 (不滞留 converting)"""
    async def _boom(object_name):
        raise RuntimeError("minio down")
    u = await _mk_member(db, "u")
    f = await _mk_file(db, u, "net.xlsx")
    monkeypatch.setattr(drive_files, "_XLSX_PREVIEW_ROOT", tmp_path / "xr")
    monkeypatch.setattr(drive_files.file_service, "download_file", _boom)
    resp = await get_xlsx_preview_status(file_id=f.id, max_rows=8, db=db, current_user=u)
    assert resp["status"] == "error" and "minio down" in resp["message"]
    assert drive_files._XLSX_PREVIEW_LOCKS == {}          # 锁已释放
    assert (drive_files._xlsx_cache_dir(f.id, _xlsx_cache_key(f.updated_at)) / "error.txt").exists()


def test_worker_exact_200_boundary(tmp_path):
    """恰好 200 行 → 全缓存且 truncated=False; 201 行 → truncated=True"""
    p = tmp_path / "edge.xlsx"
    _write_xlsx(p, {"s": [["h1", "h2"]] + [[i, i] for i in range(199)]})
    cache_dir = tmp_path / "c1"
    _xlsx_preview_worker(3, str(p), cache_dir, "k")
    s = json.loads((cache_dir / "ready.json").read_text(encoding="utf-8"))["sheets"][0]
    assert len(s["rows"]) == 200 and s["truncated"] is False and s["total_rows"] == 200
    p2 = tmp_path / "edge2.xlsx"
    _write_xlsx(p2, {"s": [["h1", "h2"]] + [[i, i] for i in range(200)]})
    cache_dir2 = tmp_path / "c2"
    _xlsx_preview_worker(4, str(p2), cache_dir2, "k")
    s2 = json.loads((cache_dir2 / "ready.json").read_text(encoding="utf-8"))["sheets"][0]
    assert len(s2["rows"]) == 200 and s2["truncated"] is True and s2["total_rows"] == 201


def test_clip_cell_none_to_empty():
    """None → 空串, 非 None → str 截 24"""
    assert _clip_cell(None) == ""
    assert _clip_cell(42) == "42"
    assert _clip_cell("Y" * 30) == "Y" * 24
