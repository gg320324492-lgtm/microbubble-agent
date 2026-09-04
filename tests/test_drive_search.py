"""批次① B6 — 网盘文件名/标题搜索测试 (2026-09-05)

覆盖: 中缀命中 / 大小写不敏感 / % _ 通配符按字面量转义 / 跨文件夹命中 /
空 search 行为回归锁 (与老版完全一致)。

DB fixture: conftest db (TEST_DATABASE_URL)。索引性能 (trgm GIN) 由迁移 134 提供,
功能正确性不依赖索引, 本测试只锁 SQL 谓词语义。
"""
import uuid as _uuid

import pytest
import pytest_asyncio

from app.models.knowledge import Knowledge
from app.models.member import Member
from app.services.drive_service import DriveService


@pytest_asyncio.fixture
async def search_env(db):
    u = _uuid.uuid4().hex[:8]
    m = Member(
        username=f"sh_{u}", name="searcher", password_hash="h",
        role="member", grade="测试", is_active=True, wechat_id=f"wx_sh_{u}",
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)

    def mk(file_name, *, folder_id=None, title=None):
        k = Knowledge(
            content="", title=title or f"title_{file_name}",
            storage_mode="drive", file_name=file_name,
            file_path=f"drive-test/{file_name}",
            folder_id=folder_id, created_by=m.id, visibility="team",
        )
        db.add(k)
        return k

    rows = [
        mk("实验报告 final.pdf"),                    # 中文 + 空格
        mk("100%纯文本.txt"),                        # 字面 %
        mk("第100章.docx"),                          # 含 "100" 但无 "%" — 未转义会误命中
        mk("under_score.xlsx"),                      # 字面 _
        mk("Zscore.pptx"),                           # 含 "Xscore" 形态 — "_" 未转义会误命中
        mk("Alpha.pdf"),                             # 大小写测试
        mk("嵌套夹文件.md", folder_id=None),
    ]
    await db.commit()
    ids = [k.id for k in rows]
    return {"db": db, "user": m, "svc": DriveService(db), "ids": ids, "names": [k.file_name for k in rows]}


async def _names(items):
    return sorted(k.file_name for k in items)


async def _search(svc, user, term, **kw):
    items, total = await svc.list_files(
        current_user_id=user.id,
        folder_id=kw.get("folder_id"),
        include_subfolders=kw.get("include_subfolders", True),  # 模拟搜索态全盘 (endpoint 强制)
        search=term,
    )
    return items, total


@pytest.mark.asyncio
async def test_infix_chinese_search(search_env):
    """中缀 + 中文: '报告' 只命中 实验报告 final.pdf"""
    items, total = await _search(
        search_env["svc"], search_env["user"], "报告",
    )
    assert total == 1
    assert await _names(items) == ["实验报告 final.pdf"]


@pytest.mark.asyncio
async def test_case_insensitive(search_env):
    """'alpha' 小写命中 'Alpha.pdf' (ilike)"""
    items, total = await _search(search_env["svc"], search_env["user"], "alpha")
    assert total == 1
    assert await _names(items) == ["Alpha.pdf"]


@pytest.mark.asyncio
async def test_percent_literal_escape(search_env):
    """'100%' 按字面匹配: 只命中 100%纯文本.txt, 不命中 第100章.docx

    未转义时 pattern '%100%%' = 含 '100' 即中 → 第100章 误命中 (回归锁)。
    """
    items, total = await _search(search_env["svc"], search_env["user"], "100%")
    assert total == 1
    assert await _names(items) == ["100%纯文本.txt"]


@pytest.mark.asyncio
async def test_underscore_literal_escape(search_env):
    """'_score' 字面下划线: 只命中 under_score.xlsx, 不命中 Zscore.pptx

    未转义时 '_score' 的 _ = 任意单字符 → 'Zscore' 误命中 (回归锁)。
    """
    items, total = await _search(search_env["svc"], search_env["user"], "_score")
    assert total == 1
    assert await _names(items) == ["under_score.xlsx"]


@pytest.mark.asyncio
async def test_title_searched_too(search_env):
    """title 也在搜索域: 唯一 title 片段命中"""
    items, total = await _search(search_env["svc"], search_env["user"], "title_实验报告")
    assert total == 1
    assert await _names(items) == ["实验报告 final.pdf"]


@pytest.mark.asyncio
async def test_cross_folder_hit(search_env):
    """夹内文件在搜索态 (include_subfolders=True → 无 folder filter) 可被全盘命中"""
    db, user, svc = search_env["db"], search_env["user"], search_env["svc"]
    from app.models.folder import Folder
    from app.services.folder_service import FolderService
    folder = await FolderService(db).create_folder(name="组会归档", owner_id=user.id, visibility="team")
    k = Knowledge(
        content="", title="t_in_folder", storage_mode="drive", file_name="夹内深档.pptx",
        file_path="drive-test/in_folder", folder_id=folder.id,
        created_by=user.id, visibility="team",
    )
    db.add(k)
    await db.commit()
    items, total = await _search(svc, user, "深档")
    assert total == 1
    assert items[0].file_name == "夹内深档.pptx"


@pytest.mark.asyncio
async def test_folder_name_map_helper(search_env):
    """endpoint 层配套: _folder_name_map 批量 {folder_id: name}, _to_item 透出
    folder_name (搜索"所属文件夹"列 / 三栏工作台"位置"列消费)。"""
    db, user, svc = search_env["db"], search_env["user"], search_env["svc"]
    from app.api.v1.drive_files import _folder_name_map, _to_item
    from app.models.folder import Folder
    from app.services.folder_service import FolderService

    folder = await FolderService(db).create_folder(
        name="归档甲", owner_id=user.id, visibility="team")
    k = Knowledge(
        content="", title="t_fmap", storage_mode="drive", file_name="位置列.pdf",
        file_path="drive-test/fmap", folder_id=folder.id,
        created_by=user.id, visibility="team",
    )
    db.add(k)
    await db.commit()

    items, total = await _search(svc, user, "位置列")
    assert total == 1
    fmap = await _folder_name_map(db, items)
    assert fmap == {folder.id: "归档甲"}
    item = _to_item(items[0], folder_map=fmap)
    assert item.folder_name == "归档甲"

    # 顶级文件 (folder_id None) → folder_name None, 不误伤
    top_items, _ = await _search(svc, user, "实验报告")
    top = _to_item(top_items[0], folder_map=fmap)
    assert top.folder_id is None and top.folder_name is None

    # 空页 → 不发 SQL (map 为空 dict)
    assert await _folder_name_map(db, []) == {}


@pytest.mark.asyncio
async def test_empty_search_regression_lock(search_env):
    """search=None / 空白 → 行为与老版完全一致 (返回全部, 无搜索谓词)"""
    svc, user = search_env["svc"], search_env["user"]
    all_items, all_total = await svc.list_files(
        current_user_id=user.id, folder_id=None, include_subfolders=True,
    )
    none_items, none_total = await svc.list_files(
        current_user_id=user.id, folder_id=None, include_subfolders=True, search=None,
    )
    blank_items, blank_total = await svc.list_files(
        current_user_id=user.id, folder_id=None, include_subfolders=True, search="   ",
    )
    assert {k.id for k in none_items} == {k.id for k in all_items}
    assert none_total == blank_total == all_total
