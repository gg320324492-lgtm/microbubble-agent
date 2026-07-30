"""中文分词器 (PR3 W89 +1)

PR3 选 jieba:
- 选 jieba 而非 pg_jieba/zhparser: 应用层纯逻辑可单测, 不依赖 DB 扩展
  (派工 v11 §Q4 + plan v1.1 §3.7 纪律: 新逻辑落纯逻辑层可单测 import, 不落 embedding_service.py)
- 已有 bm25_service 用 jieba (app/services/bm25_service.py:11), 一致性
- 性能: 中文长文档 jieba 切分 ~50ms/1KB, tsvector 入库 token 化可复用

边界:
- 入库文本需先 truncate_for_embedding (PR1) 再 token 化
- BM25 + tsvector 共享 token 化路径, 但 BM25 走 jieba 切词, tsvector 走 PG simple config
  (BM25 token = jieba 切词列表; tsvector = PG 默认 simple/english 词根)
- 命中率 ±5% 门禁见 test_pr3_e2e.py case-10

派工 v10 §2: type hint 完整 + 新加字段 keyword-only + Optional 默认 None
派工 v10 §13 铁律 6: 不动 bm25_service 既有函数, 仅共用 stopwords 常量
"""

import logging
import re
from typing import List, Optional

logger = logging.getLogger("microbubble.text_splitter")

# PR3 与 bm25_service 共用 stopwords (复用 app/services/bm25_service.py:17-30 STOP_WORDS)
# 此处不复制常量, 走 import (避免双源不一致)
try:
    from app.services.bm25_service import STOP_WORDS as _BM25_STOP_WORDS
except ImportError:  # 极端情况下 bm25_service 未导入 (如 sentence_transformers importorskip 期间)
    _BM25_STOP_WORDS = set()

# PR1 截断入口 (复用 plan §3.7 + PR1 实测纪律)
try:
    from app.services.embedding_truncation_policy import truncate_for_embedding
except ImportError:
    truncate_for_embedding = None  # type: ignore[assignment]


def tokenize_chinese(text: str, *, lowercase: bool = True) -> List[str]:
    """中文分词入口 (PR3 W89 +1)

    输入: 任意 utf-8 文本
    输出: 切词后 token 列表 (过滤停用词 + 单字符 + 纯数字 + 标点)

    与 bm25_service._tokenize 区别:
    - bm25_service._tokenize 是 BM25 内部 helper (私有名, 类内部)
    - 本函数是 PR3 公共 API, tsvector 入库 token 化复用
    - 行为一致: 同一文本经过两个函数应输出相同 token 列表
      (gate e2e case-09 验证 ±0 差异)

    Args:
        text: 输入文本
        lowercase: 是否 lowercase (默认 True, 与 bm25_service 一致)

    Returns:
        token 列表 (List[str])
    """
    if not text or not text.strip():
        return []

    # 清洗: 保留中英文和数字 (与 bm25_service._tokenize 一致)
    text = re.sub(r"[^一-鿿\w]+", " ", text)

    # 延迟 import jieba (避免 importorskip 期间模块级失败)
    try:
        import jieba  # type: ignore
    except ImportError as e:
        logger.warning(f"[text_splitter] jieba 未安装: {e}, 退化为字符切分")
        return _fallback_tokenize(text, lowercase=lowercase)

    tokens = list(jieba.cut(text))
    out: List[str] = []
    for t in tokens:
        token = t.strip()
        if not token:
            continue
        if lowercase:
            token = token.lower()
        # 过滤: 停用词 + 单字符 + 纯数字
        if token in _BM25_STOP_WORDS:
            continue
        if len(token) <= 1:
            continue
        if token.isdigit():
            continue
        out.append(token)
    return out


def _fallback_tokenize(text: str, *, lowercase: bool = True) -> List[str]:
    """jieba 不可用时的字符级兜底 (用于本机未装 jieba 跑测试)

    按"单字符 + 2 字符组合"切分, 与 jieba 行为不等但保证 import 不崩。
    仅 dev/test 期间触发, 生产环境必装 jieba (派工 v11 §Q4 沿用)。

    行为约束 (与 jieba 路径一致):
    - 过滤单字符 (length <= 1)
    - 过滤纯数字
    - 过滤停用词
    - 输出 lowercase
    """
    cleaned = re.sub(r"[^一-鿿\w]+", " ", text)
    if lowercase:
        cleaned = cleaned.lower()
    tokens = cleaned.split()
    out: List[str] = []
    for t in tokens:
        # 与 jieba 路径一致的过滤: 停用词 + 单字符 + 纯数字
        if t in _BM25_STOP_WORDS:
            continue
        if len(t) <= 1:
            continue
        if t.isdigit():
            continue
        out.append(t)
    return out


def tokens_to_tsvector_input(tokens: List[str]) -> str:
    """将 token 列表转为 PG tsvector 入库字符串 (PR3 W89 +1 配套)

    输入: token 列表
    输出: 空格分隔的 token 字符串 (PG `to_tsvector('simple', $1)` 接受)

    Args:
        tokens: tokenize_chinese() 输出

    Returns:
        空格分隔字符串, 适合 to_tsvector('simple', $1)
    """
    if not tokens:
        return ""
    # PG tsvector 接受空格分隔, 单 token 不带空格
    return " ".join(t for t in tokens if t)


def split_for_tsvector(
    text: str,
    *,
    max_chars: Optional[int] = 6000,
    lowercase: bool = True,
) -> str:
    """PR3 tsvector 入库一站式入口 (供 knowledge_service 钩子调用)

    流程:
        1. truncate_for_embedding (PR1 统一截断, 默认 6000 字符)
        2. tokenize_chinese (本模块)
        3. tokens_to_tsvector_input (输出 PG tsvector 字符串)

    Args:
        text: 原始文本
        max_chars: 截断上限, 默认 6000 (PR1 常量复用); None = 不截
        lowercase: token lowercase, 默认 True

    Returns:
        tsvector 输入字符串 (PG `to_tsvector('simple', $1)` 可消费)
    """
    if not text:
        return ""
    # 1. 截断 (复用 PR1 入口)
    if max_chars is not None and truncate_for_embedding is not None:
        text = truncate_for_embedding(text)
    elif max_chars is not None and len(text) > max_chars:
        text = text[:max_chars]
    # 2. 切词
    tokens = tokenize_chinese(text, lowercase=lowercase)
    # 3. 拼 tsvector 入库字符串
    return tokens_to_tsvector_input(tokens)