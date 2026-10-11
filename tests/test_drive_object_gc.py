"""批次① B2 + N1 — MinIO 版本对象统一回收测试 (2026-09-05)

断言核心 = "永久删一条带 2 个历史版本的文件时, delete_file 必须收到 3 个 key
(当前对象 + 2 个版本对象)"。

N1 回归锁 (cleanup 路径): clean_old_drive_files 旧实现先 DELETE 后 SELECT →
MinIO key 恒空。若顺序回退, 本测试 mock 的 delete_file 收不到 key 即红。

打点 (类 20.181): purge_minio_keys 走调用时 inline import, 因此
patch("app.services.file_service.file_service") 对整个 service 链生效 —
与重构前 drive_cleanup_service 的旧打点完全一致, 老测试 patch 不失效。

DB fixture: conftest db (TEST_DATABASE_URL)。
"""
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.drive_file_star import DriveFileStar  # noqa: F401  (确保 create_all 覆盖 134 表)
from app.models.drive_file_version import DriveFileVersion
from app.models.knowledge import Knowledge
from app.models.knowledge_multimodal import KnowledgeImage  # noqa: F401  (同上, 覆盖 knowledge_images)
from app.models.member import Member
from app.services.drive_object_gc import collect_object_keys, purge_minio_keys


def _naive_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest_asyncio.fixture
async def gc_env(db):
    u = _uuid.uuid4().hex[:8]
    m = Member(
        username=f"gc_{u}", name="gc", password_hash="h", role="member",
        grade="测试", is_active=True    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return {"db": db, "m": m}


async def _mk_trashed_drive_file(db, owner, name, *, deleted_at, versions=0):
    k = Knowledge(
        content="", title=name, storage_mode="drive", file_name=name,
        file_path=f"drive-test/{name}", created_by=owner.id,
        visibility="team", deleted_at=deleted_at,
    )
    db.add(k)
    await db.commit()
    await db.refresh(k)
    keys = []
    for i in range(versions):
        vk = f"drive-test/{name}.v{i}"
        keys.append(vk)
        db.add(DriveFileVersion(
            file_id=k.id, version_number=i + 1, minio_object_key=vk,
            size=10, uploader_id=owner.id, is_current=0,
        ))
    await db.commit()
    return k, keys


# ---------------------------------------------------------------------------
# collect_object_keys 单元
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_collect_keys_union_dedup(gc_env):
    db, m = gc_env["db"], gc_env["m"]
    k, keys = await _mk_trashed_drive_file(
        db, m, "union.pdf", deleted_at=_naive_now() - timedelta(days=40), versions=2,
    )
    result = await collect_object_keys(db, [k])
    assert k.file_path in result
    assert set(result) == {k.file_path} | set(keys)
    assert len(result) == len(set(result)), "去重"
    assert await collect_object_keys(db, []) == []


# ---------------------------------------------------------------------------
# (a) permanent_delete: 当前对象 + 2 个版本对象 = 3 个 key
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_permanent_delete_purges_current_and_versions(gc_env):
    from app.services.drive_service import DriveService
    db, m = gc_env["db"], gc_env["m"]
    k, vkeys = await _mk_trashed_drive_file(
        db, m, "three_objects.pdf", deleted_at=_naive_now(), versions=2,
    )
    expected = {k.file_path} | set(vkeys)

    mock_fs = MagicMock()
    with patch("app.services.file_service.file_service", mock_fs):
        ok = await DriveService(db).permanent_delete(k.id, current_user_id=m.id)
    assert ok is True
    called = {c.args[0] for c in mock_fs.delete_file.call_args_list}
    assert called == expected, f"应清 3 个对象 (B2), 实收 {called}"

    left = (await db.execute(select(Knowledge).where(Knowledge.id == k.id))).scalar_one_or_none()
    assert left is None


# ---------------------------------------------------------------------------
# (b) cleanup 路径 N1 回归锁
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cleanup_purges_all_keys_n1_regression_lock(gc_env):
    """若 clean_old_drive_files 回退成"先 DELETE 后 SELECT"旧顺序 → expired_files
    恒空 → delete_file 收不到 key → 本测试即红 (N1 回归锁)。"""
    from app.services.drive_cleanup_service import clean_old_drive_files
    db, m = gc_env["db"], gc_env["m"]
    k1, v1 = await _mk_trashed_drive_file(
        db, m, "expired_v1.doc", deleted_at=_naive_now() - timedelta(days=40), versions=1,
    )
    k2, _ = await _mk_trashed_drive_file(
        db, m, "expired_v2.doc", deleted_at=_naive_now() - timedelta(days=45), versions=0,
    )
    # 不超期的对照组 (30 天内, 不该被动)
    k3, _ = await _mk_trashed_drive_file(
        db, m, "fresh.doc", deleted_at=_naive_now() - timedelta(days=1), versions=0,
    )
    expected = {k1.file_path, k2.file_path} | set(v1)

    mock_fs = MagicMock()
    with patch("app.services.file_service.file_service", mock_fs), \
         patch("app.services.drive_cleanup_service.backup_rows_to_json",
               new=AsyncMock(return_value=(2, None))):
        result = await clean_old_drive_files(db, _naive_now() - timedelta(days=30))

    assert result["deleted_files"] == 2
    assert result["minio_cleanup_failures"] == 0
    called = {c.args[0] for c in mock_fs.delete_file.call_args_list}
    assert called == expected, f"N1: cleanup 从未真正清 MinIO 的回归 {called}"
    assert k3.file_path not in called, "未超期文件对象不得被碰"
    left = (await db.execute(select(Knowledge).where(Knowledge.id == k3.id))).scalar_one_or_none()
    assert left is not None


# ---------------------------------------------------------------------------
# (d) 多模态图片对象回收 (2026-10-11 缺口修复)
#
# 该泄漏此前一直被「永久删整体回滚」那个 bug 盖住 (FK 置空撞 NOT NULL,
# 748fee987 已修), 从没暴露过; 删得掉了才显形 —— 每删一个带图的 PPT 就漏一批 PNG。
# 真实事故样本: KB 孪生 2818 挂 20 张图, permanent_delete 后 20 个孤儿永久留 MinIO。
# ---------------------------------------------------------------------------

async def _mk_image(db, knowledge_id, object_name):
    img = KnowledgeImage(
        knowledge_id=knowledge_id, image_url=f"http://minio/{object_name}",
        image_object_name=object_name, ocr_status="done",
    )
    db.add(img)
    await db.commit()
    return object_name


@pytest.mark.asyncio
async def test_collect_keys_includes_image_objects(gc_env):
    """带图行必须把 image_object_name 一并收进待删列表 (原实现只收 file_path + 版本 key)。"""
    db, m = gc_env["db"], gc_env["m"]
    k, vkeys = await _mk_trashed_drive_file(
        db, m, "with_images.pptx", deleted_at=_naive_now(), versions=1,
    )
    o1 = await _mk_image(db, k.id, "knowledge/9999/images/fig1.png")
    o2 = await _mk_image(db, k.id, "knowledge/9999/images/fig2.png")

    result = await collect_object_keys(db, [k])
    assert o1 in result and o2 in result, f"图片对象漏收 → 删后永久孤儿: {result}"
    assert set(result) == {k.file_path, vkeys[0], o1, o2}
    assert len(result) == len(set(result)), "去重"


@pytest.mark.asyncio
async def test_permanent_delete_purges_image_objects(gc_env):
    """端到端: 永久删带图文件时 delete_file 必须收到图片 key。"""
    from app.services.drive_service import DriveService
    db, m = gc_env["db"], gc_env["m"]
    k, _ = await _mk_trashed_drive_file(db, m, "del_img.pptx", deleted_at=_naive_now())
    o1 = await _mk_image(db, k.id, "knowledge/8888/images/a.png")

    mock_fs = MagicMock()
    with patch("app.services.file_service.file_service", mock_fs):
        assert await DriveService(db).permanent_delete(k.id, current_user_id=m.id) is True
    called = {c.args[0] for c in mock_fs.delete_file.call_args_list}
    assert o1 in called, f"图片对象未被 purge: {called}"


@pytest.mark.asyncio
async def test_shared_image_object_not_purged_while_other_row_alive(gc_env):
    """误删护栏: 同一 image_object_name 被**别的存活行**引用时不得进待删列表。

    实测生产库 5446 张图 0 条跨行重复 (uuid4 + knowledge/{id}/images 命名空间),
    但那是约定不是约束 —— 复制/还原/人工修数据都可能造出重复, 直接删 key 会把
    别人仍在用的图删成 404。
    """
    db, m = gc_env["db"], gc_env["m"]
    k, _ = await _mk_trashed_drive_file(db, m, "shared_src.pdf", deleted_at=_naive_now())
    twin = Knowledge(
        content="", title="shared_twin", storage_mode="kb", file_name="shared_src.pdf",
        file_path=k.file_path, created_by=m.id, visibility="team",
    )
    db.add(twin)
    await db.commit()
    await db.refresh(twin)

    shared = "knowledge/shared/object.png"
    await _mk_image(db, k.id, shared)
    await _mk_image(db, twin.id, shared)  # 孪生也引用同一个 object

    keys_only_source = await collect_object_keys(db, [k])
    assert shared not in keys_only_source, "共享图被误收 → 会删掉孪生仍在用的图"

    keys_both = await collect_object_keys(db, [k, twin])
    assert shared in keys_both, "两条都删时共享图应可回收"


# ---------------------------------------------------------------------------
# (e) ZB-1 死链回归锁 (2026-10-11): 被 skip 的 private 行, 对象不得被 purge
#
# 旧实现对**全部** files 收 key, 却在循环里才 continue 跳过 private 行 →
# DB 行活着 / 对象已删 = 404 死链。同型 bug 还有孪生无条件级联 (孪生级联的
# 前提是「源行被删 + 共享对象被 purge」, 源行被跳过时删孪生纯属无理由销毁活数据)。
# ---------------------------------------------------------------------------

async def _mk_private_drive_file(db, owner, name, *, deleted_at, visibility="private"):
    k = Knowledge(
        content="", title=name, storage_mode="drive", file_name=name,
        file_path=f"drive-test/{name}", created_by=owner.id,
        visibility=visibility, deleted_at=deleted_at,
    )
    db.add(k)
    await db.commit()
    await db.refresh(k)
    return k


@pytest.mark.asyncio
async def test_batch_delete_skipped_private_object_not_purged(gc_env):
    """一个可见 (team) + 一个 private 不可见 → 不可见那个的对象**一个都不能被 purge**。"""
    from app.services.drive_service import DriveService
    db, m = gc_env["db"], gc_env["m"]
    other = Member(
        username=f"gc_o{_uuid.uuid4().hex[:8]}", name="other", password_hash="h",
        role="member", grade="测试", is_active=True,
    )
    db.add(other)
    await db.commit()
    await db.refresh(other)

    # visible: 非 private, 他人可见
    vis, vis_vkeys = await _mk_trashed_drive_file(
        db, m, "visible_ok.pdf", deleted_at=_naive_now(), versions=2,
    )
    vis_img = await _mk_image(db, vis.id, "knowledge/7777/images/v1.png")

    # private + created_by 是别人 → current_user (m) 看不见 → 必被 skip
    priv = await _mk_private_drive_file(
        db, other, "private_no.pdf", deleted_at=_naive_now(),
    )
    priv_vkey = "drive-test/private_no.pdf.v0"
    db.add(DriveFileVersion(
        file_id=priv.id, version_number=1, minio_object_key=priv_vkey,
        size=10, uploader_id=other.id, is_current=0,
    ))
    priv_img = await _mk_image(db, priv.id, "knowledge/7777/images/p1.png")

    mock_fs = MagicMock()
    with patch("app.services.file_service.file_service", mock_fs):
        deleted, skipped = await DriveService(db).permanent_delete_batch(
            [vis.id, priv.id], current_user_id=m.id,
        )

    assert deleted == 1, f"只该删可见那个, 实删 {deleted}"
    assert skipped == [priv.id], f"private 那个必须进 skipped, 实得 {skipped}"

    called = {c.args[0] for c in mock_fs.delete_file.call_args_list}
    # 可见的那个: 当前 + 版本 + 图片 全清
    assert called == {vis.file_path, *vis_vkeys, vis_img}, f"可见文件应全清, 实收 {called}"
    # 不可见的那个: 当前 + 版本 + 图片 一个都不能碰 (404 死链回归锁)
    for leaked in (priv.file_path, priv_vkey, priv_img):
        assert leaked not in called, f"被 skip 的行对象被 purge → 404 死链: {leaked}"

    # DB 行确实还活着
    left = (await db.execute(select(Knowledge).where(Knowledge.id == priv.id))).scalar_one_or_none()
    assert left is not None, "被 skip 的行不该被删"
    assert (await db.execute(select(Knowledge).where(Knowledge.id == vis.id))).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_batch_delete_skipped_drive_keeps_its_kb_twin(gc_env):
    """源行被 ZB-1 跳过时, 共享同一 file_path 的 KB 孪生**必须存活**。

    孪生级联 (collect_live_kb_twins) 的既定前提是「网盘源行被彻底删 → 共享对象被
    purge → 孪生存活即死链」。源行被跳过 ⇒ 对象不 purge ⇒ 无死链 ⇒ 删孪生是无理由
    销毁存活 KB 数据 (连带其 chunk/embedding/图片)。反之, 源行真被删时孪生仍须级联。
    """
    from app.services.drive_service import DriveService
    db, m = gc_env["db"], gc_env["m"]
    other = Member(
        username=f"gc_o{_uuid.uuid4().hex[:8]}", name="other2", password_hash="h",
        role="member", grade="测试", is_active=True,
    )
    db.add(other)
    await db.commit()
    await db.refresh(other)

    # --- 场景 1: private 源被跳过 → 孪生存活 ---
    priv = await _mk_private_drive_file(db, other, "priv_twin.pdf", deleted_at=_naive_now())
    priv_twin = Knowledge(
        content="", title="priv_twin_kb", storage_mode="kb", file_name="priv_twin.pdf",
        file_path=priv.file_path, created_by=other.id, visibility="team",
    )
    db.add(priv_twin)
    await db.commit()
    await db.refresh(priv_twin)
    priv_twin_img = await _mk_image(db, priv_twin.id, "knowledge/6666/images/t1.png")

    # --- 场景 2: team 源真被删 → 孪生仍须级联 (防止修复过头) ---
    vis, _ = await _mk_trashed_drive_file(db, m, "vis_twin.pdf", deleted_at=_naive_now())
    vis_twin = Knowledge(
        content="", title="vis_twin_kb", storage_mode="kb", file_name="vis_twin.pdf",
        file_path=vis.file_path, created_by=m.id, visibility="team",
    )
    db.add(vis_twin)
    await db.commit()
    await db.refresh(vis_twin)
    vis_twin_img = await _mk_image(db, vis_twin.id, "knowledge/6666/images/t2.png")

    mock_fs = MagicMock()
    with patch("app.services.file_service.file_service", mock_fs):
        deleted, skipped = await DriveService(db).permanent_delete_batch(
            [priv.id, vis.id], current_user_id=m.id,
        )
    assert (deleted, skipped) == (1, [priv.id])

    called = {c.args[0] for c in mock_fs.delete_file.call_args_list}
    # 场景 1: 源行与共享对象都留着 → 孪生行与孪生图一个都不能动
    assert priv.file_path not in called, "被跳过的源对象被 purge → 死链"
    assert priv_twin_img not in called, "存活孪生的图被 purge"
    alive = (await db.execute(select(Knowledge).where(Knowledge.id == priv_twin.id))).scalar_one_or_none()
    assert alive is not None, "源行被跳过时 KB 孪生不该被级联删"
    assert (
        await db.execute(select(KnowledgeImage).where(KnowledgeImage.knowledge_id == priv_twin.id))
    ).scalars().first() is not None, "孪生图片行不该消失"

    # 场景 2: 源真被删 → 孪生级联 + 共享对象/孪生图照收 (防修复过头)
    gone = (await db.execute(select(Knowledge).where(Knowledge.id == vis_twin.id))).scalar_one_or_none()
    assert gone is None, "源行真被删时孪生必须级联, 否则共享对象 purge 后孪生成死链"
    assert vis.file_path in called and vis_twin_img in called, f"该清的没清: {called}"


# ---------------------------------------------------------------------------
# (c) purge 单 key 失败不抛、其余继续
# ---------------------------------------------------------------------------

def test_purge_continues_after_failure_and_counts():
    keys = ["ok1", "bad", "ok2"]
    mock_fs = MagicMock()

    def _delete(p):
        if p == "bad":
            raise IOError("MinIO connection refused")
    mock_fs.delete_file.side_effect = _delete

    with patch("app.services.file_service.file_service", mock_fs):
        failures = purge_minio_keys(keys)  # 不得抛
    assert failures == 1
    assert [c.args[0] for c in mock_fs.delete_file.call_args_list] == keys, "失败后继续逐 key 删"
