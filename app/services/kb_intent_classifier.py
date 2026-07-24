"""KB intent classifier — 自动标 KB intent (W68 第 10 批 B-4, 2026-07-24)

## 背景

qa-bench 自动入库 (save_to_kb.py) 后, 写入的 KB 卡片的 **intent** 字段要么缺失要么
固定值 ("auto_expansion"), 缺业务级语义分类 (meeting / task / knowledge / member / project / drive / tool / feedback).

本服务复用 W68 第 10 批 B-2 `intelligence_classifier` (W69 派工) 的 8 类 intent 分类逻辑,
输出结构化的 `IntentCategory` 枚举 + confidence 分数.

## 8 类 intent (与 B-2 对齐)

| intent | 含义 | 示例 KB |
|--------|------|--------|
| meeting | 会议内容 / 决议 / 议程 | 例会纪要 / 课题组讨论 |
| task | 任务 / Todo / 项目子任务 | 数据采集任务 / 实验跑腿 |
| knowledge | 知识 / 论文 / 文献 / 综述 | 微纳米气泡文献综述 |
| member | 成员 / 人员 / 角色 | 课题组人员分工 |
| project | 项目 / 里程碑 / 立项 | 国家自然基金申报 |
| drive | 网盘 / 文件夹 / 文档 | 课题组共享资料 |
| tool | 工具 / API / 脚本 | OCR 脚本 / PDF 解析 |
| feedback | 反馈 / 评价 / 用户意见 | 用户反馈意见收集 |
| unclassified | confidence < 0.7, 标 unclassified 待人工 review |

## 设计

- `classify_intent(text) -> IntentCategory` 单条分类 (sync, 复用 B-2 LLM 调用)
- `batch_classify(texts) -> List[IntentCategory]` 批量 (并发, 限速)
- 纯函数 + 1 个可选 LLM client 注入 (走 B-2 的 intelligence_classifier 公共接口)
- confidence < 0.7 标 "unclassified" (8 类之外), 触发人工 review

## 调用方

- `app/services/kb_closed_loop_service.py` stage=STAGE_INTENT_CLASSIFY 时调
- 后续 PR: chat 工具调用直接走本服务, 不再调 B-2 LLM 单独路径

## 纪律

- 0 production code 改动铁律 (W68 第 10 批): 本服务 + 配套模型全部新增, 不动老路径
- 跨 event loop 安全 (CLAUDE.md 519/527 行铁律): LLM client 通过 `classifier` 注入, 模块顶部不创建
"""
from __future__ import annotations

import enum
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol

logger = logging.getLogger("microbubble.kb_intent_classifier")


# ============== IntentCategory 枚举 ==============

class IntentCategory(str, enum.Enum):
    """8 类 KB intent 分类 + unclassified 兜底"""

    MEETING = "meeting"
    TASK = "task"
    KNOWLEDGE = "knowledge"
    MEMBER = "member"
    PROJECT = "project"
    DRIVE = "drive"
    TOOL = "tool"
    FEEDBACK = "feedback"
    UNCLASSIFIED = "unclassified"  # confidence < 0.7 兜底


# 8 类白名单 (不含 unclassified)
CLASSIFIABLE_INTENTS = frozenset(
    i.value for i in IntentCategory if i != IntentCategory.UNCLASSIFIED
)

# confidence 阈值 (< 该值标 unclassified)
DEFAULT_CONFIDENCE_THRESHOLD = 0.7

# 批量并发上限
DEFAULT_BATCH_CONCURRENCY = 4

# LLM 调用超时 (秒)
DEFAULT_LLM_TIMEOUT_SEC = 30.0


# ============== Classifier Protocol (B-2 接口预留) ==============

