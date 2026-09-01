"""WP10 (2026-09-01): kg_entities 存量回填 — 实体链召回第 5 路数据补齐

背景 (fuzzy-questing-prism WP10):
  kg_entities 由 knowledge_service Step 5b hook (_add_entity_links) 只对
  新入库文档生效, 存量文档无实体 → entity_link 召回路休眠 (生产实测 0 行)。
  本脚本循环存量 kb 文档调 _add_entity_links (复用现有函数, 内部幂等:
  同 (name,type,knowledge_id) 只累计 mention_count), 0 新增 LLM 调用
  (复用 Step 5 已写入的 knowledge_entities SPO 三元组派生)。

注意: _add_entity_links 内部会为实体生成 embedding (本地模型推理)。

用法 (容器内):
    docker compose exec app python scripts/backfill_kg_entities.py --dry-run
    docker compose exec app python scripts/backfill_kg_entities.py --apply
    docker compose exec app python scripts/backfill_kg_entities.py --apply --limit 30
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_kg_entities")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WP10: kg_entities 存量回填")
    parser.add_argument("--apply", action="store_true", help="真写库 (默认 dry-run 只统计)")
    parser.add_argument("--limit", type=int, default=0, help="最多处理 N 篇 (0 = 全部)")
    parser.add_argument("--knowledge-id", type=int, default=0, help="只处理指定文档")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()

    from app.config import settings
    from app.models.kg_entity import KGEntity
    from app.models.knowledge import Knowledge
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url, pool_size=2)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    stats = {"scanned": 0, "todo": 0, "linked": 0, "failed": 0, "dry_run": not args.apply}
    try:
        async with Session() as db:
            # 已有 kg_entities 的文档 (幂等跳过)
            done_ids = set(
                (await db.execute(select(KGEntity.knowledge_id).distinct())).scalars()
            )
            stmt = select(Knowledge.id, Knowledge.title).where(
                Knowledge.deleted_at.is_(None),
                Knowledge.storage_mode == "kb",
            )
            if args.knowledge_id:
                stmt = stmt.where(Knowledge.id == args.knowledge_id)
            if args.limit:
                stmt = stmt.limit(args.limit)
            rows = (await db.execute(stmt)).all()
            stats["scanned"] = len(rows)
            todo = [(kid, title) for kid, title in rows if kid not in done_ids]
            stats["todo"] = len(todo)
            logger.info(
                "扫描 kb 文档 %d 篇, 缺实体 %d 篇%s",
                len(rows),
                len(todo),
                " (dry-run)" if not args.apply else "",
            )

            if not args.apply:
                for kid, title in todo[:50]:
                    logger.info("  [dry-run] 待回填 knowledge_id=%s (%s)", kid, (title or "")[:30])
                return 0

        from app.services.kg_embedding import generate_kg_entity_embedding
        from app.services.knowledge_graph_service import _add_entity_links

        def _jsonb_candidates(entities_jsonb) -> list:
            """entities JSONB ({name,type,...}) → kg_entities 候选 (JSONB 兜底派生)"""
            from app.models.kg_entity import coerce_entity_type, normalize_entity_name

            out = []
            if not isinstance(entities_jsonb, list):
                return out
            for ent in entities_jsonb:
                if not isinstance(ent, dict):
                    continue
                name = normalize_entity_name(str(ent.get("name") or ""))
                if not name:
                    continue
                out.append({
                    "entity_name": name,
                    "entity_type": coerce_entity_type(str(ent.get("type") or "OTHER")),
                    "mention_count": 1,
                })
            return out

        async def _upsert_jsonb_entities(kid: int) -> dict:
            """SPO 派生为 0 时, 从 knowledge.entities JSONB 直接 upsert
            (与 _add_entity_links 同款幂等语义: 同 (name,type,doc) 只累计 mention_count)"""
            from sqlalchemy import and_, select as sa_select

            from app.models.kg_entity import KGEntity

            local_stats = {"created": 0, "updated": 0}
            async with Session() as wdb:
                krow = (
                    await wdb.execute(sa_select(Knowledge).where(Knowledge.id == kid))
                ).scalar_one_or_none()
                if krow is None:
                    return local_stats
                candidates = _jsonb_candidates(krow.entities)
                candidates = candidates[:40]  # 单文档上限, 控制回填成本
                for cand in candidates:
                    name = cand["entity_name"]
                    etype = cand["entity_type"]
                    existing = (
                        await wdb.execute(
                            sa_select(KGEntity).where(
                                and_(
                                    KGEntity.entity_name == name,
                                    KGEntity.entity_type == etype,
                                    KGEntity.knowledge_id == kid,
                                )
                            )
                        )
                    ).scalar_one_or_none()
                    if existing is not None:
                        existing.mention_count = (existing.mention_count or 1) + 1
                        local_stats["updated"] += 1
                        continue
                    entity = KGEntity(
                        entity_name=name,
                        entity_type=etype,
                        knowledge_id=kid,
                        mention_count=cand["mention_count"],
                    )
                    emb = await generate_kg_entity_embedding(name, etype)
                    if emb:
                        entity.embedding = emb
                    wdb.add(entity)
                    local_stats["created"] += 1
                await wdb.commit()
            return local_stats

        for i, (kid, title) in enumerate(todo, 1):
            try:
                async with Session() as wdb:
                    kg_stats = await _add_entity_links(wdb, kid)
                if kg_stats.get("total", 0) == 0:
                    # SPO 表无三元组 → entities JSONB 兜底派生 (95/99 篇属此类)
                    kg_stats = await _upsert_jsonb_entities(kid)
                    kg_stats["via"] = "entities_jsonb"
                stats["linked"] += 1
                logger.info("[%d/%d] knowledge_id=%s → %s", i, len(todo), kid, kg_stats)
            except Exception as e:
                stats["failed"] += 1
                logger.warning("knowledge_id=%s 实体回填失败: %s", kid, e)
    finally:
        await engine.dispose()

    import json

    print(json.dumps(stats, ensure_ascii=False))
    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
