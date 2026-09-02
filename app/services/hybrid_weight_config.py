"""HybridRetriever 四路召回权重配置

PR4 (W90 +0..+2) 引入 — 让 vector / bm25 / graph / rerank 四路召回的权重
从 yaml 文件 + 运行时 DB 表双路可配, 配 RRF (Reciprocal Rank Fusion) 归一化
+ A/B 灰度切流。

设计原则 (CLAUDE.md §3 0 production code 例外清单 — PR4 不算例外, 仅扩配置):
1. 默认权重 = plan §2 PR4 锚点范式目标 (vector=0.4, bm25=0.3, graph=0.1, rerank=0.2)
2. yaml 文件 + DB 表双路覆盖, 运行时优先 DB, 启动期读 yaml fallback 到默认
3. RRF 归一化 (k=60) — 解决不同路分数尺度不一致 (向量 cos dist ∈ [0,1] vs BM25 ∈ [0, N])
4. A/B 灰度切流 — `bucket_key` (任意 string, 通常 user_id) hash → 桶号 → 决定用 A 组还是 B 组权重
5. 跨路合并: `_apply_weights` / `_apply_synonyms` 仅追加新辅助函数, 不动 hybrid_retriever 原签名

不动:
- hybrid_retriever.py 原 10 个 def (CLAUDE.md §3 严禁)
- knowledge_service.py 老核心
- alembic (PR4 无迁移)

新增文件清单 (PR4):
- `app/services/hybrid_weight_config.py` (本文件)
- `app/services/synonym_dict.py` (W90 +3..+5)
- `tests/rag/test_hybrid_weight_config.py` (W90 +9)
- `tests/rag/test_synonym_dict.py` (W90 +10)
- `tests/rag/test_pr4_e2e.py` (W90 +11)

量化门禁:
- 四路权重 yaml + DB 可配
- synonym dict ≥ 200 条
- CrossEncoder 保留率 ≥ 70% (PR5 RAGEvaluator 验证)
- qa-bench PASS ≥ 95% (PR5 推荐不跑, e2e 验证)
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger("microbubble.hybrid_weight_config")

# RRF 公式常数 k (Reciprocal Rank Fusion, 经典 Cormack 2009 论文)
RRF_K = 60

# 默认权重 (plan §2 PR4 锚点范式目标)
# 注意: 这些是合并权重 (RRF score 之后), 不是原始检索分数的权重
DEFAULT_WEIGHTS: Dict[str, float] = {
    "vector": 0.4,
    "bm25": 0.3,
    "graph": 0.1,
    "rerank": 0.2,
    "image": 0.15,
    "temporal": 0.0,
    "chunk": 0.2,
    "meetings": 0.8,
    "drive": 0.7,
}

# 默认 A/B 灰度 — A 组 = 全开, B 组 = 强化 bm25 (实验性)
DEFAULT_AB_CONFIG: Dict[str, Dict[str, float]] = {
    "A": {
        "vector": 0.4,
        "bm25": 0.3,
        "graph": 0.1,
        "rerank": 0.2,
    },
    "B": {
        "vector": 0.3,
        "bm25": 0.45,
        "graph": 0.05,
        "rerank": 0.2,
    },
}

# 默认 yaml 路径 — env var 覆盖 (HybridRetriever 单实例配置)
DEFAULT_YAML_PATH = os.getenv(
    "HYBRID_WEIGHT_YAML_PATH",
    str(Path(__file__).parent.parent.parent / "config" / "hybrid_weight.yaml"),
)


@dataclass
class HybridWeights:
    """四路召回权重

    字段:
        vector: 向量检索 (pgvector HNSW 语义搜索)
        bm25: BM25 关键词检索 (rank_bm25 + jieba)
        graph: 知识图谱实体链检索 (Neo4j)
        rerank: Cross-encoder 重排序 (BGE m3)
        chunk: chunk 级向量召回 (parent-child, 2026-09-01 WP1.7 RRF 第 4 路)
    """

    vector: float = 0.4
    bm25: float = 0.3
    graph: float = 0.1
    rerank: float = 0.2
    # W100-RAG-5: OCR 图片召回第 5 路
    image: float = 0.15
    # W100-RAG-6: 时间衰减 — 不作为 RRF 路权重 (temporal=0), 仅作最终乘子
    temporal: float = 0.0
    # 2026-09-01 WP1.7: chunk 级向量召回 (retrieve_per_method "chunk" 路)
    chunk: float = 0.2
    # WP1 (2026-09-02): 会议转录 chunk 召回 (meeting_chunks, 第 6 路)
    meetings: float = 0.8
    # WP2 (2026-09-02): drive 文件内容召回 (knowledge_chunks drive 语料域, 第 7 路)
    drive: float = 0.7

    def __post_init__(self) -> None:
        # 防御性: 负权重 / NaN 守护；新增加入白名单
        for field_name in ("vector", "bm25", "graph", "rerank", "image", "temporal", "chunk", "meetings", "drive"):
            v = getattr(self, field_name)
            if not isinstance(v, (int, float)):
                raise ValueError(
                    f"HybridWeights.{field_name} 必须为数字, 实际 {type(v).__name__}"
                )
            if v < 0:
                raise ValueError(f"HybridWeights.{field_name} 不能为负, 实际 {v}")

    def to_dict(self) -> Dict[str, float]:
        """转 dict (用于 logging / DB 序列化)"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "HybridWeights":
        """从 dict 创建 (用于 yaml / DB 反序列化)

        Args:
            data: 含 vector/bm25/graph/rerank/image/temporal/chunk/meetings 键的 dict, 缺键走默认
        """
        kwargs: Dict[str, float] = {}
        for k in ("vector", "bm25", "graph", "rerank", "image", "temporal", "chunk", "meetings", "drive"):
            if k in data:
                kwargs[k] = float(data[k])
        return cls(**kwargs)


