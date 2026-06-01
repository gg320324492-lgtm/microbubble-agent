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
    """upload_to_path 上传 bytes 到指定 object_name（mock MinIO put_object）"""
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
        # 验证 put_object 被以正确参数调用
        file_service.client.put_object.assert_called_once()
        call_kwargs = file_service.client.put_object.call_args.kwargs
        assert call_kwargs["Bucket"] == file_service.bucket
        assert call_kwargs["Key"] == object_name
        assert call_kwargs["Length"] == len(test_bytes)
        assert call_kwargs["ContentType"] == "audio/ogg"
