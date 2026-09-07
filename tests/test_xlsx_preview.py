"""XLSX 预览 (2026-09-07 选型 D) — worker 解析规则 + 纯函数测试

覆盖: worker 截断(200 行×6 列)/单元格 24 字符裁剪/空表/truncated 语义,
_slice_xlsx_sheets 切片, updated_at 变化 → key 轮换。
不依赖 MinIO: worker 直接喂临时文件。
端点状态机用例 (依赖 get_xlsx_preview_status, 任务 2 实现) 暂拆在
tests/test_xlsx_preview_endpoint.py, 任务 2 合回本文件。
DB fixture: conftest db (TEST_DATABASE_URL)。
"""
import json
import uuid as _uuid
from datetime import timedelta

import pytest
from openpyxl import Workbook

from app.api.v1.drive_files import (
    _slice_xlsx_sheets,
    _xlsx_cache_key,
    _xlsx_preview_worker,
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


def _write_xlsx(path, rows_by_sheet):
    wb = Workbook()
    for i, (name, rows) in enumerate(rows_by_sheet.items()):
        ws = wb.active if i == 0 else wb.create_sheet()
        ws.title = name
        for r in rows:
            ws.append(r)
    wb.save(path)


def test_worker_truncation_and_clipping(tmp_path):
    """worker: 30 行文件全量缓存, 7 列截前 6 列, 40 字符单元格裁到 24"""
    p = tmp_path / "in.xlsx"
    long_cell = "X" * 40
    _write_xlsx(p, {
        "数据": [["列A", "列B", "列C", "列D", "列E", "列F", "列G"]]
               + [[long_cell, j, "", None, 1.5, True, "g"] for j in range(29)],
        "空表": [],
    })
    cache_dir = tmp_path / "cache"
    _xlsx_preview_worker(1, str(p), cache_dir, "k")
    data = json.loads((cache_dir / "ready.json").read_text(encoding="utf-8"))
    s1, s2 = data["sheets"]
    assert s1["name"] == "数据"
    assert s1["total_rows"] == 30
    assert len(s1["rows"]) == 30
    assert all(len(r) == 6 for r in s1["rows"])          # 7 列 → 前 6 列
    assert s1["rows"][1][0] == "X" * 24                  # 单元格 24 字符裁剪
    assert s1["rows"][0][0] == "列A"
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
