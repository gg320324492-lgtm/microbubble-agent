"""SaveToKbService — W68 第 10 批 B-2 5 道防线 + 入库核心 (2026-07-24)

设计要点:
- 5 道防线:
  1. 分数门控: score >= MIN_SCORE (默认 4/5)
  2. 内容长度: content >= MIN_CONTENT_LENGTH (默认 200 字)
  3. 意图白名单: intent ∈ ALLOWED_INTENTS (explain_concept + search_info)
  4. 灰度开关: KB_INTAKE_GRAYSCALE > 0 或 AUTO_KB_INTAKE_ENABLED=true
  5. 实际入库: 调 KnowledgeService.create_from_auto_expansion
- 任一防线失败 → AutoIntakeRollbackService.record_failure(qa_id, failed_gate, ...)
- 5 道防线全过 → 入库 + 返回 success

设计纪律:
- 同步 API (无 async, 无 Celery import) → 业务层与调度层完全解耦
- service 函数签名接 (db: AsyncSession, ...) → 跨 event loop 安全
- 复用 KnowledgeService (alembic 058 knowledge.source_type=auto_expansion 已建)

与 save_to_kb.py (qa-bench runner 脚本) 区别:
- save_to_kb.py: CLI 入口 + 灰度切档 + 批量 POST /api/v1/knowledge/from-auto-expansion
- save_to_kb_service.py (本文件): 服务端入库逻辑, 调 KnowledgeService.create_from_auto_expansion
  + AutoIntakeRollbackService.record_failure
"""
import hashlib
import logging
import os
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auto_intake_rollback_service import AutoIntakeRollbackService
from app.models.knowledge_rejected import (
    GATE_CONTENT,
    GATE_GRAYSCALE,
    GATE_INTAKE_FLAG,
    GATE_INTENT,
    GATE_SCORE,
)

logger = logging.getLogger("microbubble.save_to_kb_service")

# 质量门 (与 API 端 AutoExpansionIngestRequest 默认值对齐)
DEFAULT_MIN_SCORE = 4
DEFAULT_MIN_CONTENT_LENGTH = 200
DEFAULT_ALLOWED_INTENTS = ("explain_concept", "search_info")

# W5 防线 4: 灰度开关 (从 env AUTO_KB_INTAKE_ENABLED 读, 默认 False 避免误触发)
AUTO_KB_INTAKE_ENABLED = os.environ.get("AUTO_KB_INTAKE_ENABLED", "false").lower() == "true"

# W62 D2: 灰度百分比 (0-100, 默认 0 完全跳过入库)
def _parse_grayscale_env() -> int:
    """解析 KB_INTAKE_GRAYSCALE env, 非法值降级为 0"""
    raw = os.environ.get("KB_INTAKE_GRAYSCALE", "0").strip()
    try:
        v = int(raw)
        if v < 0:
            return 0
        if v > 100:
            return 100
        return v
    except ValueError:
        return 0


KB_INTAKE_GRAYSCALE_ENV = _parse_grayscale_env()


def is_in_grayscale(qa_id: str, grayscale_pct: int) -> bool:
    """灰度命中判定: 同一 question_id 永远命中同一档, 跨多次跑一致

    Args:
        qa_id: 题号 (e.g. "S-001")
        grayscale_pct: 0-100 整数百分比

    Returns:
        True if 该题本次应进入入库路径
    """
    if grayscale_pct <= 0:
        return False
    if grayscale_pct >= 100:
        return True
    # 稳定 hash: SHA-256 前 8 hex 字符 → int → mod 100
    h = hashlib.sha256(qa_id.encode("utf-8")).hexdigest()[:8]
    bucket = int(h, 16) % 100
    return bucket < grayscale_pct


