"""测试 file_service.upload_to_path

设计原则：
- **不依赖真实 MinIO**：在 import file_service 之前，把整个 minio 模块替换为 MagicMock，
  避免 import 时连接 MinIO（在 SKIP_DB_SETUP=1 模式下也能运行）
- **占位测试 + 完整结构验证**：验证方法存在性、签名、行为
"""

import sys
import importlib
import inspect
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# ====================================================================
# 在 import 之前 mock 掉 minio 模块，阻止真实 Minio 客户端创建
# ====================================================================
# 把整个 minio 模块替换为 MagicMock，这样 `from minio import Minio` 拿到的是 Mock
sys.modules.setdefault("minio", MagicMock())

# 清掉可能缓存的 file_service，避免 import 时 Network 调用
if "app.services.file_service" in sys.modules:
    importlib.reload(sys.modules["app.services.file_service"])

from app.services.file_service import FileService, file_service  # noqa: E402


# ====================================================================
# 实际测试
# ====================================================================


def test_upload_to_path_method_exists():
    """FileService 必须有 upload_to_path 方法（bypass UUID 固定路径上传）"""
    assert hasattr(FileService, "upload_to_path"), "FileService 缺少 upload_to_path 方法"
    assert inspect.iscoroutinefunction(FileService.upload_to_path), "upload_to_path 必须是 async 方法"


def test_upload_to_path_signature():
    """upload_to_path 应接受 (object_name, file_data, content_type) 参数"""
    sig = inspect.signature(FileService.upload_to_path)
    params = sig.parameters
    assert "object_name" in params
    assert "file_data" in params
    assert "content_type" in params


@pytest.mark.asyncio
async def test_upload_to_path_basic():
    """upload_to_path 上传 bytes 到指定 object_name (mock MinIO put_object 用位置参数 API)

    W1 (2026-07-21) T1 endpoint_404 fix: 测试从 s3 kwargs API 改成 minio-py 位置参数 API
    (生产 file_service.py 用 minio-py: client.put_object(bucket, object_name, data, length, content_type))
    """
    test_bytes = b"fake audio content for testing"
    object_name = "test_uploads/audio_test.opus"

    with patch.object(file_service, "delete_file", new=AsyncMock(return_value=None)):
        result = await file_service.upload_to_path(
            object_name=object_name,
            file_data=test_bytes,
            content_type="audio/ogg",
        )
        assert result["object_name"] == object_name
        assert result["size"] == len(test_bytes)
        assert result["content_type"] == "audio/ogg"
        # 验证 put_object 被以正确位置参数调用 (minio-py 风格)
        file_service.client.put_object.assert_called_once()
        call_args = file_service.client.put_object.call_args.args
        call_kwargs = file_service.client.put_object.call_args.kwargs
        # minio-py 位置参数: (bucket_name, object_name, data, length, content_type)
        assert call_args[0] == file_service.bucket  # bucket_name
        assert call_args[1] == object_name  # object_name
        assert call_kwargs.get("length") == len(test_bytes)
        assert call_kwargs.get("content_type") == "audio/ogg"