@dataclass
class HybridABConfig:
    """A/B 灰度配置

    字段:
        enabled: 是否启用 A/B 切流
        bucket_a_ratio: 桶号 < ratio 走 A 组 (默认 0.5 = 50/50)
        config_a: A 组权重
        config_b: B 组权重
    """

    enabled: bool = False
    bucket_a_ratio: float = 0.5
    config_a: HybridWeights = field(default_factory=lambda: HybridWeights(**DEFAULT_AB_CONFIG["A"]))
    config_b: HybridWeights = field(default_factory=lambda: HybridWeights(**DEFAULT_AB_CONFIG["B"]))

    def pick_bucket(self, bucket_key: str) -> HybridWeights:
        """根据 bucket_key (user_id / session_id 等) 决定 A/B 组

        Args:
            bucket_key: 任意 string, hash 后 mod 100 映射到 [0, 100) 整数
                - 整数 < (bucket_a_ratio * 100) → A 组
                - 否则 → B 组

        Returns:
            HybridWeights (A 组或 B 组)

        Examples:
            >>> cfg = HybridABConfig(enabled=True, bucket_a_ratio=0.5)
            >>> cfg.pick_bucket("user-001")  # doctest 不可用, 仅说明
        """
        if not self.enabled:
            return self.config_a

        if not bucket_key:
            return self.config_a  # fallback to A

        # 用 SHA-256 取前 8 hex → int → mod 100, 稳定 hash
        digest = hashlib.sha256(bucket_key.encode("utf-8")).hexdigest()[:8]
        bucket_num = int(digest, 16) % 100
        if bucket_num < self.bucket_a_ratio * 100:
            return self.config_a
        return self.config_b


