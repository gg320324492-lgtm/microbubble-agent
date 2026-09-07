"""CSV 预览 (2026-09-07 选型 A 数据网格) — worker 解析 + 端点状态机测试

覆盖: utf-8/gb18030 编码探测, 带引号字段含逗号/换行, 200 行截断与全量行数统计,
列裁剪, 端点非 csv 400/缓存命中/误差文件, key 轮换。
不依赖 MinIO: worker 直接喂临时文件; 端点走 monkeypatch 的缓存根目录。
DB fixture: conftest db (TEST_DATABASE_URL)。
"""
import json
import uuid as _uuid
from datetime import timedelta

import pytest

from app.api.v1 import drive_files
from app.api.v1.drive_files import (
    _csv_cache_key,
    _csv_preview_worker,
    get_csv_preview_status,
)
from app.models.knowledge import Knowledge
from app.models.member import Member


async def _mk_member(db, tag):
    u = _uuid.uuid4().hex[:8]
    m = Member(
        username=f"cp_{tag}_{u}", name=tag, password_hash="h",
        role="member", grade="测试", is_active=True, wechat_id=f"wx_cp_{tag}_{u}",
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


def test_worker_utf8_parse_and_headers(tmp_path):
    """worker: utf-8 csv → rows 含表头, 引号字段内逗号/换行不拆列"""
    p = tmp_path / "in.csv"
    p.write_bytes(
        "时间戳,温度(°C),状态\n"
        "2026-09-07 08:00:00,24.82,OK\n"
        '"含,逗号","含\n换行",OK\n'
        .encode("utf-8"))
    cache_dir = tmp_path / "cache"
    _csv_preview_worker(1, str(p), cache_dir, "k")
    data = json.loads((cache_dir / "ready.json").read_text(encoding="utf-8"))
    assert data["encoding"] == "utf-8"
    assert data["total_rows"] == 3
    assert data["rows"][0] == ["时间戳", "温度(°C)", "状态"]
    assert data["rows"][2] == ["含,逗号", "含\n换行", "OK"]
    assert data["truncated"] is False


def test_worker_gb18030_encoding_detected(tmp_path):
    """worker: GBK 编码 csv → 自动探测 gb18030, 中文不乱码"""
    p = tmp_path / "gbk.csv"
    p.write_bytes("样品,备注\n纯水对照,首次测量\n".encode("gb18030"))
    cache_dir = tmp_path / "cache"
    _csv_preview_worker(2, str(p), cache_dir, "k")
    data = json.loads((cache_dir / "ready.json").read_text(encoding="utf-8"))
    assert data["encoding"] == "gb18030"
    assert data["rows"][1] == ["纯水对照", "首次测量"]


def test_worker_caps_200_rows_and_counts_total(tmp_path):
    """worker: 260 行 → 缓存 200, total_rows=260, truncated=True"""
    p = tmp_path / "big.csv"
    lines = ["idx,val"] + [f"{i},{i * 2}" for i in range(259)]
    p.write_bytes("\n".join(lines).encode("utf-8"))
    cache_dir = tmp_path / "cache"
    _csv_preview_worker(3, str(p), cache_dir, "k")
    data = json.loads((cache_dir / "ready.json").read_text(encoding="utf-8"))
    assert len(data["rows"]) == 200
    assert data["total_rows"] == 260
    assert data["truncated"] is True


def test_worker_cell_clip_and_trailing_empty_cols(tmp_path):
    """worker: 单元格 24 字符裁剪; 长短不齐行裁掉全空尾列"""
    p = tmp_path / "clip.csv"
    long_cell = "Y" * 40
    p.write_bytes(f"a,b\n{long_cell},1,\n".encode("utf-8"))
    cache_dir = tmp_path / "cache"
    _csv_preview_worker(4, str(p), cache_dir, "k")
    data = json.loads((cache_dir / "ready.json").read_text(encoding="utf-8"))
    assert data["rows"][1][0] == "Y" * 24
    assert data["cols"] == 2   # 第三列所有行皆空 → 裁掉


def test_worker_binary_writes_error(tmp_path):
    """worker: 二进制垃圾 → error.txt"""
    p = tmp_path / "bad.csv"
    p.write_bytes(bytes(range(256)) * 8)
    cache_dir = tmp_path / "cache"
    _csv_preview_worker(5, str(p), cache_dir, "k")
    assert (cache_dir / "error.txt").exists()


@pytest.mark.asyncio
async def test_non_csv_rejected_400(db):
    u = await _mk_member(db, "u")
    f = await _mk_file(db, u, "data.xlsx")
    with pytest.raises(Exception) as ei:
        await get_csv_preview_status(file_id=f.id, max_rows=8, db=db, current_user=u)
    assert getattr(ei.value, "status_code", None) == 400


@pytest.mark.asyncio
async def test_endpoint_cache_hit(db, tmp_path, monkeypatch):
    u = await _mk_member(db, "u")
    f = await _mk_file(db, u, "sensor.csv")
    root = tmp_path / "cr"
    monkeypatch.setattr(drive_files, "_CSV_PREVIEW_ROOT", root)
    d = drive_files._csv_cache_dir(f.id, _csv_cache_key(f.updated_at))
    d.mkdir(parents=True)
    (d / "ready.json").write_text(json.dumps({
        "rows": [["h1"], ["v1"]], "total_rows": 2, "truncated": False,
        "encoding": "utf-8", "cols": 1,
    }, ensure_ascii=False), encoding="utf-8")
    resp = await get_csv_preview_status(file_id=f.id, max_rows=8, db=db, current_user=u)
    assert resp["status"] == "ready"
    assert resp["rows"] == [["h1"], ["v1"]]
    assert resp["cols"] == 1


@pytest.mark.asyncio
async def test_endpoint_error_file(db, tmp_path, monkeypatch):
    u = await _mk_member(db, "u")
    f = await _mk_file(db, u, "bad.csv")
    root = tmp_path / "cr"
    monkeypatch.setattr(drive_files, "_CSV_PREVIEW_ROOT", root)
    d = drive_files._csv_cache_dir(f.id, _csv_cache_key(f.updated_at))
    d.mkdir(parents=True)
    (d / "error.txt").write_text("decoder error", encoding="utf-8")
    resp = await get_csv_preview_status(file_id=f.id, max_rows=8, db=db, current_user=u)
    assert resp["status"] == "error" and "decoder error" in resp["message"]


@pytest.mark.asyncio
async def test_cache_key_rotates_with_updated_at(db):
    u = await _mk_member(db, "u")
    f1 = await _mk_file(db, u, "a.csv")
    f2 = await _mk_file(db, u, "b.csv", updated_at=f1.updated_at + timedelta(hours=1))
    assert _csv_cache_key(f1.updated_at) != _csv_cache_key(f2.updated_at)
