"""
W74 第 1 批 D-1: License 校验实战测试

依据: W73 B-1 a6835841 license_service.py + D-1 §5.2 商业化底线

4 case:
1. License 校验 (online 模式)
2. License 过期 → read_only 模式
3. 离线 7 天宽限 (offline_grace 模式)
4. License 离线超 7 天 → read_only 模式

不依赖真实 DB, mock AsyncSession
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "app"))


# ===== fixtures =====


@pytest.fixture
def mock_license_active():
    """活跃 License (未过期)."""

    lic = MagicMock()
    lic.license_key_hash = "abc123hash"
    lic.tenant_id = "tenant_A"
    lic.tier = "pro"
    lic.is_active = True
    lic.expires_at = datetime.utcnow() + timedelta(days=30)
    lic.last_verified_at = datetime.utcnow()
    return lic


@pytest.fixture
def mock_license_expired():
    """过期 License (read_only)."""

    lic = MagicMock()
    lic.license_key_hash = "expiredhash"
    lic.tenant_id = "tenant_B"
    lic.tier = "basic"
    lic.is_active = True
    lic.expires_at = datetime.utcnow() - timedelta(days=1)
    return lic


@pytest.fixture
def mock_license_offline_grace():
    """离线宽限期内 License (last_verified 3 天前)."""

    lic = MagicMock()
    lic.license_key_hash = "gracehash"
    lic.tenant_id = "tenant_C"
    lic.tier = "enterprise"
    lic.is_active = True
    lic.expires_at = datetime.utcnow() + timedelta(days=365)
    lic.last_verified_at = datetime.utcnow() - timedelta(days=3)
    return lic


@pytest.fixture
def mock_license_grace_exceeded():
    """离线超 7 天 License (last_verified 10 天前)."""

    lic = MagicMock()
    lic.license_key_hash = "exceededhash"
    lic.tenant_id = "tenant_D"
    lic.tier = "pro"
    lic.is_active = True
    lic.expires_at = datetime.utcnow() + timedelta(days=180)
    lic.last_verified_at = datetime.utcnow() - timedelta(days=10)
    return lic


# ===== 4 License 实战 case =====


def test_01_license_verify_online_mode(mock_license_active):
    """case 1: License 在线校验 → online 模式 + valid=True."""
    from app.services.license_service import verify_license

    db = AsyncMock()
    # 模拟 db.execute 返 License
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = mock_license_active
    db.execute.return_value = result_mock

    import asyncio

    result = asyncio.run(
        verify_license(db, license_key="test_key", tenant_id="tenant_A", online=True)
    )
    assert result["valid"] is True
    assert result["mode"] == "online"
    assert result["tier"] == "pro"
    assert result["days_until_expiry"] >= 29


def test_02_license_expired_triggers_read_only(mock_license_expired):
    """case 2: License 过期 → read_only 模式 + valid=False."""
    from app.services.license_service import verify_license

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = mock_license_expired
    db.execute.return_value = result_mock

    import asyncio

    result = asyncio.run(
        verify_license(db, license_key="expired_key", tenant_id="tenant_B", online=True)
    )
    assert result["valid"] is False
    assert result["mode"] == "read_only"
    assert "expired" in result["reason"].lower()


def test_03_license_offline_grace_within_7_days(mock_license_offline_grace):
    """case 3: 离线 3 天 (宽限 7 天内) → offline_grace 模式 + valid=True."""
    from app.services.license_service import OFFLINE_GRACE_DAYS, verify_license

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = mock_license_offline_grace
    db.execute.return_value = result_mock

    import asyncio

    result = asyncio.run(
        verify_license(db, license_key="grace_key", tenant_id="tenant_C", online=False)
    )
    assert result["valid"] is True
    assert result["mode"] == "offline_grace"
    assert result["tier"] == "enterprise"
    # 宽限剩余 4 天
    assert "grace_days_remaining" in result
    assert result["grace_days_remaining"] == OFFLINE_GRACE_DAYS - 3


def test_04_license_offline_grace_exceeded_read_only(mock_license_grace_exceeded):
    """case 4: 离线超 7 天 → read_only 模式 + valid=False."""
    from app.services.license_service import verify_license

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = mock_license_grace_exceeded
    db.execute.return_value = result_mock

    import asyncio

    result = asyncio.run(
        verify_license(db, license_key="exceeded_key", tenant_id="tenant_D", online=False)
    )
    assert result["valid"] is False
    assert result["mode"] == "read_only"
    assert "grace" in result["reason"].lower() or "exceeded" in result["reason"].lower()