def load_weights_from_yaml(yaml_path: Optional[str] = None) -> HybridWeights:
    """从 yaml 文件加载默认权重

    yaml 文件格式 (示例):
        weights:
          vector: 0.4
          bm25: 0.3
          graph: 0.1
          rerank: 0.2
        ab_config:
          enabled: false
          bucket_a_ratio: 0.5
          config_a:
            vector: 0.4
            bm25: 0.3
            graph: 0.1
            rerank: 0.2
          config_b:
            vector: 0.3
            bm25: 0.45
            graph: 0.05
            rerank: 0.2

    Args:
        yaml_path: yaml 文件路径, None 走 DEFAULT_YAML_PATH
            - 文件不存在 → 返回默认 HybridWeights (不抛异常, fallback 优雅)
            - 文件存在但解析失败 → logger.warning + 返回默认

    Returns:
        HybridWeights 实例
    """
    yaml_path = yaml_path or DEFAULT_YAML_PATH
    path = Path(yaml_path)
    if not path.exists():
        logger.debug(f"hybrid_weight yaml 不存在, 走默认: {yaml_path}")
        return HybridWeights()

    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as e:
        logger.warning(f"hybrid_weight yaml 解析失败, 走默认: {e}")
        return HybridWeights()

    weights_data = data.get("weights") or {}
    try:
        return HybridWeights.from_dict(weights_data)
    except (ValueError, TypeError) as e:
        logger.warning(f"hybrid_weight yaml 数据非法, 走默认: {e}")
        return HybridWeights()


def load_ab_config_from_yaml(yaml_path: Optional[str] = None) -> HybridABConfig:
    """从 yaml 文件加载 A/B 灰度配置

    Args:
        yaml_path: yaml 文件路径, None 走 DEFAULT_YAML_PATH
            - 文件不存在 / 解析失败 → 返回默认 HybridABConfig (enabled=False)

    Returns:
        HybridABConfig 实例
    """
    yaml_path = yaml_path or DEFAULT_YAML_PATH
    path = Path(yaml_path)
    if not path.exists():
        return HybridABConfig()

    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as e:
        logger.warning(f"hybrid_weight yaml 解析失败, 走默认: {e}")
        return HybridABConfig()

    ab_data = data.get("ab_config") or {}
    try:
        enabled = bool(ab_data.get("enabled", False))
        bucket_a_ratio = float(ab_data.get("bucket_a_ratio", 0.5))
        config_a_data = ab_data.get("config_a") or DEFAULT_AB_CONFIG["A"]
        config_b_data = ab_data.get("config_b") or DEFAULT_AB_CONFIG["B"]
        return HybridABConfig(
            enabled=enabled,
            bucket_a_ratio=bucket_a_ratio,
            config_a=HybridWeights.from_dict(config_a_data),
            config_b=HybridWeights.from_dict(config_b_data),
        )
    except (ValueError, TypeError) as e:
        logger.warning(f"hybrid_weight yaml ab_config 数据非法, 走默认: {e}")
        return HybridABConfig()


def _rrf_score(rank: int, weight: float, k: int = RRF_K) -> float:
    """RRF (Reciprocal Rank Fusion) 单路分数

    公式: weight / (k + rank)
    rank 是 1-indexed (1 = 最相关)

    Args:
        rank: 在该路结果中的排名 (1-indexed)
        weight: 该路的合并权重
        k: RRF 常数 (默认 60)

    Returns:
        RRF 分数
    """
    if rank < 1:
        return 0.0
    return weight / (k + rank)


