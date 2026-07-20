"""Embedding prompt 工具 (2026-07-20 实装 query prompt)

本模块是纯逻辑层，无 sentence_transformers 重型依赖，可被单测直接 import。
设计上从 app.services.embedding_service 拆出，避免测试时加载 500MB+ 模型依赖。
"""
from typing import Optional

# 2026-07-20: query/document 不对称检索 prefix
# Qwen3-Embedding-0.6B / BGE-m3 等 instruction-tuned 模型需要 query 侧加指令前缀
# （"为这个句子生成表示以用于检索相关文章"）让 query embedding 偏向"问题"语义，
# document 侧不加（前缀会污染入库向量）。bge-m3 / Qwen3 推荐 prefix。
#
# ⚠️ 铁律：常量值一旦发布即固化。修改内容意味着所有历史入库向量全部失效
#    （prefix 是 embedding 模型输入的一部分，向量空间与 prefix 强绑定）。
#    如需更换 prefix，必须配套全量 re-embed 数据库。
QUERY_PROMPT_ZH = "为这个句子生成表示以用于检索相关文章:"


def build_embedding_prompt(for_query: bool, has_query_prompt: bool) -> Optional[str]:
    """根据模型能力 + 用途构造 embedding prefix

    Args:
        for_query: 当前调用是 query 侧（检索匹配）还是 document 侧（入库）
        has_query_prompt: 当前模型是否支持 query prefix（instruction-tuned 才行，
                          纯无监督模型加 prefix 会污染向量）

    Returns:
        prefix 字符串（for_query + supported）或 None（document 模式 / 不支持 prefix）

    Examples:
        >>> build_embedding_prompt(False, False)  # document 模式默认
        None
        >>> build_embedding_prompt(True, True)    # query 模式 + Qwen3/BGE
        '为这个句子生成表示以用于检索相关文章:'
        >>> build_embedding_prompt(True, False)   # 模型不支持 prefix
        None
        >>> build_embedding_prompt(False, True)   # document 不加 prefix
        None
    """
    if for_query and has_query_prompt:
        return QUERY_PROMPT_ZH
    return None
