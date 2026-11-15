"""ZIP 预览 (2026-09-07 选型 A 清单下钻) — worker 条目抽取 + 端点状态机测试

覆盖: worker 目录自动补齐(隐式父目录)/文件+大小/总数统计/条目上限,
端点 .zip 400/缓存命中/误差文件, key 基准 (file_path, 非 updated_at)。
不依赖 MinIO: worker 直接喂临时 zip; 端点走 monkeypatch 的缓存根目录。
DB fixture: conftest db (TEST_DATABASE_URL)。
"""
import json
import uuid as _uuid
import zipfile
from datetime import timedelta

import pytest

from app.api.v1 import drive_files
from app.api.v1.drive_files import (
    _decode_archive_name,
    _zip_cache_key,
    _zip_preview_worker,
    get_zip_list,
)
from app.models.knowledge import Knowledge
from app.models.member import Member


async def _mk_member(db, tag):
    u = _uuid.uuid4().hex[:8]
    m = Member(
        username=f"zp_{tag}_{u}", name=tag, password_hash="h",
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


def _write_zip(path, files, dirs=()):
    """files: {arcname: content}; dirs: 显式目录条目 (部分 zip 会有)"""
    with zipfile.ZipFile(path, "w") as zf:
        for d in dirs:
            zf.writestr(d if d.endswith("/") else d + "/", "")
        for arcname, content in files.items():
            zf.writestr(arcname, content)


def test_worker_builds_entries_and_synthesizes_dirs(tmp_path):
    """worker: 文件条目+大小, 隐式父目录自动补齐, 统计正确, 排序稳定"""
    p = tmp_path / "in.zip"
    _write_zip(p, {
        "实验数据/表面张力.xlsx": "x" * 100,
        "实验数据/子目录/zeta.csv": "y" * 50,
        "README.txt": "hello",
    })
    cache_dir = tmp_path / "cache"
    _zip_preview_worker(1, str(p), cache_dir, "k")
    data = json.loads((cache_dir / "ready.json").read_text(encoding="utf-8"))
    assert data["total_files"] == 3
    assert data["total_size"] == 100 + 50 + 5
    assert data["truncated"] is False
    paths = {e["path"]: e for e in data["entries"]}
    # 隐式父目录全部补齐 (含没有显式目录条目的 多级路径)
    for expected in ["实验数据", "实验数据/子目录", "README.txt",
                     "实验数据/表面张力.xlsx", "实验数据/子目录/zeta.csv"]:
        assert expected in paths, f"缺少条目: {expected}"
    assert paths["实验数据"]["dir"] is True and paths["实验数据"]["size"] == 0
    assert paths["实验数据/表面张力.xlsx"]["size"] == 100
    assert paths["README.txt"]["dir"] is False


def test_worker_caps_entries(tmp_path):
    """worker: 条目超上限 → truncated=True 且缓存被截断"""
    p = tmp_path / "big.zip"
    files = {f"f{i:05d}.txt": "x" for i in range(drive_files._ZIP_MAX_ENTRIES + 50)}
    _write_zip(p, files)
    cache_dir = tmp_path / "cache"
    _zip_preview_worker(2, str(p), cache_dir, "k")
    data = json.loads((cache_dir / "ready.json").read_text(encoding="utf-8"))
    assert len(data["entries"]) == drive_files._ZIP_MAX_ENTRIES
    assert data["truncated"] is True


def test_worker_corrupt_zip_writes_error(tmp_path):
    """worker: 损坏 zip → error.txt"""
    p = tmp_path / "bad.zip"
    p.write_bytes(b"not a zip at all")
    cache_dir = tmp_path / "cache"
    _zip_preview_worker(3, str(p), cache_dir, "k")
    assert (cache_dir / "error.txt").exists()


@pytest.mark.asyncio
async def test_non_zip_rejected_400(db):
    u = await _mk_member(db, "u")
    f = await _mk_file(db, u, "doc.docx")
    with pytest.raises(Exception) as ei:
        await get_zip_list(file_id=f.id, db=db, current_user=u)
    assert getattr(ei.value, "status_code", None) == 400


@pytest.mark.asyncio
async def test_endpoint_cache_hit(db, tmp_path, monkeypatch):
    """ready.json 已存在 → 直接返回条目"""
    u = await _mk_member(db, "u")
    f = await _mk_file(db, u, "archive.zip")
    root = tmp_path / "zr"
    monkeypatch.setattr(drive_files, "_ZIP_PREVIEW_ROOT", root)
    d = drive_files._zip_cache_dir(f.id, _zip_cache_key("v3:" + f.file_path))
    d.mkdir(parents=True)
    (d / "ready.json").write_text(json.dumps({
        "entries": [{"path": "a.txt", "dir": False, "size": 3}],
        "total_files": 1, "total_dirs": 0, "total_size": 3, "truncated": False,
    }, ensure_ascii=False), encoding="utf-8")
    resp = await get_zip_list(file_id=f.id, db=db, current_user=u)
    assert resp["status"] == "ready"
    assert resp["entries"][0]["path"] == "a.txt"
    assert resp["total_files"] == 1


@pytest.mark.asyncio
async def test_endpoint_error_file(db, tmp_path, monkeypatch):
    u = await _mk_member(db, "u")
    f = await _mk_file(db, u, "bad.zip")
    root = tmp_path / "zr"
    monkeypatch.setattr(drive_files, "_ZIP_PREVIEW_ROOT", root)
    d = drive_files._zip_cache_dir(f.id, _zip_cache_key("v3:" + f.file_path))
    d.mkdir(parents=True)
    (d / "error.txt").write_text("BadZipFile", encoding="utf-8")
    resp = await get_zip_list(file_id=f.id, db=db, current_user=u)
    assert resp["status"] == "error" and "BadZipFile" in resp["message"]


@pytest.mark.asyncio
async def test_cache_key_stable_across_updated_at_rotates_with_file_path(db):
    """2026-10-09 (agent39) key 基准改为 file_path, 理由见 _preview_cache_key。"""
    u = await _mk_member(db, "u")
    f1 = await _mk_file(db, u, "a.zip")
    f2 = await _mk_file(db, u, "b.zip", updated_at=f1.updated_at + timedelta(hours=1))
    assert _zip_cache_key(f1.file_path) != _zip_cache_key(f2.file_path)
    bumped = await _mk_file(db, u, "a.zip", updated_at=f1.updated_at + timedelta(hours=1))
    assert bumped.file_path == f1.file_path
    assert _zip_cache_key(bumped.file_path) == _zip_cache_key(f1.file_path)


def test_decode_archive_name_restores_cp437_gbk_bytes():
    """zipfile 对无 UTF-8 flag 的条目按 cp437 解码；还原原始字节再按 GB18030 解码。"""
    info = zipfile.ZipInfo("placeholder")
    info.filename = "╥╗╝ⁿ░▓╫░-Origin2025b.bat"
    info.flag_bits = 0

    assert _decode_archive_name(info) == "一键安装-Origin2025b.bat"


def test_decode_archive_name_keeps_utf8_flag_names():
    """UTF-8 flag 已置位的条目保持 Python zipfile 的正确解码结果。"""
    info = zipfile.ZipInfo("安装说明.md")
    info.flag_bits = 0x800

    assert _decode_archive_name(info) == "安装说明.md"


def test_worker_decodes_cp437_gbk_zip_bytes(tmp_path):
    """真实 ZIP 中央目录里写入 GBK 字节，worker 应产出中文条目名而不是乱码。"""
    p = tmp_path / "gbk.zip"
    gbk_name = "一键安装-Origin2025b.bat"
    # ASCII 占位名长度必须等于 GBK 名称字节数，字节替换才不会改变 ZIP 的偏移。
    gbk_bytes = gbk_name.encode("gbk")
    ascii_name = b"x" * len(gbk_bytes) + b".bat"
    stored_name = gbk_bytes + b".bat"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr(ascii_name.decode(), b"echo ok")
    raw = p.read_bytes()
    # 本地文件头 + 中央目录各一处；等长替换，CRC / 偏移都不变。
    assert raw.count(ascii_name) == 2
    p.write_bytes(raw.replace(ascii_name, stored_name))
    with zipfile.ZipFile(p) as zf:
        stored = zf.infolist()[0]
        assert not (stored.flag_bits & 0x800)
        assert stored.orig_filename.encode("cp437") == stored_name
    cache_dir = tmp_path / "cache"
    _zip_preview_worker(4, str(p), cache_dir, "k")
    data = json.loads((cache_dir / "ready.json").read_text(encoding="utf-8"))
    names = {e["path"] for e in data["entries"]}
    assert gbk_name + ".bat" in names
    assert not any("╥╗" in n or "░▓" in n for n in names)


def test_rar_range_file_reads_only_needed_bytes():
    """RAR 清单只读主头部，不整包下载；seek/read 均走 Range。"""
    calls = []

    class FakeResponse:
        def read(self): return b"X" * 8
        def close(self): pass
        def release_conn(self): pass

    class FakeClient:
        def get_object(self, bucket, object_name, offset=0, length=0):
            calls.append((offset, length))
            return FakeResponse()

    class FakeService:
        bucket = "test"
        client = FakeClient()

    original = drive_files.file_service
    drive_files.file_service = FakeService()
    try:
        f = drive_files._MinioRangeFile("k.rar", 1024)
        f.seek(16)
        assert f.read(8) == b"X" * 8
        assert f.tell() == 24
        assert calls == [(16, 8)]
        assert f.bytes_read == 8
    finally:
        drive_files.file_service = original
