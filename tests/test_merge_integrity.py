"""chunked_upload_service.assert_merged_integrity 测试 (2026-09-18 会议 253 事故)

事故: 307 个实时 webm 分片 (~5MB) 走 ffmpeg concat, 无 header 的 cluster 续片
被 ffmpeg **静默丢弃** (rc=0), 产物只剩首片 15KB ≈ 0.96s → 8 分钟会议只转出
一个词。校验函数必须在"产物 << 输入"时抛错, 触发调用方的 raw 字节拼接兜底。
"""

import pytest

from app.services.chunked_upload_service import ChunkedUploadService


svc = ChunkedUploadService


def test_integrity_ok_when_output_close_to_input():
    """正常拼接: 产物 ≈ 输入 (±header 开销) → 不抛"""
    svc.assert_merged_integrity(5_000_000, 5_010_000)
    svc.assert_merged_integrity(1000, 1000)


def test_integrity_ok_for_empty_input():
    """无输入 (0 字节) → 直接放行 (上游已有空产物检查)"""
    svc.assert_merged_integrity(0, 0)


def test_integrity_raises_when_output_is_tiny_fraction():
    """会议 253 实况复现: 307 片 5MB 只产出 15KB → 必须抛"""
    with pytest.raises(RuntimeError, match="raw 字节拼接"):
        svc.assert_merged_integrity(15_945, 5_000_000)


def test_integrity_raises_at_half_threshold():
    """阈值边界: 刚好低于一半 → 抛; 刚好过半 → 放行"""
    with pytest.raises(RuntimeError):
        svc.assert_merged_integrity(499, 1000)
    svc.assert_merged_integrity(501, 1000)
