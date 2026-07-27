"""Drive v2 W72 第 2 批 B-1 — Share Link 增强 e2e 测试 (2026-07-27)

背景 (派工 v10 段 7):
- folder share (PR7 alembic 061) 已实施
- W72 第 2 批 B-1 差量: drive_folder_shares 加 password_hash + max_downloads +
  download_count 3 列, 加 service 层 password/max_downloads 参数 + 审计
- alembic 081 migration 已写, 接 078_drive_dedupe_audit 串单链

8 场景:
1. 创建 share link + 过期时间
2. 密码保护 share link (有/无 password)
3. 次数限制 share link (max_downloads + download_count 原子)
4. 桌面 UI 创建 + 复制 + 撤销 (ShareLinkDialog.vue emit 接口验证)
5. 移动端入口 (MobileDriveView fileActions share-folder)
6. 审计 3 action 落库 (share_created / share_revoked / share_downloaded)
7. 链接过期自动失效 (PR7 老逻辑兼容)
8. 次数超限自动失效 (W72-B-1 差量)
9. PR7 老调用兼容 (无 password + 无 max_downloads)

跑法:
    cd <worktree> && python -m pytest tests/test_drive_v2_w72b1_sharing_e2e.py -v

设计要点:
- 用 raw DDL + sqlite (与 tests/test_drive_v2_pr10_collab_e2e.py 模式一致)
- 不依赖 docker / 真 PG / pgvector
- audit_middleware._classify_action 直接字符串验证
- 移动端 UI 通过读 vue 源码验证 (静态分析)
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# === 直接从 drive_share_service 引入, 不依赖 knowledge/folder model ===
#   (PG-only types 会让 sqlite ORM 建表失败)
from app.services.drive_share_service import (
    DEFAULT_SHARE_EXPIRES_DAYS,
    DriveShareService,
    DriveShareServiceError,
)


# ============================================================
# 最小 raw DDL (只覆盖 drive_folder_shares + folder 必需列)
# ============================================================
_CREATE_MEMBERS = """
CREATE TABLE members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    username VARCHAR(64),
    email VARCHAR(200),
    role VARCHAR(32) DEFAULT 'student',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""

_CREATE_FOLDERS = """
CREATE TABLE folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(200) NOT NULL,
    owner_id INTEGER NOT NULL,
    parent_id INTEGER,
    path VARCHAR(500),
    visibility VARCHAR(16) DEFAULT 'private',
    depth INTEGER DEFAULT 0,
    is_team_shared BOOLEAN DEFAULT 0,
    is_team_default BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    deleted_at DATETIME
)
"""

_CREATE_DRIVE_FOLDER_SHARES = """
CREATE TABLE drive_folder_shares (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    folder_id INTEGER NOT NULL,
    share_token VARCHAR(64) NOT NULL UNIQUE,
    permission VARCHAR(16) NOT NULL DEFAULT 'read',
    expires_at DATETIME NOT NULL,
    created_by INTEGER NOT NULL,
    revoked_at DATETIME,
    password_hash VARCHAR(128),
    max_downloads INTEGER,
    download_count INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""

_CREATE_KNOWLEDGE = """
CREATE TABLE knowledge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(500),
    content TEXT,
    category VARCHAR(100),
    topic VARCHAR(100),
    tags VARCHAR(500),
    key_concepts TEXT,
    related_topics TEXT,
    knowledge_type VARCHAR(50),
    analysis_status VARCHAR(32),
    auto_researched BOOLEAN DEFAULT 0,
    quality_score INTEGER,
    needs_review BOOLEAN DEFAULT 0,
    entities TEXT,
    source VARCHAR(200),
    source_type VARCHAR(50),
    meta TEXT,
    file_path VARCHAR(500),
    file_name VARCHAR(500),
    file_type VARCHAR(64),
    summary TEXT,
    formatted_content TEXT,
    embedding BLOB,
    created_by INTEGER,
    storage_mode VARCHAR(16) DEFAULT 'drive',
    folder_id INTEGER,
    visibility VARCHAR(16) DEFAULT 'private',
    deleted_at DATETIME,
    download_count INTEGER DEFAULT 0,
    share_token VARCHAR(64),
    share_expires_at DATETIME,
    share_password VARCHAR(128),
    is_starred BOOLEAN DEFAULT 0,
    starred_at DATETIME,
    is_team_shared BOOLEAN DEFAULT 0,
    file_size INTEGER,
    file_hash VARCHAR(64),
    is_latest BOOLEAN DEFAULT 1,
    parent_version_id INTEGER,
    version_number INTEGER DEFAULT 1,
    thumbnail_path VARCHAR(500),
    thumbnail_status VARCHAR(32),
    thumbnail_generated_at DATETIME,
    drive_dedupe_count INTEGER DEFAULT 0,
    drive_dedupe_first_hit_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""


