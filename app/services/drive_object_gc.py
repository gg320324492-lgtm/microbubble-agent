"""批次① B2+N1 — Drive 文件物理删除时的 MinIO 对象统一回收 (2026-09-05)

背景 (两个真 bug):
- B2: drive_service.permanent_delete / permanent_delete_batch 只删
  Knowledge.file_path 的**当前**对象, PR9 版本历史 (drive_file_versions.
  minio_object_key) 的旧对象全部泄漏在 MinIO 里, 永不可见也永不清理。
- N1: drive_cleanup_service.clean_old_drive_files 先 `DELETE FROM knowledge`
  后用**同一个 where** 再 SELECT 拿 file_path → 恒空 → MinIO 清理从未执行过
  (过期文件对象全量泄漏)。修复 = 重排为 先 SELECT → 后 DELETE, 本模块把
  "收集 key + 逐 key 删除" 收敛成两个函数供两处调用。

2026-10-11 追加 (第三类漏项):
- IMG: 上面两类漏项 (当前对象 / 版本对象) 之外, 多模态图片
  (`knowledge_images.image_object_name`) 也是独立 MinIO object, 却从未被收集 →
  每删一个带图的 PPT/文档就永久漏一批 PNG。该泄漏此前一直被**另一个 bug 整体盖住**
  (permanent_delete 因 ORM FK 置空撞 NOT NULL 而回滚, commit 748fee987 已修),
  从未暴露过; 删得掉了才显形 (实测孪生 2818 挂 20 图 ⇒ 删它留 20 个孤儿)。
  ⚠️ 注意图片挂在 **KB 孪生** 上 (孪生自己跑过多模态抽取), 所以三个调用点都必须
  把 `kb_twins` 一并传进 collect_object_keys, 只传 drive 行仍会漏收。

调用顺序铁律:
1. collect_object_keys **必须**在任何 db.delete/DELETE 之前调用 —
   drive_file_versions 与 knowledge_images 对 knowledge 都是 ON DELETE CASCADE,
   主表行一删版本/图片行即消失, 之后再查 key 永远查不到 (这正是 N1 的同型陷阱)。
2. purge_minio_keys 放在 DB commit **之后** — MinIO 不可达时不应回滚已成功的
   DB 硬删 (宁可留孤儿对象可事后清, 不可留无主 DB 行)。
3. purge 永不抛异常: 逐 key try/except + logger.warning, 返回失败计数,
   与 cleanup_service 原有 "失败不阻塞 DB 硬删" 铁律一致。

类 20.181 教训 (patch 目标 = 本地绑定): purge_minio_keys 内 file_service 走
**调用时 inline import**, 保持与旧 drive_cleanup_service 相同打点,
测试继续 patch("app.services.file_service.file_service") 即可生效。
"""
import logging
from typing import List, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.drive_file_version import DriveFileVersion
from app.models.knowledge_multimodal import KnowledgeImage

logger = logging.getLogger("microbubble.drive_object_gc")


