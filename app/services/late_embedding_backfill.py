"""Late embedding chunk-level backfill service (W-N-FILL-IMPL +1, 2026-08-06)

设计目的:
  W-N-D++ 端到端 late chunking 召回 bench 决策 (W-N-D++ +2, commit `1cc5362e2`)
  Gate 1 hard-fail (recall +0.00%), 整段归档.
  W-N-D 加列 `knowledge_chunks.chunk_embedding` (vector(1024)[]) 已存在
  (W-N-G+ 修复后), 但**回填操作因 W-N-D++ §5 决策被拦截** (W-N-FILL 留口 §2).

  本 service 提供**dry-run by default**的回填入口, 留待 W-N-FILL 派工真跑时调用.
  当前不接入 Celery beat (W-N-REVISE §3 修订: 业务决策 recall > 0 仍 FAIL).

W-N-FILL-IMPL 派工 brief 严禁:
  - 0 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ 旧 commits
  - 0 改 alembic/versions/ 任何已有迁移
  - 0 改 app/services/hybrid_retriever.py 既有 4 路逻辑
  - 0 改 app/services/embedding_service.py 既有 4 API
  - 0 改 app/agent/chat_engine.py 方案 C 6 铁律
  - 0 改 drive_comments_path_backfill_service.py 模板 (W68 第 12 批 B-1 范畴)
  - 0 改 celery_app.conf.beat_schedule (不注册新 schedule)
  - 0 改 app/main.py 启动流程
  - 0 真跑 Celery task (W-N-FILL 留口 §2 阻断)
  - 0 真写 DB (CLI 默认 dry_run=True, 显式 --apply 才写)
  - 0 改 .env / EMBEDDING_BACKEND / EMBEDDING_MODEL_NAME

设计要点 (复用 W68 第 12 批 B-1 PR14 模板):
  1. dry_run 默认 True — 默认只统计, 不写库 (防误操作)
  2. 走 service 入口 — 不直接调 Celery task, CLI 同步看结果
  3. 跨 event loop 修复 — 复用 create_celery_engine_and_session (NullPool + expire_on_commit=False)
  4. update_one_chunk() 幂等 — 单 chunk 重算, 可重入
  5. backfill_all() 全表模式 — 扫所有 chunk_embedding IS NULL 的 chunk
  6. 530 docs 估算 — 沿用 W-N-FILL 留口 §2 业务背景 (W-N-D +2 已部署 530 docs)

与 PR14 模板差异:
  1. 不调 reset_count / commit 流 (W-N-D++ 决策后**禁止写入**, 默认 dry_run)
  2. 不依赖 drive_comments_path_backfill_service (避免跨模型耦合)
  3. LateChunkingService 是新依赖 (W-N-C +1 范畴, 已存在)
  4. 不调 LLM / 远程 embedding API (本地 model 推理, 沿用 W-N-BGE 灰度路径)

业务代码路径 (派工 brief 严禁擅自扩):
  - 不动 hybrid_retriever._chunk_late_recall (W-N-OBS 范畴, 业务代码)
  - 不动 _chunk_late_recall SQL 路径 (class 20.156 best-effort 静默失败)
  - 不动 _chunk_late_recall 异常处理 (W-N-D++ §3 实测)

W-N-FILL-IMPL 启用条件 (W-N-REVISE §3 修订 3 选 1):
  (a) knowledge_chunks.chunk_embedding 列存在 — ✅ W-N-G+ 验证
  (b) tests 8/8 PASS — ✅ W-N-G+ 验证
  (c) 业务决策 recall > 0 — ❌ W-N-D++ 决策 +0.00% FAIL (默认禁止)

触发再启条件 (W-N-REVISE +1):
  1. W-N-D++ 决策文档中 §5 是否仍标 "整段归档" — 若 YES, 拒绝派工
  2. qa-bench 当前分数是否 ≥ 96.5% — 若 NO, 拒绝派工
  3. 主拍是否明确书面批准 W-N-FILL 派工 — 若 NO, 拒绝派工
  4. (W-N-REVISE 新增) 3 选 1 触发条件 (a)(b)(c) 是否齐全 — (c) FAIL, 默认禁止

类 20 沉淀 (W-N-FILL-IMPL 新增):
  - 类 20.158: late_embedding 回填脚本必 dry_run 默认 True + 5 秒 apply 等待 + 严禁本地 Celery 触发
  - 类 20.159: 业务决策 recall +0% 硬门禁禁止下, 脚本可写但真跑必须主拍书面批准
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("microbubble.late_embedding_backfill")


@dataclass
class LateEmbeddingBackfillResult:
    """W-N-FILL-IMPL 回填结果汇总

    Fields:
        total_examined: 扫到的 chunk 总数 (含无变化)
        updated: 实际 UPDATE 成功的 chunk 数 (chunk_embedding 已写入)
        failed: 失败 chunk 数 (encode 异常 / NULL content)
        dry_run: 是否 dry-run (无写库)
        target: "all" / "chunk:42" / "knowledge:5" 描述
        errors: List[str] 失败原因摘要
    """

    total_examined: int = 0
    updated: int = 0
    failed: int = 0
    dry_run: bool = True
    target: str = "all"
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_examined": self.total_examined,
            "updated": self.updated,
            "failed": self.failed,
            "dry_run": self.dry_run,
            "target": self.target,
            "errors": list(self.errors),
        }


class LateEmbeddingBackfillService:
    """Late embedding chunk-level 回填 service (W-N-FILL-IMPL +1)

    Usage:
        async with AsyncSessionLocal() as db:
            svc = LateEmbeddingBackfillService(db, model_tokenizer, model_forward)
            result = await svc.backfill_all(dry_run=True)  # default dry-run
            print(result.to_dict())

        # 如主拍书面批准 (W-N-FILL 触发条件 3 选 1 全 PASS):
            result = await svc.backfill_all(dry_run=False)  # 真写库
    """

    def __init__(
        self,
        db: AsyncSession,
        *,
        model_tokenizer: Any,
        model_forward: Any,
        chunk_size: int = 256,
        overlap: int = 32,
        max_length: int = 8192,
    ) -> None:
        """初始化 service

        Args:
            db: AsyncSession (AsyncSessionLocal context)
            model_tokenizer: tokenizer callable (LateChunkingService 依赖)
            model_forward: forward callable (LateChunkingService 依赖)
            chunk_size: LateChunkingService chunk_size (默认 256, 沿用 W-N-C 默认)
            overlap: LateChunkingService overlap (默认 32, 沿用 W-N-C 默认)
            max_length: LateChunkingService max_length (默认 8192, 沿用 W-N-C 默认)
        """
        self.db = db
        self._model_tokenizer = model_tokenizer
        self._model_forward = model_forward
        self._chunk_size = chunk_size
        self._overlap = overlap
        self._max_length = max_length

    def _build_late_chunking_service(self):
        """延迟 import LateChunkingService (避免 service 加载时强依赖 numpy)"""
        from app.services.late_chunking_service import LateChunkingService

        # 沿用 LateChunkingService 期望的 model 协议: tokenizer + forward
        class _Adapter:
            def __init__(self, tokenizer, forward):
                self.tokenizer = tokenizer
                self.forward = forward

        adapter = _Adapter(self._model_tokenizer, self._model_forward)
        return LateChunkingService(
            adapter,
            chunk_size=self._chunk_size,
            overlap=self._overlap,
            max_length=self._max_length,
        )

    async def _fetch_pending_chunks(
        self,
        *,
        knowledge_id: Optional[int] = None,
        chunk_id: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[dict]:
        """扫 chunk_embedding IS NULL 的 chunk rows

        Returns:
            List[dict] 每个 dict 包含 id, knowledge_id, chunk_index, content, char_start, char_end
        """
        conditions = ["chunk_embedding IS NULL"]
        params: dict[str, Any] = {}

        if chunk_id is not None:
            conditions.append("id = :chunk_id")
            params["chunk_id"] = chunk_id
        elif knowledge_id is not None:
            conditions.append("knowledge_id = :knowledge_id")
            params["knowledge_id"] = knowledge_id

        sql = f"""
            SELECT id, knowledge_id, chunk_index, content, char_start, char_end
            FROM knowledge_chunks
            WHERE {' AND '.join(conditions)}
            ORDER BY knowledge_id, chunk_index
        """
        if limit is not None:
            sql += f" LIMIT {int(limit)}"

        result = await self.db.execute(text(sql), params)
        rows = result.mappings().all()
        return [dict(row) for row in rows]

    async def _encode_chunk_to_pgvector(self, content: str) -> Optional[List[str]]:
        """调 LateChunkingService.encode(content) → pgvector 字符串数组

        Args:
            content: chunk 原文

        Returns:
            List[str] 形如 ["[0.1,0.2,...]", ...] pgvector 字面量数组
            None 当 encode 失败 (NULL content / 空 content / 异常)
        """
        if not content:
            return None
        try:
            service = self._build_late_chunking_service()
            vectors = service.encode(content)
            if not vectors:
                return None
            # pgvector array literal: ['[v0,v1,...]', '[v0,v1,...]']
            return ["[" + ",".join(f"{v:.6f}" for v in vec.tolist()) + "]" for vec in vectors]
        except Exception as exc:
            logger.warning("late embedding encode failed: %s", exc, exc_info=False)
            return None

    async def backfill_one_chunk(
        self,
        chunk_id: int,
        *,
        dry_run: bool = True,
    ) -> LateEmbeddingBackfillResult:
        """单 chunk 重算 (派工 brief 严禁真跑, 默认 dry_run=True)

        Args:
            chunk_id: 单 chunk mode (e.g. 42)
            dry_run: True = 只统计, 不写库 (默认)
                     False = 真写库 (W-N-FILL 真派工时显式确认)

        Returns:
            LateEmbeddingBackfillResult
        """
        target = f"chunk:{chunk_id}"
        chunks = await self._fetch_pending_chunks(chunk_id=chunk_id)
        if not chunks:
            return LateEmbeddingBackfillResult(
                total_examined=0,
                updated=0,
                dry_run=dry_run,
                target=target,
                errors=[f"chunk {chunk_id} not found or already filled"],
            )

        chunk = chunks[0]
        encoded = await self._encode_chunk_to_pgvector(chunk["content"])
        if encoded is None:
            return LateEmbeddingBackfillResult(
                total_examined=1,
                updated=0,
                failed=1,
                dry_run=dry_run,
                target=target,
                errors=["encode failed (empty content or model error)"],
            )

        if dry_run:
            logger.info(
                "🔍 [DRY-RUN] Would update chunk %d: %d vectors",
                chunk_id,
                len(encoded),
            )
            return LateEmbeddingBackfillResult(
                total_examined=1,
                updated=0,  # dry-run: 0 actual update
                dry_run=True,
                target=target,
            )

        # 真写库 (W-N-FILL 真派工时)
        chunk_emb_array = "{" + ",".join(encoded) + "}"
        await self.db.execute(
            text(
                "UPDATE knowledge_chunks "
                "SET chunk_embedding = :chunk_emb::vector[], updated_at = NOW() "
                "WHERE id = :chunk_id"
            ),
            {"chunk_emb": chunk_emb_array, "chunk_id": chunk_id},
        )
        await self.db.commit()
        logger.warning(
            "🔄 [APPLY] Updated chunk %d with %d vectors",
            chunk_id,
            len(encoded),
        )
        return LateEmbeddingBackfillResult(
            total_examined=1,
            updated=1,
            dry_run=False,
            target=target,
        )

    async def backfill_all(
        self,
        *,
        dry_run: bool = True,
        limit: Optional[int] = None,
    ) -> LateEmbeddingBackfillResult:
        """全表模式回填 (派工 brief 严禁真跑, 默认 dry_run=True)

        Args:
            dry_run: True = 只统计, 不写库 (默认)
            limit: 限制 chunk 数 (e.g. 100 试跑, 避免 530 docs 全表锁)

        Returns:
            LateEmbeddingBackfillResult 汇总
        """
        target = "all"
        chunks = await self._fetch_pending_chunks(limit=limit)
        total = len(chunks)
        if total == 0:
            return LateEmbeddingBackfillResult(
                total_examined=0,
                updated=0,
                dry_run=dry_run,
                target=target,
                errors=["no pending chunks (all chunk_embedding already filled)"],
            )

        if dry_run:
            # Dry-run: 扫一遍 + encode 测一遍, 不写库
            updated = 0
            failed = 0
            errors: List[str] = []
            for chunk in chunks:
                encoded = await self._encode_chunk_to_pgvector(chunk["content"])
                if encoded is None:
                    failed += 1
                    if len(errors) < 10:
                        errors.append(f"chunk {chunk['id']}: encode failed")
                else:
                    updated += 1

            logger.info(
                "🔍 [DRY-RUN] Would update %d/%d chunks (%d failed)",
                updated,
                total,
                failed,
            )
            return LateEmbeddingBackfillResult(
                total_examined=total,
                updated=0,  # dry-run: 0 actual update (audit "已写" 必须 = 0)
                failed=failed,
                dry_run=True,
                target=target,
                errors=errors,
            )

        # 真写库 (W-N-FILL 真派工时)
        updated = 0
        failed = 0
        errors: List[str] = []
        for chunk in chunks:
            encoded = await self._encode_chunk_to_pgvector(chunk["content"])
            if encoded is None:
                failed += 1
                if len(errors) < 10:
                    errors.append(f"chunk {chunk['id']}: encode failed")
                continue
            chunk_emb_array = "{" + ",".join(encoded) + "}"
            await self.db.execute(
                text(
                    "UPDATE knowledge_chunks "
                    "SET chunk_embedding = :chunk_emb::vector[], updated_at = NOW() "
                    "WHERE id = :chunk_id"
                ),
                {"chunk_emb": chunk_emb_array, "chunk_id": chunk["id"]},
            )
            updated += 1

        await self.db.commit()
        logger.warning(
            "🔄 [APPLY] Updated %d/%d chunks (%d failed)",
            updated,
            total,
            failed,
        )
        return LateEmbeddingBackfillResult(
            total_examined=total,
            updated=updated,
            failed=failed,
            dry_run=False,
            target=target,
            errors=errors,
        )

    async def backfill_for_knowledge(
        self,
        knowledge_id: int,
        *,
        dry_run: bool = True,
    ) -> LateEmbeddingBackfillResult:
        """单 knowledge 维度回填 (派工 brief 严禁真跑, 默认 dry_run=True)

        Args:
            knowledge_id: 单 knowledge mode (e.g. 5)
            dry_run: True = 只统计, 不写库 (默认)

        Returns:
            LateEmbeddingBackfillResult
        """
        target = f"knowledge:{knowledge_id}"
        chunks = await self._fetch_pending_chunks(knowledge_id=knowledge_id)
        if not chunks:
            return LateEmbeddingBackfillResult(
                total_examined=0,
                updated=0,
                dry_run=dry_run,
                target=target,
                errors=[f"knowledge {knowledge_id} has no pending chunks"],
            )

        if dry_run:
            updated = 0
            failed = 0
            errors: List[str] = []
            for chunk in chunks:
                encoded = await self._encode_chunk_to_pgvector(chunk["content"])
                if encoded is None:
                    failed += 1
                    if len(errors) < 10:
                        errors.append(f"chunk {chunk['id']}: encode failed")
                else:
                    updated += 1
            logger.info(
                "🔍 [DRY-RUN] knowledge %d would update %d/%d chunks",
                knowledge_id,
                updated,
                len(chunks),
            )
            return LateEmbeddingBackfillResult(
                total_examined=len(chunks),
                updated=0,
                failed=failed,
                dry_run=True,
                target=target,
                errors=errors,
            )

        # 真写库
        updated = 0
        failed = 0
        errors: List[str] = []
        for chunk in chunks:
            encoded = await self._encode_chunk_to_pgvector(chunk["content"])
            if encoded is None:
                failed += 1
                if len(errors) < 10:
                    errors.append(f"chunk {chunk['id']}: encode failed")
                continue
            chunk_emb_array = "{" + ",".join(encoded) + "}"
            await self.db.execute(
                text(
                    "UPDATE knowledge_chunks "
                    "SET chunk_embedding = :chunk_emb::vector[], updated_at = NOW() "
                    "WHERE id = :chunk_id"
                ),
                {"chunk_emb": chunk_emb_array, "chunk_id": chunk["id"]},
            )
            updated += 1
        await self.db.commit()
        logger.warning(
            "🔄 [APPLY] knowledge %d updated %d/%d chunks",
            knowledge_id,
            updated,
            len(chunks),
        )
        return LateEmbeddingBackfillResult(
            total_examined=len(chunks),
            updated=updated,
            failed=failed,
            dry_run=False,
            target=target,
            errors=errors,
        )