class SaveToKbService:
    """qa-bench 高分问答 → 自动拓展入库 5 道防线核心

    设计要点:
    - 与 save_to_kb.py (qa-bench runner 脚本) 解耦: 本 service 跑服务端入库逻辑
    - record_failure 调 AutoIntakeRollbackService.record_failure 写 knowledge_rejected
    - 复用 KnowledgeService.create_from_auto_expansion (alembic 058 已建 source_type)
    """

    def __init__(
        self,
        db: AsyncSession,
        *,
        min_score: int = DEFAULT_MIN_SCORE,
        min_content_length: int = DEFAULT_MIN_CONTENT_LENGTH,
        allowed_intents: tuple = DEFAULT_ALLOWED_INTENTS,
        grayscale_pct: Optional[int] = None,
    ):
        self.db = db
        self.min_score = min_score
        self.min_content_length = min_content_length
        self.allowed_intents = allowed_intents
        # grayscale 默认从 env 读 (允许 None 表示"按 env 自动")
        self.grayscale_pct = (
            grayscale_pct if grayscale_pct is not None else KB_INTAKE_GRAYSCALE_ENV
        )
        self.rollback_svc = AutoIntakeRollbackService(db)

    async def ingest_one(
        self,
        *,
        qa_id: str,
        question: str,
        content: str,
        score: int,
        intent: str,
        tool_calls: Optional[list] = None,
        rich_blocks: Optional[list] = None,
        scope: Optional[str] = None,
        created_by: Optional[int] = None,
        extra: Optional[dict] = None,
    ) -> dict:
        """5 道防线检查 + 入库

        Args:
            qa_id: qa-bench 业务 ID (S-001 格式)
            question: 题干
            content: 答案内容
            score: auto_score (0-5)
            intent: 意图分类
            tool_calls: 工具调用列表
            rich_blocks: Rich Block 列表
            scope: scope 标签
            created_by: 用户 ID (NULL = 系统)
            extra: 额外元数据

        Returns:
            dict: {
                "status": "ok"|"skipped"|"rejected",
                "qa_id": str,
                "failed_gate": str? (rejected 时),
                "knowledge_id": int? (ok 时),
                "rejected_id": int? (rejected 时),
                "reason": str?,
            }

        5 道防线顺序:
        1. score < min_score → rejected (GATE_SCORE)
        2. content < min_content_length → rejected (GATE_CONTENT)
        3. intent not in allowed_intents → rejected (GATE_INTENT)
        4. grayscale = 0 → rejected (GATE_GRAYSCALE)
        5. AUTO_KB_INTAKE_ENABLED=false → rejected (GATE_INTAKE_FLAG)
        全过 → 调 KnowledgeService.create_from_auto_expansion
        """
        # 防线 1: 分数门控
        if (score or 0) < self.min_score:
            await self._record_failure(
                qa_id=qa_id, question=question, content=content, score=score, intent=intent,
                failed_gate=GATE_SCORE,
                error_msg=f"score {score} < min_score {self.min_score}",
                extra=extra, created_by=created_by,
            )
            return {
                "status": "rejected",
                "qa_id": qa_id,
                "failed_gate": GATE_SCORE,
                "reason": f"score {score} < min_score {self.min_score}",
            }

        # 防线 2: 内容长度
        if not content or len(content) < self.min_content_length:
            await self._record_failure(
                qa_id=qa_id, question=question, content=content, score=score, intent=intent,
                failed_gate=GATE_CONTENT,
                error_msg=f"content length {len(content or '')} < {self.min_content_length}",
                extra=extra, created_by=created_by,
            )
            return {
                "status": "rejected",
                "qa_id": qa_id,
                "failed_gate": GATE_CONTENT,
                "reason": f"content length {len(content or '')} < {self.min_content_length}",
            }

        # 防线 3: 意图白名单
        if self.allowed_intents and intent not in self.allowed_intents:
            await self._record_failure(
                qa_id=qa_id, question=question, content=content, score=score, intent=intent,
                failed_gate=GATE_INTENT,
                error_msg=f"intent {intent!r} not in allowed {list(self.allowed_intents)}",
                extra=extra, created_by=created_by,
            )
            return {
                "status": "rejected",
                "qa_id": qa_id,
                "failed_gate": GATE_INTENT,
                "reason": f"intent {intent!r} not in allowed",
            }

        # 防线 4: 灰度开关
        if not is_in_grayscale(qa_id, self.grayscale_pct):
            await self._record_failure(
                qa_id=qa_id, question=question, content=content, score=score, intent=intent,
                failed_gate=GATE_GRAYSCALE,
                error_msg=f"grayscale_pct={self.grayscale_pct} skipped qa_id={qa_id}",
                extra={**(extra or {}), "grayscale_pct": self.grayscale_pct},
                created_by=created_by,
            )
            return {
                "status": "rejected",
                "qa_id": qa_id,
                "failed_gate": GATE_GRAYSCALE,
                "reason": f"grayscale_pct={self.grayscale_pct} skipped",
            }

        # 防线 5: AUTO_KB_INTAKE_ENABLED 总开关
        if not AUTO_KB_INTAKE_ENABLED and self.grayscale_pct < 100:
            # grayscale_pct 100 隐含 AUTO_KB_INTAKE_ENABLED=true
            await self._record_failure(
                qa_id=qa_id, question=question, content=content, score=score, intent=intent,
                failed_gate=GATE_INTAKE_FLAG,
                error_msg="AUTO_KB_INTAKE_ENABLED=false and grayscale<100",
                extra=extra, created_by=created_by,
            )
            return {
                "status": "rejected",
                "qa_id": qa_id,
                "failed_gate": GATE_INTAKE_FLAG,
                "reason": "AUTO_KB_INTAKE_ENABLED=false",
            }

        # 5 道防线全过 → 实际入库
        try:
            # 延迟 import 避免循环依赖
            from app.services.knowledge_service import KnowledgeService

            knowledge_service = KnowledgeService(self.db)
            knowledge = await knowledge_service.create_from_auto_expansion(
                qa_id=qa_id,
                question=question,
                content=content,
                scope=scope,
                score=score,
                intent=intent,
                tool_calls=tool_calls,
                rich_blocks=rich_blocks,
            )
            if knowledge:
                logger.info(
                    f"✅ [save_to_kb] ingested qa_id={qa_id!r} → knowledge_id={knowledge.id}"
                )
                return {
                    "status": "ok",
                    "qa_id": qa_id,
                    "knowledge_id": knowledge.id,
                }
            else:
                # KnowledgeService 内部幂等拒绝 (同 qa_id 已存在)
                return {
                    "status": "skipped",
                    "qa_id": qa_id,
                    "reason": "duplicate qa_id (already ingested)",
                }
        except Exception as exc:
            logger.error(
                f"❌ [save_to_kb] ingestion failed qa_id={qa_id!r}: {exc}",
                exc_info=True,
            )
            return {
                "status": "error",
                "qa_id": qa_id,
                "reason": str(exc)[:200],
            }

    async def retry_from_rejected(self, rejected) -> dict:
        """从 KnowledgeRejected 实例重试入库 (B-3 task 调用)

        Args:
            rejected: KnowledgeRejected ORM 实例

        Returns:
            dict: 同 ingest_one 返回格式

        设计要点:
        - 不传 grayscale (按 env 自动)
        - 复用 ingest_one 5 道防线 (重审, 失败再次写 rejected)
        """
        return await self.ingest_one(
            qa_id=rejected.qa_id,
            question=rejected.question or "",
            content=rejected.content or "",
            score=rejected.score or 0,
            intent=rejected.intent or "",
            scope=None,
            created_by=rejected.created_by,
            extra=rejected.extra or {},
        )

    async def _record_failure(
        self,
        *,
        qa_id: str,
        failed_gate: str,
        error_msg: str,
        question: Optional[str] = None,
        content: Optional[str] = None,
        score: Optional[int] = None,
        intent: Optional[str] = None,
        extra: Optional[dict] = None,
        created_by: Optional[int] = None,
    ) -> None:
        """5 道防线失败的统一入口 (调 AutoIntakeRollbackService.record_failure)"""
        try:
            await self.rollback_svc.record_failure(
                qa_id=qa_id,
                failed_gate=failed_gate,
                error_msg=error_msg,
                question=question,
                content=content,
                score=score,
                intent=intent,
                extra=extra,
                created_by=created_by,
            )
        except Exception as e:
            # record_failure 失败不应阻塞 ingest_one 返回
            logger.error(
                f"❌ [save_to_kb] record_failure failed qa_id={qa_id!r} gate={failed_gate!r}: {e}",
                exc_info=True,
            )