"""v2.21 (2026-07-11) DriveView UX bug 修复回归测试.

背景:
  /api/v1/drive/files endpoint 在不传 folder_id 时强制 folder_id IS NULL filter
  (v2 PR3 修复时加的副作用). 导致 🌐 团队共享盘顶级 view + selectedFolderId=null
  时 FileGrid 显示空 (因为 root folder (NULL) 没 team PPT, 273 个 PPT 全在
  组会PPT folder 下的 23 个 sub folder).

修复:
  - service list_files 加 include_subfolders: bool = False 参数
  - True 时跳过 folder_id IS NULL filter (🌐 团队共享盘顶级用)
  - 默认 False 保持 v2 PR3 行为 (个人顶级 = folder_id IS NULL)
  - endpoint 加 include_subfolders query param, personal view 防御性忽略
  - 前端 useDriveFiles.fetchFiles 自动 (view=team/all + folder_id 未传) 传 true

测试矩阵:
  - view=personal + folder_id=None + include_subfolders=False (默认): 维持 v2 PR3
    只返 folder_id IS NULL 的 PPT (个人根目录)
  - view=personal + folder_id=None + include_subfolders=True (防御性忽略): 同上
  - view=team + folder_id=None + include_subfolders=False: 维持原行为 0 PPT (root NULL)
  - view=team + folder_id=None + include_subfolders=True (修复): 返所有 is_team_shared=true
  - view=team + folder_id=<id> + include_subfolders=True: 正常只看该 folder (不退化)
  - view=all + folder_id=None + include_subfolders=True: 返所有 PPT
"""
import asyncio
import pytest
import pytest_asyncio
import uuid as _uuid_lib
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import text

from app.config import settings
from app.models.member import Member
from app.models.folder import Folder
from app.models.knowledge import Knowledge
from app.services.drive_service import DriveService


# === 异步 pytest 配置 ===

