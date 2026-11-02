"""staging 两阶段替换 + 合并产物时长保护（2026-11-02 会议 265 事故）。

事故：前端结束听会时先 `chunks/reset` 删掉 5041 个实时分片，再整段重传；
只传了 6 片浏览器就关闭 ⇒ 服务器上只剩 24MB，完整录音只剩浏览器内存。
修复：
1. 整段重传先写 `staging/` 前缀（不碰实时分片），merge 成功后才清理旧分片；
2. merge 产物明显短于录音墙钟时保留分片不删（`should_preserve_chunks`）。

本文件只测纯逻辑 + mock 掉 MinIO，不连 DB/网络。
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

from app.services.chunked_upload_service import ChunkedUploadService


svc = ChunkedUploadService()


def _run(coro):
    return asyncio.run(coro)


# ---------- 对象命名 ----------


def test_staged_object_name_uses_staging_prefix_and_bin_suffix():
    name = svc._staged_chunk_object_name(265, 7)
    assert name == "recordings/265/staging/chunk_00007.bin"
    # 与实时分片前缀必须完全隔离
    assert not name.startswith("recordings/265/chunks/")
    assert svc._chunk_object_name(265, 7) == "recordings/265/chunks/chunk_00007.webm"


# ---------- 暂存分片读写 ----------


def test_save_staged_chunk_writes_staging_prefix():
    upload = AsyncMock()
    with patch("app.services.chunked_upload_service.file_service") as fs:
        fs.upload_to_path = upload
        name = _run(svc.save_staged_chunk(265, 3, b"\x1aE\xdf\xa3fake"))

    assert name == "recordings/265/staging/chunk_00003.bin"
    assert upload.await_count == 1
    kwargs = upload.await_args.kwargs
    assert kwargs["object_name"] == name
    assert kwargs["file_data"] == b"\x1aE\xdf\xa3fake"


def test_list_staged_chunks_filters_and_sorts():
    objs = [
        {"object_name": "recordings/265/staging/chunk_00002.bin", "size": 20},
        {"object_name": "recordings/265/staging/chunk_00000.bin", "size": 10},
        {"object_name": "recordings/265/staging/notes.txt", "size": 1},  # 非分片 → 忽略
        {"object_name": "recordings/265/chunks/chunk_00009.webm", "size": 9},  # 另一前缀
    ]
    with patch("app.services.chunked_upload_service.file_service") as fs:
        fs.list_objects = AsyncMock(return_value=objs)
        got = _run(svc.list_staged_chunks(265))

    assert [o["chunk_index"] for o in got] == [0, 2]
    assert fs.list_objects.await_args.kwargs["prefix"] == "recordings/265/staging/"


def test_delete_staged_chunks_deletes_only_staging_objects():
    objs = [
        {"object_name": "recordings/265/staging/chunk_00000.bin", "size": 10},
        {"object_name": "recordings/265/staging/chunk_00001.bin", "size": 10},
    ]
    with patch("app.services.chunked_upload_service.file_service") as fs:
        fs.list_objects = AsyncMock(return_value=objs)
        # delete_file 是同步方法（普通 def），不能用 AsyncMock
        fs.delete_file = Mock()
        deleted = _run(svc.delete_staged_chunks(265))

    assert deleted == 2
    assert fs.list_objects.await_args.kwargs["prefix"] == "recordings/265/staging/"
    deleted_names = [c.args[0] for c in fs.delete_file.call_args_list]
    assert deleted_names == [o["object_name"] for o in objs]


def test_merge_staged_raw_concatenates_only_staged_chunks():
    chunks = [
        {"object_name": "recordings/265/staging/chunk_00000.bin", "chunk_index": 0},
        {"object_name": "recordings/265/staging/chunk_00001.bin", "chunk_index": 1},
    ]
    with patch("app.services.chunked_upload_service.file_service") as fs:
        fs.download_file = AsyncMock(side_effect=[b"AAA", b"BBB"])
        fs.upload_to_path = AsyncMock()
        with patch.object(svc, "list_staged_chunks", AsyncMock(return_value=chunks)):
            name = _run(svc.merge_staged_raw(265))

    assert fs.download_file.await_count == 2
    assert fs.upload_to_path.await_args.kwargs["file_data"] == b"AAABBB"
    # 产物仍写到统一的 merged 路径
    assert name.startswith("recordings/265/merged.")


def test_merge_staged_raw_raises_when_empty():
    with patch.object(svc, "list_staged_chunks", AsyncMock(return_value=[])):
        try:
            _run(svc.merge_staged_raw(265))
        except ValueError as e:
            assert "无 chunk 可合并" in str(e)
        else:  # pragma: no cover
            raise AssertionError("空 staging 必须抛 ValueError")


# ---------- 合并产物时长保护 ----------


def test_preserve_chunks_when_merged_audio_too_short():
    # 会议 265 实况：录音墙钟 7870s，合并产物只有 24MB ≈ 1500s
    assert svc.should_preserve_chunks(1500, 7870) is True


def test_do_not_preserve_when_duration_matches():
    assert svc.should_preserve_chunks(7500, 7500) is False
    # 允许 10% 误差
    assert svc.should_preserve_chunks(6800, 7500) is False
    assert svc.should_preserve_chunks(6700, 7500) is True


def test_do_not_preserve_when_expected_unknown_or_short():
    assert svc.should_preserve_chunks(100, None) is False
    assert svc.should_preserve_chunks(100, 0) is False
    assert svc.should_preserve_chunks(100, 30) is False  # 区间 < 60s 不判
    assert svc.should_preserve_chunks(None, 7500) is False
    assert svc.should_preserve_chunks(0, 7500) is False