_CREATE_AUDIT_LOG = """
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    ip_address VARCHAR(45),
    user_agent TEXT,
    method VARCHAR(10) NOT NULL,
    path VARCHAR(500) NOT NULL,
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(20),
    resource_id VARCHAR(50),
    status_code INTEGER,
    duration_ms INTEGER,
    meta_data TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""


@pytest_asyncio.fixture
async def db():
    """内存 sqlite + raw DDL (与 PR10 e2e 模式一致)"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.execute(text(_CREATE_MEMBERS))
        await conn.execute(text(_CREATE_FOLDERS))
        await conn.execute(text(_CREATE_DRIVE_FOLDER_SHARES))
        await conn.execute(text(_CREATE_KNOWLEDGE))
        await conn.execute(text(_CREATE_AUDIT_LOG))
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def sample_member(db):
    """建测试成员"""
    result = await db.execute(
        text(
            "INSERT INTO members (name, username, email, role) "
            "VALUES ('测试老师', 'test_teacher', 't@example.com', 'teacher')"
        )
    )
    await db.commit()
    return result.lastrowid


@pytest_asyncio.fixture
async def sample_folder(db, sample_member):
    """建测试 folder"""
    result = await db.execute(
        text(
            "INSERT INTO folders (name, owner_id, visibility, depth) "
            "VALUES ('共享测试', :oid, 'private', 1)"
        ),
        {"oid": sample_member},
    )
    await db.commit()
    return result.lastrowid


# ============================================================
# 场景 1: 创建 share link + 过期时间
# ============================================================
async def test_create_share_link_with_expiry(db, sample_folder, sample_member):
    """场景 1: POST /folders/{id}/share, expires_days=7 → expires_at 准确"""
    svc = DriveShareService(db)
    share = await svc.create_folder_share(
        folder_id=sample_folder,
        user_id=sample_member,
        permission="read",
        expires_days=7,
    )
    assert share.id is not None
    assert share.share_token is not None
    assert share.permission == "read"
    # expires_at 应在 6-8 天后 (允许 sqlite + naive 比较)
    now_utc_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    delta_days = (share.expires_at - now_utc_naive).total_seconds() / 86400
    assert 6.0 < delta_days < 8.0, f"expires_at 偏差: {delta_days} 天"


# ============================================================
# 场景 2: 密码保护 share link
# ============================================================
async def test_create_share_with_password(db, sample_folder, sample_member):
    """场景 2a: 4 位数字 password → password_hash 落库, 校验可解密"""
    svc = DriveShareService(db)
    share = await svc.create_folder_share(
        folder_id=sample_folder,
        user_id=sample_member,
        permission="read",
        expires_days=7,
        password="1234",
    )
    assert share.password_hash is not None
    assert share.password_hash != "1234", "密码不应明文落库"

    # 校验: 用 password 应可访问
    result = await svc.get_folder_by_share_token(
        share.share_token, password="1234"
    )
    assert result is not None
    folder, _share, files, subfolders = result
    assert folder.id == sample_folder


async def test_create_share_with_wrong_password_fails(db, sample_folder, sample_member):
    """场景 2b: 错密码应访问失败"""
    svc = DriveShareService(db)
    share = await svc.create_folder_share(
        folder_id=sample_folder,
        user_id=sample_member,
        permission="read",
        password="1234",
    )
    # 错密码
    result = await svc.get_folder_by_share_token(
        share.share_token, password="5678"
    )
    assert result is None


