"""tests/test_drive_v2_pr9_import_smoke.py — Drive v2 PR9 version_diff_service import smoke (2026-07-24)

W68 第 5 批 hot-fix: drive_version_diff_service.py 漏 import `select` 导致模块加载失败.
此文件为教训沉淀 — 任何派工新建 service 文件都必须跑 import smoke 验证.

核心场景 (3 个 import smoke):
1. import app.services.drive_version_diff_service 模块本身能 load
2. import DriveVersionDiffService 类 (API 路由依赖)
3. import DriveVersionDiffServiceError 异常类 (API 路由依赖)

W68 第 4 批 #7 desktop-version-diff agent 漏掉此检查, 主指挥 W68 第 5 批 hot-fix 修复.

依赖: 无 (纯 import smoke, 不连 DB / API)
"""
import importlib

import pytest


MODULE_NAME = "app.services.drive_version_diff_service"


def test_smoke_01_module_importable():
    """场景 1: drive_version_diff_service 模块本身能 load.

    关键检查: module 不能因为 NameError (如 select 未定义) 加载失败.
    修复前: ImportError: cannot import name 'compare_versions' (根因 select 未 import).
    """
    module = importlib.import_module(MODULE_NAME)
    assert module is not None
    assert hasattr(module, "__file__"), f"{MODULE_NAME} 模块加载失败"


def test_smoke_02_drive_version_diff_service_class_importable():
    """场景 2: DriveVersionDiffService 类可被 import.

    API 路由 app/api/v1/drive_version_diff.py L29-32 依赖:
        from app.services.drive_version_diff_service import (
            DriveVersionDiffService,
            DriveVersionDiffServiceError,
        )
    """
    from app.services.drive_version_diff_service import DriveVersionDiffService

    assert DriveVersionDiffService is not None
    assert callable(DriveVersionDiffService), "DriveVersionDiffService 必须可调用"


def test_smoke_03_drive_version_diff_service_error_class_importable():
    """场景 3: DriveVersionDiffServiceError 异常类可被 import.

    异常处理 / 装饰器依赖: HTTPException 转换.
    """
    from app.services.drive_version_diff_service import DriveVersionDiffServiceError

    assert DriveVersionDiffServiceError is not None
    assert issubclass(DriveVersionDiffServiceError, Exception)