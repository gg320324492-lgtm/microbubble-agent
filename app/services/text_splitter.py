"""中文分词器 (PR3 W89 +1)

PR3 选 jieba:
- 选 jieba 而非 pg_jieba/zhparser: 应用层纯逻辑可单测, 不依赖 DB 扩展
  (派工 v11 §Q4 + plan v1.1 §3.7 纪律: 新逻辑落纯逻辑层可单测 import, 不落 embedding_service.py)
- 已有 bm25_service 用 jieba (app/services/bm25_service.py:11), 一致性
- 性能: 中文长文档 jieba 切分 ~50ms/1KB, tsvector 入库 token 化可复用

边界:
- 入库文本需先 truncate_for_embedding (PR1) 再 token 化
- **split_for_tsvector 的 max_chars 是"输出预算"** (2026-10-09 agent24 修正):
  jieba 切词 + 空格拼接会让长度膨胀 20%-60%, 只按输入截断会撞
  `ck_knowledge_search_text_len (length <= 6000)` 导致入库钩子 except 吞异常、
  search_text 静默留空。现按 **token 边界** 裁剪输出, 保证 len(out) <= max_chars
  且不产生半个词。详见 split_for_tsvector docstring 的语义变更段
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


def _fit_tokens_to_budget(tokens: List[str], max_chars: Optional[int]) -> str:
    """把 token 列表拼成字符串并**按 token 边界**裁剪到 max_chars 字符内

    为什么需要它 (2026-10-09 agent24 事故):
        `" ".join(tokens)` 会在每两个 token 之间插入 1 个分隔空格。中文 jieba
        平均词长 ~1.5-2.5 字, 即**每 1.5-2 个字符就要补一个空格**, 拼接结果
        系统性膨胀 20%-60% (实测 5400 字原文 -> 6599 字输出, +22%)。
        若只按**输入**长度截断 (旧 split_for_tsvector 行为), 输出必然可以
        超过 `ck_knowledge_search_text_len CHECK (length(search_text) <= 6000)`。

    为什么按 token 边界而不是 `s[:max_chars]`:
        字符级硬切会从词中间劈开 (实测留下 "核心 水质 传" 这种半词),
        PG to_tsvector 会把半词当独立 lexeme 建索引 -> 污染召回 + 浪费索引空间。
        本函数逐 token 累加, **只输出完整 token**, 且保留**前缀**语义
        (与旧的 "取原文前 N 字符" 一致: 文档开头的信息优先保留)。

    Args:
        tokens: tokenize_chinese() 输出
        max_chars: 输出预算 (字符数); None = 不裁剪 (调用方显式放弃上限)

    Returns:
        空格分隔字符串, 保证 len(out) <= max_chars (max_chars 非 None 时);
        每个空格分隔段都是**完整 token** (不会出现半个词)。
    """
    if max_chars is None:
        return tokens_to_tsvector_input(tokens)

    kept: List[str] = []
    used = 0  # 已用字符数 (= " ".join(kept) 的长度)
    for t in tokens:
        if not t:
            continue
        # 首个 token 不带前导空格, 之后每个都多 1 个分隔符
        cost = len(t) + (1 if kept else 0)
        if used + cost > max_chars:
            # 预算耗尽 -> 停在这里 (保留前缀, 不再往下找更短的 token 填空)
            break
        kept.append(t)
        used += cost
    return " ".join(kept)


def split_for_tsvector(
    text: str,
    *,
    max_chars: Optional[int] = 6000,
    lowercase: bool = True,
) -> str:
    """PR3 tsvector 入库一站式入口 (供 knowledge_service 钩子调用)

    流程:
        1. 输入预截断 (PR1 统一截断, 再按 max_chars 收紧)
        2. tokenize_chinese (本模块)
        3. tokens_to_tsvector_input (输出 PG tsvector 字符串)
        4. **输出预算裁剪** (按 token 边界, 保证 len(out) <= max_chars)

    ⚠️ max_chars 语义变更 (2026-10-09, agent24)
    ------------------------------------------------
    修复**前** max_chars 只作用于**输入**: `truncate_for_embedding(text)` 取原文
    前 6000 字 -> jieba 切词 -> 空格拼接, 输出**可以 > 6000**。撞库约束
    `ck_knowledge_search_text_len (search_text IS NULL OR length(search_text) <= 6000)`
    -> 抛异常 -> 被 3 个入库钩子的 `except` **吞成 warning** -> 表现为
    **search_text 静默留空** (全文检索通道对该文档彻底失效, 无任何报错)。

    修复**前**还有第二个更隐蔽的问题: `truncate_for_embedding` 分支
    **完全忽略 max_chars**, 硬编码走 MAX_EMBED_INPUT_CHARS=6000。
    实测 `split_for_tsvector('a'*8000, max_chars=100)` 返回 6000 字符 —— 调小
    max_chars 根本不生效 (而 fallback 分支却是**尊重** max_chars 的,
    两条分支语义不一致)。

    修复**后** max_chars = **最终输出预算 (字符数)**, 同时作为输入预截断上限:
        - 输出: 保证 len(out) <= max_chars, 且按 **token 边界**裁剪 (无半个词)
        - 输入: 仍先走 PR1 统一入口 truncate_for_embedding, 再按 max_chars 收紧
          (输入 <= max_chars 时第二步是 no-op, 与旧默认行为逐字节一致)

    对调用方是否透明: **透明**。3 个调用方
    (`knowledge_service.py:63` / `:208` / `rag_auto_ingest_service.py:161`)
    全部使用默认值 6000, 恰好等于 CHECK 上限 —— 语义变更不影响它们。

    Args:
        text: 原始文本
        max_chars: **输出**预算 (字符数), 默认 6000 (与 CHECK 约束同值);
            None = 不裁剪 (输出长度无上限, 调用方自行负责)
        lowercase: token lowercase, 默认 True

    Returns:
        tsvector 输入字符串 (PG `to_tsvector('simple', $1)` 可消费);
        max_chars 非 None 时保证 len(out) <= max_chars。
        输出是**空格分隔的完整 token 串**, 不是 JSON —— 下游只经
        `content_tsvector GENERATED ALWAYS AS (to_tsvector('simple', coalesce(search_text,'')))`
        消费, 不存在"截出非法 JSON"的风险。
    """
    if not text:
        return ""
    # 1. 输入预截断 (复用 PR1 入口 + 按 max_chars 收紧)
    #    注: 顺序不可颠倒 —— 必须先走 truncate_for_embedding 保持 PR1 统一口径
    if max_chars is not None:
        if truncate_for_embedding is not None:
            text = truncate_for_embedding(text)
        if len(text) > max_chars:
            text = text[:max_chars]
    # 2. 切词
    tokens = tokenize_chinese(text, lowercase=lowercase)
    # 3. 拼 tsvector 入库字符串 + 按 token 边界裁剪到输出预算
    return _fit_tokens_to_budget(tokens, max_chars)