async def collect_object_keys(db: AsyncSession, files: Sequence) -> List[str]:
    """收集一批 Knowledge 行关联的全部 MinIO object key
    (当前对象 + 全部历史版本 + 全部多模态图片对象).

    Args:
        db: AsyncSession (只读查询)
        files: Knowledge ORM 行序列 (需 .id / .file_path), 通常来自永久删前的 SELECT。
              ⚠️ 必须是**将被删除的那批行**的完整集合 —— 两个方向都会出事:
              **少传** = 漏收 key (删完变永久孤儿, 如 2026-10-11 的图片/版本泄漏),
              **多传** = purge 掉 DB 行还活着的对象 (404 死链, 如 permanent_delete_batch
              曾对被 ZB-1 跳过的 private 行也收 key)。所以上游三个调用点都把
              `kb_twins` 一并传进来 (「上传即自动入库」的 KB 孪生**自己也有图片**,
              实测孪生 2818 = storage_mode 'kb' 挂 20 张图), 且传的都是「确实会删」的子集。

    Returns:
        去重后的 key 列表 (保持发现顺序: 当前对象 → 版本对象 → 图片对象); 空输入返 []

    ⚠️ 必须在任何针对这些行的 DELETE 之前调用 (FK CASCADE 会先消版本/图片行, 见模块 docstring)。
    """
    keys: List[str] = []
    seen: set = set()
    file_ids: List[int] = []

    for f in files:
        file_ids.append(f.id)
        if f.file_path and f.file_path not in seen:
            seen.add(f.file_path)
            keys.append(f.file_path)

    if not file_ids:
        return keys

    # PR9 版本仓库: 每个历史版本一份独立 object, 主表删了它们就是纯孤儿
    stmt = select(DriveFileVersion.minio_object_key).where(
        DriveFileVersion.file_id.in_(file_ids)
    )
    rows = (await db.execute(stmt)).scalars().all()
    for key in rows:
        if key and key not in seen:
            seen.add(key)
            keys.append(key)

    # 2026-10-11 缺口修复: 多模态图片 (knowledge_images.image_object_name)
    # 同样带 object 却从未被收集 → 每删一个带图的 PPT/文档就永久漏一批 PNG 到 MinIO。
    # 该泄漏此前被「永久删整体回滚」这个 bug 盖住 (748fee987 已修), 从没暴露过。
    # 批量取, 不 N+1。image_url 是公开 URL **不是** key, 不可收。
    img_stmt = select(KnowledgeImage.image_object_name).where(
        KnowledgeImage.knowledge_id.in_(file_ids)
    )
    image_keys: List[str] = []
    for key in (await db.execute(img_stmt)).scalars().all():
        if key and key not in seen:
            seen.add(key)
            keys.append(key)
            image_keys.append(key)

    if image_keys:
        shared = await _find_shared_image_keys(db, image_keys, file_ids)
        if shared:
            for key in shared:
                keys.remove(key)  # 仍活着的其他 Knowledge 行在用 → 不碰

    return keys


async def _find_shared_image_keys(
    db: AsyncSession, image_keys: Sequence[str], deleting_ids: Sequence[int]
) -> set:
    """找出「本次待删集合之外仍有 Knowledge 行引用」的图片 key。

    误删风险护栏 (2026-10-11): image_object_name 是**裸 String(500), 表上无 unique 约束**
    (唯一性只来自 file_service.upload_file 的 uuid4 + `knowledge/{id}/images/` 命名空间前缀,
    且全库仅 multimodal_extraction_service._upload_images 一处创建)。实测生产库 5446 张图
    **0 条**跨行重复 —— 即"结构上不会共享"。但那是**约定**不是**约束**: 将来任何复制/复用
    路径 (备份还原 / 文档去重 / 人工修数据) 一旦写入重复 object_name, 直接删 key 就会把
    **别人仍在用的图**删成 404。故此处显式兜底: 有外部引用就不进待删列表 (宁可留孤儿,
    孤儿事后可巡检, 活图被删不可恢复 —— 与 purge_minio_keys 的同一取舍)。

    单条查询 (实测 Seq Scan 3.2ms @ 5446 行), 仅在真有图片 key 时才发。
    """
    result = await db.execute(
        select(KnowledgeImage.image_object_name)
        .where(
            KnowledgeImage.image_object_name.in_(list(image_keys)),
            KnowledgeImage.knowledge_id.notin_(list(deleting_ids)),
        )
        .distinct()
    )
    return {k for k in result.scalars().all() if k}


def purge_minio_keys(keys: Sequence[str]) -> int:
    """逐 key 物理删 MinIO 对象; 单 key 失败只记 warning 不抛 (防御性).

    Args:
        keys: collect_object_keys 的产出 (调用方保证已在 DB commit 之后)

    Returns:
        失败数 (0 = 全部删净); 失败对象留在 MinIO 可事后孤儿巡检再清
    """
    failures = 0
    # 类 20.181: 调用时 import, 与旧 drive_cleanup_service 打点兼容
    # (patch("app.services.file_service.file_service") 在调用时才解析)
    from app.services.file_service import file_service

    for key in keys:
        try:
            file_service.delete_file(key)
        except Exception as e:
            failures += 1
            logger.warning(f"⚠️ [drive_object_gc] MinIO 对象删除失败 key={key}: {e}")
    return failures