class IntentClassifierProto(Protocol):
    """B-2 intelligence_classifier 的公共接口 (W69 派工)

    本服务通过 Protocol 兼容 B-2 实现, 不强制 import B-2 模块 (避免循环依赖).
    """

    async def classify(
        self,
        text: str,
        *,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """返回 {intent: str, confidence: float}

        B-2 实现示例:
            return {"intent": "knowledge", "confidence": 0.92}
        """
        ...


# ============== Classification Result ==============

@dataclass(frozen=True)
class IntentClassification:
    """分类结果 (含 confidence + 异常兜底)"""

    intent: IntentCategory
    confidence: float
    raw: Optional[Dict[str, Any]] = None  # B-2 LLM 返回原始 payload
    error: Optional[str] = None  # 异常信息 (status=failed 时填)

    @property
    def is_classified(self) -> bool:
        """是否为有效分类 (非 unclassified)"""
        return self.intent != IntentCategory.UNCLASSIFIED and self.error is None

    def to_log_metadata(self) -> Dict[str, Any]:
        """转 meta_data JSONB (kb_closed_loop_log.meta_data)"""
        out: Dict[str, Any] = {
            "intent": self.intent.value,
            "confidence": round(self.confidence, 3),
        }
        if self.raw:
            out["raw"] = self.raw
        if self.error:
            out["error"] = self.error
        return out


# ============== 纯函数 classifier ==============

def _normalize_intent(raw: str) -> IntentCategory:
    """LLM 返回字符串 → IntentCategory 枚举 (大写/小写/拼写兜底)"""
    s = (raw or "").strip().lower()
    # 直查
    for cat in IntentCategory:
        if cat.value == s:
            return cat
    # 拼写兜底 (LLM 偶发 typo)
    alias = {
        "kbase": IntentCategory.KNOWLEDGE.value,
        "doc": IntentCategory.DRIVE.value,
        "document": IntentCategory.DRIVE.value,
        "file": IntentCategory.DRIVE.value,
        "person": IntentCategory.MEMBER.value,
        "people": IntentCategory.MEMBER.value,
        "user": IntentCategory.MEMBER.value,
        "milestone": IntentCategory.PROJECT.value,
        "agenda": IntentCategory.MEETING.value,
        "summary": IntentCategory.MEETING.value,
        "todo": IntentCategory.TASK.value,
        "review": IntentCategory.FEEDBACK.value,
        "comment": IntentCategory.FEEDBACK.value,
    }
    if s in alias:
        return IntentCategory(alias[s])
    return IntentCategory.UNCLASSIFIED


def _apply_threshold(
    intent: IntentCategory,
    confidence: float,
    *,
    threshold: float,
) -> IntentCategory:
    """低于阈值降级为 unclassified"""
    if confidence < threshold and intent != IntentCategory.UNCLASSIFIED:
        logger.debug(
            "kb_intent_classifier confidence %.3f < threshold %.3f, "
            "降级 %s -> unclassified",
            confidence, threshold, intent.value,
        )
        return IntentCategory.UNCLASSIFIED
    return intent


# ============== 主入口 ==============

async def classify_intent(
    text: str,
    *,
    classifier: Optional[IntentClassifierProto] = None,
    threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    timeout: Optional[float] = DEFAULT_LLM_TIMEOUT_SEC,
) -> IntentClassification:
    """对单条 KB 文本分类

    Args:
        text: KB 标题 + 内容 (推荐拼接: title + "\n" + content[:1000])
        classifier: B-2 intelligence_classifier 实例 (可选, 默认用占位实现)
        threshold: confidence 阈值, 低于此值标 unclassified
        timeout: LLM 调用超时 (秒, 默认 30)

    Returns:
        IntentClassification (含 intent + confidence + error)
    """
    if not text or not text.strip():
        return IntentClassification(
            intent=IntentCategory.UNCLASSIFIED,
            confidence=0.0,
            error="empty_text",
        )

    impl = classifier or _PlaceholderClassifier()
    try:
        result = await impl.classify(text, timeout=timeout)
    except Exception as exc:  # LLM 调用异常兜底
        logger.warning(
            "kb_intent_classifier LLM 调用失败: %s, 降级 unclassified",
            exc,
        )
        return IntentClassification(
            intent=IntentCategory.UNCLASSIFIED,
            confidence=0.0,
            error=f"llm_error: {exc.__class__.__name__}",
        )

    if not isinstance(result, dict):
        return IntentClassification(
            intent=IntentCategory.UNCLASSIFIED,
            confidence=0.0,
            error=f"invalid_result_type: {type(result).__name__}",
        )

    raw_intent = result.get("intent", "unclassified")
    confidence = float(result.get("confidence", 0.0) or 0.0)

    intent = _normalize_intent(raw_intent)
    intent = _apply_threshold(intent, confidence, threshold=threshold)

    return IntentClassification(
        intent=intent,
        confidence=confidence,
        raw=result,
    )


async def batch_classify(
    texts: List[str],
    *,
    classifier: Optional[IntentClassifierProto] = None,
    threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    concurrency: int = DEFAULT_BATCH_CONCURRENCY,
    timeout: Optional[float] = DEFAULT_LLM_TIMEOUT_SEC,
) -> List[IntentClassification]:
    """批量分类 (并发限速)

    Args:
        texts: 多条 KB 文本
        concurrency: 并发上限 (默认 4, 避免 LLM 限速)
        timeout: 每条 LLM 调用超时

    Returns:
        与 texts 同序的 IntentClassification 列表
    """
    import asyncio

    sem = asyncio.Semaphore(max(1, concurrency))

    async def _one(t: str) -> IntentClassification:
        async with sem:
            return await classify_intent(
                t,
                classifier=classifier,
                threshold=threshold,
                timeout=timeout,
            )

    return await asyncio.gather(*[_one(t) for t in texts])


# ============== 占位实现 (B-2 未就绪时兜底) ==============

class _PlaceholderClassifier:
    """B-2 intelligence_classifier 尚未派工时的占位实现

    - 不调 LLM, 简单基于关键词猜 intent
    - B-2 派工后, 调用方注入真正的 classifier 实例即可替换
    - 永远返回 confidence < threshold → 全部标 unclassified → 触发人工 review
    """

    async def classify(
        self,
        text: str,
        *,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        # 启发式: 基于关键词粗判 intent (置信度低, 触发人工 review)
        lower = text.lower()
        if any(k in lower for k in ("会议", "meeting", "议程", "纪要")):
            intent = "meeting"
        elif any(k in lower for k in ("任务", "task", "todo", "待办")):
            intent = "task"
        elif any(k in lower for k in ("成员", "member", "人员", "同学", "老师")):
            intent = "member"
        elif any(k in lower for k in ("项目", "project", "基金", "立项")):
            intent = "project"
        elif any(k in lower for k in ("网盘", "drive", "文件夹", "folder")):
            intent = "drive"
        elif any(k in lower for k in ("工具", "tool", "脚本", "api")):
            intent = "tool"
        elif any(k in lower for k in ("反馈", "feedback", "评价", "意见")):
            intent = "feedback"
        else:
            intent = "knowledge"
        # 占位实现故意返回低 confidence, 让 service 层走人工 review
        return {"intent": intent, "confidence": 0.5}


# ============== 工厂 ==============

def build_classifier_from_settings() -> Optional[IntentClassifierProto]:
    """从 settings 构造 classifier (B-2 派工前返回 None, 走占位)

    Returns:
        - None: B-2 未就绪, 走 _PlaceholderClassifier
        - IntentClassifierProto: B-2 已就绪, 用真实现
    """
    try:
        # B-2 派工后, 这里 import 真正的 intelligence_classifier
        from app.services.intelligence_classifier import (  # noqa: F401
            intelligence_classifier,
        )
        return intelligence_classifier  # type: ignore[return-value]
    except ImportError:
        logger.info(
            "intelligence_classifier 未就绪 (B-2 派工前), 走 _PlaceholderClassifier"
        )
        return None