@pytest_asyncio.fixture
async def db_session():
    """测试用真 DB + NullPool

    容器内运行时 settings.DATABASE_URL 已被 docker-compose 覆盖为
    postgresql://postgres:microbubble2026@db:5432/microbubble, 所以直接用就行.
    本地 (无 override) 会用 default postgresql://postgres:password@localhost:5432/microbubble,
    测试会自动 SKIP / 失败 — 这是预期的 (本地没 DB fixture).
    """
    url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(url, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            yield session, factory
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def alice_subfolders(db_session):
    """alice 1 个 folder_team_root, 下面 3 个 sub folder, 每个 2 PPT
       总共 root 1 PPT + sub folder 6 PPT = 7 PPT
    """
    session, factory = db_session
    u = _uuid_lib.uuid4().hex[:8]
    u_alice = f"alice_v221_{u}"
    f_root = f"alice_v221_root_{u}"
    f_sub1 = f"alice_v221_sub1_{u}"
    f_sub2 = f"alice_v221_sub2_{u}"
    f_sub3 = f"alice_v221_sub3_{u}"

    alice = Member(
        username=u_alice,
        name=f"Alice v2.21 {u}",
        password_hash="hash",
        role="member",
        grade="测试",
        is_active=True,
        # v2 PR6-P17 (2026-07-03): wechat_id NOT NULL 防 NULL 渗透
        # placeholder 格式避开 PR6-P14 UNIQUE 冲突
        wechat_id=f"__NULL_BACKFILL_alice_v221_{u}__",
    )
    session.add(alice)
    await session.commit()
    await session.refresh(alice)

    # root folder
    folder_root = Folder(
        name=f_root,
        owner_id=alice.id,
        visibility="team",
        path="/",
        depth=0,
    )
    session.add(folder_root)
    await session.commit()
    await session.refresh(folder_root)

    # 3 sub folder
    sub_folders = []
    for f_name in [f_sub1, f_sub2, f_sub3]:
        f = Folder(
            name=f_name,
            owner_id=alice.id,
            parent_id=folder_root.id,
            visibility="team",
            path=f"/{folder_root.id}/",
            depth=1,
        )
        session.add(f)
        sub_folders.append(f)
    await session.commit()
    for f in sub_folders:
        await session.refresh(f)

    # 1 PPT in root (folder_id=root.id)
    p_root = Knowledge(
        title=f"v221_root_ppt_{u}",
        content=f"v221 root content {u}",  # Knowledge.content NOT NULL
        file_path=f"v221/root/{u}.txt",
        file_name=f"v221_root_{u}.txt",
        file_type=".txt",
        file_size=100,
        created_by=alice.id,  # Knowledge 用 created_by, 不是 owner_id
        storage_mode="drive",
        visibility="team",
        folder_id=folder_root.id,
        is_team_shared=True,
    )
    session.add(p_root)

    # 2 PPT per sub folder (6 total)
    sub_files = []
    for i, f in enumerate(sub_folders):
        for j in range(2):
            p = Knowledge(
                title=f"v221_sub{i+1}_ppt{j}_{u}",
                content=f"v221 sub{i+1} content{j} {u}",  # Knowledge.content NOT NULL
                file_path=f"v221/sub{i+1}/{u}_{j}.txt",
                file_name=f"v221_sub{i+1}_{j}_{u}.txt",
                file_type=".txt",
                file_size=100,
                created_by=alice.id,  # Knowledge 用 created_by, 不是 owner_id
                storage_mode="drive",
                visibility="team",
                folder_id=f.id,
                is_team_shared=True,
            )
            session.add(p)
            sub_files.append(p)
    await session.commit()

    yield {
        "alice": alice,
        "folder_root": folder_root,
        "sub_folders": sub_folders,  # 3 个
        "root_ppt_id": p_root.id,
        "sub_ppt_ids": [p.id for p in sub_files],  # 6 个
        "u": u,
        "factory": factory,
    }

    # cleanup
    try:
        await session.execute(text("SET session_replication_role = 'replica'"))
        from sqlalchemy import delete as _del
        all_ppt_ids = [p_root.id] + [p.id for p in sub_files]
        await session.execute(_del(Knowledge).where(Knowledge.id.in_(all_ppt_ids)))
        await session.execute(_del(Folder).where(Folder.id.in_([folder_root.id] + [f.id for f in sub_folders])))
        await session.execute(_del(Member).where(Member.id == alice.id))
        await session.execute(text("RESET session_replication_role"))
        await session.commit()
    except Exception:
        try:
            await session.rollback()
        except Exception:
            pass


# === 实际测试 ===

@pytest.mark.asyncio
async def test_v221_personal_view_default_returns_only_root_ppt(alice_subfolders):
    """v2 PR3 行为保持: view=personal + folder_id=None + include_subfolders 默认 False
       应只返 folder_id IS NULL 的 PPT (个人根目录). 我们 PPT 都在 folder 里,
       所以应 0 个 (没有 folder_id IS NULL 的 PPT).

       验证修复**不破坏** v2 PR3 personal view 语义.
    """
    factory = alice_subfolders["factory"]
    alice = alice_subfolders["alice"]

    async with factory() as session:
        svc = DriveService(session)
        # v2 PR3 默认行为: include_subfolders 不传 = False
        items, total = await svc.list_files(
            current_user_id=alice.id,
            folder_id=None,
            is_team_shared=False,  # personal view
        )
        # 我们的测试 PPT 都在 folder 里, 没有 folder_id IS NULL 的 PPT
        # 所以 personal view 应返 0
        assert total == 0, f"personal view 应 0 PPT (v2 PR3 folder_id IS NULL), 实际 {total}"
        assert len(items) == 0


@pytest.mark.asyncio
async def test_v221_personal_view_include_subfolders_ignored(alice_subfolders):
    """防御性: view=personal + include_subfolders=True 应被 service 端忽略
       (service 不区分, 但 endpoint 防御性忽略).

       service 层实际行为: include_subfolders=True 会跳过 folder_id IS NULL filter,
       列出所有 personal PPT. endpoint 已经在 view=personal 时强制 include_subfolders=False.

       这里测试 service 层: personal + include_subfolders=True 应返回所有 personal PPT
       (即所有 is_team_shared=false + visibility 满足的 PPT, 不限 folder_id).

       但我们的 fixture PPT 都是 is_team_shared=true (team view PPT), 所以 personal view
       应该 0 个, 不管 include_subfolders.
    """
    factory = alice_subfolders["factory"]
    alice = alice_subfolders["alice"]

    async with factory() as session:
        svc = DriveService(session)
        # 即使 include_subfolders=True, is_team_shared=False 仍过滤掉我们的 team PPT
        items, total = await svc.list_files(
            current_user_id=alice.id,
            folder_id=None,
            is_team_shared=False,
            include_subfolders=True,
        )
        assert total == 0, f"personal view + include_subfolders=True 应仍 0 (所有 PPT 都是 team), 实际 {total}"


@pytest.mark.asyncio
async def test_v221_team_view_default_returns_zero(alice_subfolders):
    """v2 PR3 默认: view=team + folder_id=None + include_subfolders=False
       应只返 folder_id IS NULL 的 team PPT. 我们没有 NULL 的 team PPT,
       所以 0 个 (修复前的 bug 状态).
    """
    factory = alice_subfolders["factory"]
    alice = alice_subfolders["alice"]

    async with factory() as session:
        svc = DriveService(session)
        items, total = await svc.list_files(
            current_user_id=alice.id,
            folder_id=None,
            is_team_shared=True,  # team view
        )
        assert total == 0, f"team view 默认应 0 (folder_id IS NULL filter), 实际 {total}"


@pytest.mark.asyncio
async def test_v221_team_view_include_subfolders_returns_all_team_ppts(alice_subfolders):
    """v2.21 修复: view=team + folder_id=None + include_subfolders=True
       应跳过 folder_id IS NULL filter, 列出**所有** is_team_shared=true 的 PPT
       (fixture 创建的 7 PPT 都应被列出).

       注意: 生产 DB 已有其他团队 PPT (组会 275), 所以 total 至少 282.
       验证 fixture 创建的 7 PPT 都齐.
    """
    factory = alice_subfolders["factory"]
    alice = alice_subfolders["alice"]
    u = alice_subfolders["u"]
    prefix = f"v221_"

    async with factory() as session:
        svc = DriveService(session)
        items, total = await svc.list_files(
            current_user_id=alice.id,
            folder_id=None,
            is_team_shared=True,  # team view
            include_subfolders=True,  # v2.21 新参数
        )
        # 关键断言: fixture 创建的 7 PPT 全在结果里
        fixture_titles = {x.title for x in items if x.title.startswith(prefix)}
        assert f"v221_root_ppt_{u}" in fixture_titles, "fixture root PPT 应在 team view 结果里"
        sub_titles = {t for t in fixture_titles if t.startswith("v221_sub")}
        assert len(sub_titles) == 6, f"fixture 应有 6 个 sub PPT, 实际 {len(sub_titles)}"
        # 验证 fixture root PPT 的 folder_id 是 folder_root.id
        root_ppt = next(x for x in items if x.title == f"v221_root_ppt_{u}")
        assert root_ppt.folder_id == alice_subfolders["folder_root"].id, \
            f"root PPT 应在 folder_root 里, 实际 folder_id={root_ppt.folder_id}"
        # 验证 fixture sub PPT 的 folder_id 是对应 sub folder id
        for sf in alice_subfolders["sub_folders"]:
            sub_ppts = [x for x in items
                        if x.title.startswith(f"v221_sub{sub_folders_index(alice_subfolders, sf)}_")
                        and x.title.endswith(f"_{u}")]
            for p in sub_ppts:
                assert p.folder_id == sf.id, f"sub PPT 应在对应 sub folder {sf.id}, 实际 {p.folder_id}"
        # 总数 >= 282 (fixture 7 + 生产 275)
        assert total >= 282, f"team view + include_subfolders=True 应至少 282 PPT (7 fixture + 275 生产), 实际 {total}"


def sub_folders_index(alice_subfolders, sub_folder):
    """helper: 返回 sub_folder 在 sub_folders list 里的 1-based index"""
    return alice_subfolders["sub_folders"].index(sub_folder) + 1


@pytest.mark.asyncio
async def test_v221_team_view_with_folder_id_unaffected(alice_subfolders):
    """include_subfolders=True + folder_id=<id> 应**不**退化
       (仍只返该 folder 的 PPT, 不扩散到其他 sub folder).
    """
    factory = alice_subfolders["factory"]
    alice = alice_subfolders["alice"]
    sub1 = alice_subfolders["sub_folders"][0]  # 第 1 个 sub folder

    async with factory() as session:
        svc = DriveService(session)
        items, total = await svc.list_files(
            current_user_id=alice.id,
            folder_id=sub1.id,  # 显式指定 folder
            is_team_shared=True,
            include_subfolders=True,  # 即便传 True 也不退化
        )
        # 应只看 sub1 的 PPT. fixture 创建了 2 个 sub1 PPT, 生产 DB 可能有其他
        # PPT 在 sub1 里 (历史数据). 验证 fixture PPT 都在且 folder_id 正确.
        u = alice_subfolders["u"]
        fixture_in_sub1 = [x for x in items if x.title.startswith("v221_sub1_") and x.title.endswith(f"_{u}")]
        assert len(fixture_in_sub1) == 2, f"fixture 应在 sub1 创建 2 PPT, 实际 {len(fixture_in_sub1)}"
        for p in fixture_in_sub1:
            assert p.folder_id == sub1.id
        # 验证 total >= 2 (有其他历史 PPT 在 sub1 也算)
        assert total >= 2, f"folder_id=sub1 应至少 2 PPT (fixture), 实际 {total}"


@pytest.mark.asyncio
async def test_v221_all_view_include_subfolders_returns_everything(alice_subfolders):
    """view=all + include_subfolders=True 应返所有 PPT (不过滤 view).

       验证 fixture 的 7 PPT 全在结果里.
    """
    factory = alice_subfolders["factory"]
    alice = alice_subfolders["alice"]
    u = alice_subfolders["u"]
    prefix = "v221_"

    async with factory() as session:
        svc = DriveService(session)
        items, total = await svc.list_files(
            current_user_id=alice.id,
            folder_id=None,
            is_team_shared=None,  # all view (不过滤 is_team_shared)
            include_subfolders=True,
        )
        # 验证 fixture 7 PPT 全在结果里
        fixture_titles = {x.title for x in items if x.title.startswith(prefix)}
        assert f"v221_root_ppt_{u}" in fixture_titles
        sub_titles = {t for t in fixture_titles if t.startswith("v221_sub")}
        assert len(sub_titles) == 6, f"fixture 应有 6 个 sub PPT, 实际 {len(sub_titles)}"
        # all view 应返很多 PPT (生产 DB 团队 PPT + personal PPT), 至少 282+
        assert total >= 282, f"all view 应至少 282 PPT, 实际 {total}"


@pytest.mark.asyncio
async def test_v221_include_subfolders_default_is_false(alice_subfolders):
    """默认参数 include_subfolders=False 必须保持 (向后兼容, v2 PR3 行为)."""
    factory = alice_subfolders["factory"]
    alice = alice_subfolders["alice"]

    async with factory() as session:
        svc = DriveService(session)
        # 不传 include_subfolders
        items_default, total_default = await svc.list_files(
            current_user_id=alice.id,
            folder_id=None,
            is_team_shared=True,
        )
        # 显式 False 应与默认行为一致
        items_explicit, total_explicit = await svc.list_files(
            current_user_id=alice.id,
            folder_id=None,
            is_team_shared=True,
            include_subfolders=False,
        )
        assert total_default == total_explicit == 0, \
            f"默认 vs include_subfolders=False 应一致 (都 0): {total_default} vs {total_explicit}"