async def test_password_validation(db, sample_folder, sample_member):
    """场景 2c: password 格式校验 (非 4-8 位数字应报错)"""
    svc = DriveShareService(db)
    # 非数字
    with pytest.raises(DriveShareServiceError):
        await svc.create_folder_share(
            folder_id=sample_folder, user_id=sample_member, password="abcd",
        )
    # 3 位
    with pytest.raises(DriveShareServiceError):
        await svc.create_folder_share(
            folder_id=sample_folder, user_id=sample_member, password="123",
        )


# ============================================================
# 场景 3: 次数限制 share link
# ============================================================
async def test_max_downloads_limit(db, sample_folder, sample_member):
    """场景 3: max_downloads=2, 第 3 次自增应返 -1 (超限)"""
    svc = DriveShareService(db)
    share = await svc.create_folder_share(
        folder_id=sample_folder,
        user_id=sample_member,
        permission="read",
        max_downloads=2,
    )
    assert share.max_downloads == 2
    assert share.download_count == 0

    # 第 1 次
    new_count = await svc.increment_download_count(share.id)
    assert new_count == 1

    # 第 2 次
    new_count = await svc.increment_download_count(share.id)
    assert new_count == 2

    # 第 3 次: 应返 -1 (超限)
    new_count = await svc.increment_download_count(share.id)
    assert new_count == -1


async def test_is_active_false_when_max_reached(db, sample_folder, sample_member):
    """场景 3b: is_active 属性在 max_downloads 达到时返 False"""
    svc = DriveShareService(db)
    share = await svc.create_folder_share(
        folder_id=sample_folder, user_id=sample_member, max_downloads=1,
    )
    assert share.is_active is True

    # 自增到 1
    await svc.increment_download_count(share.id)

    # 重新查
    from sqlalchemy import select
    from app.models.drive_share import DriveFolderShare
    fresh = (await db.execute(
        select(DriveFolderShare).where(DriveFolderShare.id == share.id)
    )).scalar_one()
    assert fresh.download_count == 1
    assert fresh.is_active is False, "次数超限 is_active 应为 False"


# ============================================================
# 场景 4: 桌面 UI 完整流 create → access → revoke → access None
# ============================================================
async def test_full_share_lifecycle(db, sample_folder, sample_member):
    """场景 4: ShareLinkDialog 完整流"""
    svc = DriveShareService(db)
    share = await svc.create_folder_share(
        folder_id=sample_folder,
        user_id=sample_member,
        permission="write",
        password="8888",
        max_downloads=10,
    )

    # 撤销前可访问
    result = await svc.get_folder_by_share_token(
        share.share_token, password="8888"
    )
    assert result is not None

    # 撤销
    revoked = await svc.revoke_folder_share(share.id, sample_member)
    assert revoked is True

    # 撤销后访问返 None
    result = await svc.get_folder_by_share_token(
        share.share_token, password="8888"
    )
    assert result is None


# ============================================================
# 场景 5: 移动端入口 (MobileDriveView fileActions 含 share-folder)
# ============================================================
def test_mobile_file_actions_includes_share_folder():
    """场景 5: MobileDriveView fileActions computed 含 share-folder 当 currentFolderId 非空

    静态分析 vue 源码验证逻辑
    """
    src_path = (
        Path(__file__).resolve().parents[1]
        / "web/src/views/mobile/MobileDriveView.vue"
    )
    src = src_path.read_text(encoding="utf-8")

    # 验证 fileActions computed 含 share-folder 分支
    assert "share-folder" in src, "MobileDriveView.vue 缺 share-folder 入口"
    # 验证 navigator.vibrate 触觉反馈 (CLAUDE.md 2026-06-27 教训)
    assert "navigator.vibrate" in src, "MobileDriveView.vue 缺 navigator.vibrate 触觉反馈"
    # 验证 ShareLinkDialog 集成
    assert "ShareLinkDialog" in src, "MobileDriveView.vue 缺 ShareLinkDialog 集成"