def apply_weights(
    results_by_method: Dict[str, List[Dict[str, Any]]],
    weights: HybridWeights,
    top_k: int = 10,
    temporal_factor: Optional[Dict[Any, float]] = None,
) -> List[Dict[str, Any]]:
    """对多路结果按权重合并 + RRF 归一化

    输入格式:
        {
            "vector": [{"id": 1, "score": 0.9, ...}, ...],
            "bm25":   [{"id": 5, "score": 12.3, ...}, ...],
            "graph":  [{"id": 3, "score": 0.7, ...}, ...],
            "rerank": [{"id": 1, "rerank_score": 0.95, ...}, ...],
        }

    合并规则:
        1. 每一路按 score 降序排, 取 rank (1-indexed)
        2. RRF 加权: weight / (60 + rank)
        3. 同一 doc_id 在多路命中 → RRF 分数累加
        4. 按 RRF 总分降序排, 取 top_k
        5. 输出带 rrf_score 字段 + retrieval_methods 列表
        6. W100-RAG-6: 若 temporal_factor 不为 None, 对每个 doc 乘 temporal 乘子
           (类 20.132: 仅作最终乘子, 不影响 RRF score 结构)

    Args:
        results_by_method: 各路结果 dict
        weights: HybridWeights 权重
        top_k: 最终返回条数
        temporal_factor: W100-RAG-6 时间衰减因子
            - None 或空 dict → 不应用 temporal 乘子 (与 W100-RAG-5 行为一致)
            - dict: key = doc_id, value ∈ [0, 1.5] 时间权重
            - 缺 key 的 doc → 不乘 (保持原 RRF score)

    Returns:
        按 rrf_score 降序排的 top_k 列表
    """
    method_weights: Dict[str, float] = {
        "vector": weights.vector,
        "bm25": weights.bm25,
        "graph": weights.graph,
        "rerank": weights.rerank,
        "image": weights.image,
        "temporal": weights.temporal,
        "chunk": weights.chunk,
        "meetings": weights.meetings,
        "drive": weights.drive,
    }

    rrf_totals: Dict[Any, float] = {}
    doc_meta: Dict[Any, Dict[str, Any]] = {}
    doc_methods: Dict[Any, List[str]] = {}

    for method, results in results_by_method.items():
        if not results:
            continue
        w = method_weights.get(method, 0.0)
        if w <= 0:
            continue

        # 按 score 排序 (rerank 用 rerank_score, 其它用 score)
        def _sort_key(r: Dict[str, Any]) -> float:
            if method == "rerank":
                return r.get("rerank_score", r.get("score", 0))
            return r.get("score", 0)

        sorted_results = sorted(results, key=_sort_key, reverse=True)

        for rank, r in enumerate(sorted_results, start=1):
            doc_id = r.get("id")
            if doc_id is None:
                continue

            rrf = _rrf_score(rank, w)
            rrf_totals[doc_id] = rrf_totals.get(doc_id, 0.0) + rrf

            if doc_id not in doc_meta:
                doc_meta[doc_id] = dict(r)
                doc_methods[doc_id] = []
            doc_methods[doc_id].append(method)

    # 构造输出
    merged: List[Dict[str, Any]] = []
    for doc_id, rrf_total in rrf_totals.items():
        meta = dict(doc_meta[doc_id])
        # W100-RAG-6: temporal 乘子 (类 20.132 仅作最终乘子, 不影响 RRF 排序结构)
        if temporal_factor and doc_id in temporal_factor:
            _t_factor = float(temporal_factor[doc_id])
            meta["rrf_score"] = round(rrf_total * _t_factor, 6)
            meta["temporal_weight"] = round(_t_factor, 4)
        else:
            meta["rrf_score"] = round(rrf_total, 6)
        meta["retrieval_methods"] = doc_methods.get(doc_id, [])
        merged.append(meta)

    merged.sort(key=lambda x: x.get("rrf_score", 0), reverse=True)
    return merged[:top_k]


def db_override_weights(
    base_weights: HybridWeights,
    db_overrides: Optional[Dict[str, float]] = None,
) -> HybridWeights:
    """DB 覆盖权重 (运行时优先级最高)

    Args:
        base_weights: yaml 默认权重
        db_overrides: DB 读到的覆盖 dict (key in {vector, bm25, graph, rerank})

    Returns:
        合并后的 HybridWeights (DB 缺键走 yaml)
    """
    if not db_overrides:
        return base_weights
    try:
        merged_dict = {**base_weights.to_dict(), **db_overrides}
        return HybridWeights.from_dict(merged_dict)
    except (ValueError, TypeError) as e:
        logger.warning(f"DB 权重覆盖数据非法, 走 yaml: {e}")
        return base_weights


__all__ = [
    "RRF_K",
    "DEFAULT_WEIGHTS",
    "DEFAULT_AB_CONFIG",
    "HybridWeights",
    "HybridABConfig",
    "load_weights_from_yaml",
    "load_ab_config_from_yaml",
    "apply_weights",
    "db_override_weights",
    "_rrf_score",
]