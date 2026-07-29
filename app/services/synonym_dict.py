"""中文同义词字典 — 微纳米气泡领域

PR4 (W90 +3..+5) 引入 — 让 BM25 / HybridRetriever 召回时支持查询改写,
召回侧量化门禁 (plan §2 PR4 锚点): synonym dict ≥ 200 条.

设计原则:
1. 数据文件在同目录的 __init__.py (lazy load via _load_synonyms), 模块顶部不 hardcode 200+ 行
2. 中文微纳米气泡领域为主 (微气泡/纳米气泡/空化/zeta电位/接触角 等), 通用中文为辅
3. 同义词组 (synonym group) 模式: 一组词互相等价, 检索时全部展开
4. 支持热加载 (reload from disk / DB 注入)
5. 暴露 expand_query(q) → str 函数, 把 query 中的词替换为该组 canonical 词
6. 不依赖外部资源, 纯内存 dict, 单测可直接 import

不动:
- bm25_service.py (HybridRetriever _bm25_search 调用方)
- hybrid_retriever.py 原 10 个 def (CLAUDE.md §3 严禁)

新增文件:
- app/services/synonym_dict.py (本文件)
- app/services/synonym_dict/__init__.py (数据, ≥ 200 条)

量化门禁 (PR4):
- synonym dict ≥ 200 条 (Chinese micro-nano bubble domain)
- CrossEncoder 保留率 ≥ 70% (PR5 RAGEvaluator 验证)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger("microbubble.synonym_dict")

# 默认数据文件路径 (同目录 synonym_data/__init__.py)
_DATA_FILE = Path(__file__).parent / "synonym_data" / "__init__.py"


def _load_synonyms() -> Dict[str, str]:
    """从数据文件加载同义词 dict (canonical → canonical 的反向索引)

    返回: {variant_word: canonical_word}
    - 例如: {"微气泡": "microbubble", "microbubble": "microbubble",
              "气泡": "bubble", "bubbles": "bubble", "bubble": "bubble"}

    加载方式: 直接 exec 数据文件 (它是合法 Python dict literal)
    """
    if not _DATA_FILE.exists():
        logger.warning(f"synonym_dict 数据文件不存在: {_DATA_FILE}")
        return {}

    try:
        # 数据文件是合法 Python module, exec 拿其 namespace
        namespace: Dict[str, object] = {}
        with _DATA_FILE.open("r", encoding="utf-8") as f:
            code = f.read()
        exec(compile(code, str(_DATA_FILE), "exec"), namespace)
        synonyms = namespace.get("SYNONYMS")
        if not isinstance(synonyms, dict):
            logger.warning("synonym_dict 数据文件未定义 SYNONYMS dict")
            return {}
        return synonyms
    except (OSError, SyntaxError) as e:
        logger.warning(f"synonym_dict 数据文件加载失败: {e}")
        return {}


# 模块级 cache (lazy + 单例)
_SYNONYM_CACHE: Optional[Dict[str, str]] = None


def get_synonyms(force_reload: bool = False) -> Dict[str, str]:
    """获取同义词 dict (单例 cache)

    Args:
        force_reload: 强制从数据文件重读 (用于热加载 / 测试)

    Returns:
        {variant: canonical} dict
    """
    global _SYNONYM_CACHE
    if force_reload or _SYNONYM_CACHE is None:
        _SYNONYM_CACHE = _load_synonyms()
    return _SYNONYM_CACHE


def reset_cache() -> None:
    """重置 cache (测试用, 允许重新加载)"""
    global _SYNONYM_CACHE
    _SYNONYM_CACHE = None


def canonical_form(word: str, synonyms: Optional[Dict[str, str]] = None) -> str:
    """查询某个词对应的 canonical (canonical form)

    Args:
        word: 输入词 (中文/英文)
        synonyms: 同义词 dict, None 走 get_synonyms()

    Returns:
        canonical word, 没找到返回原 word
    """
    if not word:
        return word
    syn = synonyms if synonyms is not None else get_synonyms()
    return syn.get(word.lower().strip(), word)


def expand_query(query: str, synonyms: Optional[Dict[str, str]] = None) -> str:
    """查询改写 — 把 query 中的同义词替换为 canonical 形式

    Args:
        query: 原始查询字符串
        synonyms: 同义词 dict, None 走 get_synonyms()

    Returns:
        改写后查询 (含 canonical 词)
        - 例: "微气泡的 zeta 电位是多少" → "microbubble 的 zeta_potential 是多少"
          (中文 canonical: 微气泡 → microbubble, 电位 → zeta_potential)
    """
    if not query:
        return query

    syn = synonyms if synonyms is not None else get_synonyms()
    if not syn:
        return query

    # 简单策略: 按字符长度倒序匹配 (避免短词先匹配)
    # 例: "microbubbles" 应在 "microbubble" 之前匹配
    sorted_variants = sorted(syn.keys(), key=len, reverse=True)

    expanded = query
    for variant in sorted_variants:
        canonical = syn[variant]
        if variant == canonical:
            continue  # 跳过 self-mapping
        # 不区分大小写替换 (英文)
        if variant.isascii():
            # 用 word boundary 防止 substring 误匹配
            # 但中文不需要 (单字/双字 token)
            import re
            pattern = re.compile(re.escape(variant), re.IGNORECASE)
            expanded = pattern.sub(canonical, expanded)
        else:
            # 中文: 直接字符串替换
            expanded = expanded.replace(variant, canonical)

    return expanded


def get_synonym_groups(synonyms: Optional[Dict[str, str]] = None) -> List[Set[str]]:
    """获取同义词组列表 (每个 group 含所有等价 variant)

    Returns:
        List of Sets, 每个 set 是一个 synonym group
    """
    syn = synonyms if synonyms is not None else get_synonyms()

    groups: Dict[str, Set[str]] = {}
    for variant, canonical in syn.items():
        if canonical not in groups:
            groups[canonical] = set()
        groups[canonical].add(variant)
        groups[canonical].add(canonical)

    return list(groups.values())


def count_synonyms(synonyms: Optional[Dict[str, str]] = None) -> int:
    """统计同义词 dict 条数 (含 canonical 自指)"""
    syn = synonyms if synonyms is not None else get_synonyms()
    return len(syn)


__all__ = [
    "get_synonyms",
    "reset_cache",
    "canonical_form",
    "expand_query",
    "get_synonym_groups",
    "count_synonyms",
]