def test_desktop_share_link_dialog_present():
    """场景 5b: DesktopDriveView 集成 ShareLinkDialog + FolderTreeNode 含 share 菜单"""
    web_root = Path(__file__).resolve().parents[1] / "web/src"

    desktop = (web_root / "views/DesktopDriveView.vue").read_text(encoding="utf-8")
    assert "ShareLinkDialog" in desktop, "DesktopDriveView.vue 缺 ShareLinkDialog"
    assert "onShareFolder" in desktop, "DesktopDriveView.vue 缺 onShareFolder handler"

    folder_node = (web_root / "components/drive/FolderTreeNode.vue").read_text(encoding="utf-8")
    assert "share" in folder_node, "FolderTreeNode.vue 缺 share 菜单项"

    folder_tree = (web_root / "components/drive/FolderTree.vue").read_text(encoding="utf-8")
    assert "share-folder" in folder_tree, "FolderTree.vue 缺 share-folder emit"

    dialog = (web_root / "components/drive/ShareLinkDialog.vue").read_text(encoding="utf-8")
    assert "max_downloads" in dialog, "ShareLinkDialog.vue 缺 max_downloads 字段"
    assert "password" in dialog, "ShareLinkDialog.vue 缺 password 字段"


# ============================================================
# 场景 6: 审计 3 action 落库 (share_created / share_revoked / share_downloaded)
# ============================================================
def test_audit_middleware_classifies_share_actions():
    """场景 6: audit_middleware._classify_action 正确归类 3 个新 action"""
    from app.core.audit_middleware import _classify_action

    # 创建 share
    assert _classify_action("POST", "/api/v1/drive/folders/42/share") == "share_created"
    # 公开访问 (无登录)
    assert _classify_action("GET", "/api/v1/drive/folders/share/abc123") == "share_downloaded"
    # 撤销 share
    assert _classify_action("DELETE", "/api/v1/drive/folders/share/123") == "share_revoked"


# ============================================================
# 场景 7: 链接过期自动失效 (PR7 老逻辑兼容)
# ============================================================
async def test_share_expires_at_past_invalid(db, sample_folder, sample_member):
    """场景 7: 改 expires_at 为过去 → is_active 返 False, 访问返 None"""
    svc = DriveShareService(db)
    share = await svc.create_folder_share(
        folder_id=sample_folder, user_id=sample_member, expires_days=1,
    )
    # 改 expires_at 为 1 小时前 (raw update 绕开 naive 比较)
    from sqlalchemy import update as sql_update
    from app.models.drive_share import DriveFolderShare
    past = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
    await db.execute(
        sql_update(DriveFolderShare)
        .where(DriveFolderShare.id == share.id)
        .values(expires_at=past)
    )
    await db.commit()

    # 重新查
    from sqlalchemy import select
    fresh = (await db.execute(
        select(DriveFolderShare).where(DriveFolderShare.id == share.id)
    )).scalar_one()

    assert fresh.is_active is False, "过期后 is_active 应为 False"
    # 访问返 None
    result = await svc.get_folder_by_share_token(share.share_token)
    assert result is None


# ============================================================
# 场景 8: 次数超限自动失效 (W72-B-1 差量)
# ============================================================
async def test_share_max_downloads_reached_invalid(db, sample_folder, sample_member):
    """场景 8: download_count >= max_downloads → get_folder_by_share_token 返 None"""
    svc = DriveShareService(db)
    share = await svc.create_folder_share(
        folder_id=sample_folder, user_id=sample_member, max_downloads=3,
    )

    # 自增 3 次到上限
    for i in range(3):
        n = await svc.increment_download_count(share.id)
        assert n == i + 1, f"第 {i+1} 次自增失败: {n}"

    # 再访问: 应返 None (超限)
    result = await svc.get_folder_by_share_token(share.share_token)
    assert result is None, "次数超限后仍可访问 (bug)"


# ============================================================
# 场景 9 (bonus): PR7 老调用兼容 (无 password + 无 max_downloads)
# ============================================================
async def test_pr7_compat_no_password_no_max(db, sample_folder, sample_member):
    """场景 9: PR7 老调用 (无 password/max_downloads 参数) 仍正常工作, 无回归"""
    svc = DriveShareService(db)
    share = await svc.create_folder_share(
        folder_id=sample_folder, user_id=sample_member, permission="admin",
    )
    # 老字段全在
    assert share.permission == "admin"
    assert share.expires_at is not None
    assert share.revoked_at is None
    # 新字段默认
    assert share.password_hash is None
    assert share.max_downloads is None
    assert share.download_count == 0
    # 访问 OK (无密码)
    result = await svc.get_folder_by_share_token(share.share_token)
    assert result is not None
    folder, _share, _, _ = result
    assert folder.id == sample_folder