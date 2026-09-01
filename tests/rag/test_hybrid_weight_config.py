"""PR4 hybrid_weight_config 单测 (W90 +9)

门禁: 5 件套 件 2 (pytest PR4 e2e 22/22 PASS)

不动: hybrid_retriever.py 原 10 个 def, knowledge_service.py, alembic
"""

import pytest

from app.services.hybrid_weight_config import (
    DEFAULT_AB_CONFIG,
    DEFAULT_WEIGHTS,
    HybridABConfig,
    HybridWeights,
    RRF_K,
    _rrf_score,
    apply_weights,
    db_override_weights,
    load_ab_config_from_yaml,
    load_weights_from_yaml,
)


class TestHybridWeightsDataclass:
    """HybridWeights dataclass 单测"""

    def test_default_weights_sum_to_one(self) -> None:
        """默认权重必须 sum = 1.0"""
        w = HybridWeights()
        total = w.vector + w.bm25 + w.graph + w.rerank
        assert abs(total - 1.0) < 1e-6, f"权重 sum != 1.0, 实际 {total}"

    def test_to_dict_returns_all_four_keys(self) -> None:
        """to_dict 必须含全部 7 个 key (4 路 + image + temporal + chunk, 2026-09-01 WP1.7)"""
        d = HybridWeights().to_dict()
        assert set(d.keys()) == {"vector", "bm25", "graph", "rerank", "image", "temporal", "chunk"}

    def test_from_dict_with_all_keys(self) -> None:
        """from_dict 全键构造"""
        w = HybridWeights.from_dict({"vector": 0.5, "bm25": 0.2, "graph": 0.1, "rerank": 0.2})
        assert w.vector == 0.5
        assert w.bm25 == 0.2

    def test_from_dict_missing_keys_uses_default(self) -> None:
        """from_dict 缺键走默认"""
        w = HybridWeights.from_dict({"vector": 0.7})
        assert w.vector == 0.7
        assert w.bm25 == 0.3  # 默认
        assert w.graph == 0.1
        assert w.rerank == 0.2

    def test_negative_weight_raises(self) -> None:
        """负权重必报错"""
        with pytest.raises(ValueError, match="不能为负"):
            HybridWeights(vector=-0.1)

    def test_non_numeric_weight_raises(self) -> None:
        """非数字权重必报错"""
        with pytest.raises(ValueError, match="必须为数字"):
            HybridWeights(vector="not a number")  # type: ignore[arg-type]


class TestHybridABConfig:
    """HybridABConfig A/B 灰度单测"""

    def test_default_disabled(self) -> None:
        """默认 disabled"""
        ab = HybridABConfig()
        assert ab.enabled is False

    def test_pick_bucket_disabled_returns_a(self) -> None:
        """disabled 时永远返 A"""
        ab = HybridABConfig(enabled=False)
        assert ab.pick_bucket("user-001") == ab.config_a
        assert ab.pick_bucket("user-002") == ab.config_a

    def test_pick_bucket_enabled_stable(self) -> None:
        """enabled 时同一 bucket_key 稳定返 A/B"""
        ab = HybridABConfig(enabled=True, bucket_a_ratio=0.5)
        # SHA-256 稳定: 同一 key 多次调用结果一致
        first = ab.pick_bucket("user-001")
        second = ab.pick_bucket("user-001")
        assert first == second

    def test_pick_bucket_empty_key_falls_back_to_a(self) -> None:
        """空 bucket_key fallback 到 A"""
        ab = HybridABConfig(enabled=True, bucket_a_ratio=0.5)
        assert ab.pick_bucket("") == ab.config_a

    def test_pick_bucket_distribution(self) -> None:
        """A/B 分布: 1000 个不同 key, A 组应在 50% ± 10% 范围内"""
        ab = HybridABConfig(enabled=True, bucket_a_ratio=0.5)
        a_count = 0
        b_count = 0
        for i in range(1000):
            if ab.pick_bucket(f"user-{i:04d}") == ab.config_a:
                a_count += 1
            else:
                b_count += 1
        a_ratio = a_count / 1000
        assert 0.40 <= a_ratio <= 0.60, f"A 组分布偏离: {a_ratio:.2%}"


class TestRRFScore:
    """RRF 公式单测"""

    def test_rrf_k_constant_is_60(self) -> None:
        """RRF_K = 60 (Cormack 2009 经典常数)"""
        assert RRF_K == 60

    def test_rrf_score_rank_1(self) -> None:
        """rank=1: weight / (60+1) = weight / 61"""
        score = _rrf_score(rank=1, weight=0.4)
        assert abs(score - 0.4 / 61) < 1e-9

    def test_rrf_score_rank_invalid(self) -> None:
        """rank < 1 必返 0"""
        assert _rrf_score(rank=0, weight=0.4) == 0.0
        assert _rrf_score(rank=-1, weight=0.4) == 0.0


class TestApplyWeights:
    """apply_weights 多路合并单测"""

    def test_apply_weights_empty_input(self) -> None:
        """空输入返空列表"""
        assert apply_weights({}, HybridWeights(), top_k=10) == []

    def test_apply_weights_single_method(self) -> None:
        """单路 (vector) RRF 合并"""
        results = {
            "vector": [
                {"id": 1, "score": 0.9},
                {"id": 2, "score": 0.5},
            ],
        }
        merged = apply_weights(results, HybridWeights(), top_k=10)
        assert len(merged) == 2
        # rank 1 必在 rank 2 之前 (rrf_score 降序)
        assert merged[0]["id"] == 1
        assert merged[1]["id"] == 2
        # retrieval_methods 标注
        assert merged[0]["retrieval_methods"] == ["vector"]
        assert merged[1]["retrieval_methods"] == ["vector"]

    def test_apply_weights_multi_method_dedup(self) -> None:
        """多路命中同 doc_id → RRF 分数累加"""
        results = {
            "vector": [{"id": 1, "score": 0.9}, {"id": 2, "score": 0.5}],
            "bm25": [{"id": 1, "score": 12.0}, {"id": 3, "score": 8.0}],
        }
        merged = apply_weights(results, HybridWeights(), top_k=10)
        # doc_id=1 同时在 vector 和 bm25 → retrieval_methods 应含两者
        doc1 = next(m for m in merged if m["id"] == 1)
        assert set(doc1["retrieval_methods"]) == {"vector", "bm25"}
        # doc_id=1 因命中两路, rrf_score 应 > 单路 doc_id=2/3
        assert merged[0]["id"] == 1

    def test_apply_weights_zero_weight_method_ignored(self) -> None:
        """权重为 0 的路被忽略"""
        w = HybridWeights(vector=0.4, bm25=0.0, graph=0.1, rerank=0.5)
        results = {
            "vector": [{"id": 1, "score": 0.9}],
            "bm25": [{"id": 2, "score": 12.0}],  # 权重 0, 应被忽略
        }
        merged = apply_weights(results, w, top_k=10)
        ids = {m["id"] for m in merged}
        assert 2 not in ids  # bm25 路被忽略

    def test_apply_weights_top_k_limit(self) -> None:
        """top_k 截断"""
        results = {"vector": [{"id": i, "score": 1.0 / (i + 1)} for i in range(20)]}
        merged = apply_weights(results, HybridWeights(), top_k=5)
        assert len(merged) == 5


class TestYamlLoading:
    """yaml 加载单测 (文件不存在 / 数据非法 fallback)"""

    def test_load_weights_yaml_not_exists_returns_default(self) -> None:
        """yaml 不存在 → 返默认"""
        w = load_weights_from_yaml(yaml_path="/nonexistent/path.yaml")
        assert w == HybridWeights()

    def test_load_ab_yaml_not_exists_returns_default(self) -> None:
        """yaml 不存在 → 返默认 disabled"""
        ab = load_ab_config_from_yaml(yaml_path="/nonexistent/path.yaml")
        assert ab.enabled is False

    def test_load_weights_yaml_invalid_returns_default(self, tmp_path) -> None:
        """yaml 非法 → 返默认 (不抛)"""
        invalid = tmp_path / "bad.yaml"
        invalid.write_text("not a yaml: [unclosed", encoding="utf-8")
        w = load_weights_from_yaml(yaml_path=str(invalid))
        assert w == HybridWeights()


class TestDBOverride:
    """DB 覆盖权重单测"""

    def test_db_override_empty_returns_base(self) -> None:
        """DB 覆盖为空 → 返 base"""
        base = HybridWeights()
        assert db_override_weights(base, None) == base
        assert db_override_weights(base, {}) == base

    def test_db_override_partial_keeps_base(self) -> None:
        """DB 部分覆盖 → 其它字段保留 base"""
        base = HybridWeights()
        merged = db_override_weights(base, {"vector": 0.7})
        assert merged.vector == 0.7
        assert merged.bm25 == base.bm25

    def test_db_override_invalid_keeps_base(self) -> None:
        """DB 覆盖非法 (负数) → 保留 base"""
        base = HybridWeights()
        merged = db_override_weights(base, {"vector": -0.5})
        assert merged == base


class TestDefaults:
    """默认值/常量单测"""

    def test_default_weights_dict_matches_dataclass(self) -> None:
        """DEFAULT_WEIGHTS 必须与 HybridWeights 默认一致"""
        w = HybridWeights()
        assert DEFAULT_WEIGHTS["vector"] == w.vector
        assert DEFAULT_WEIGHTS["bm25"] == w.bm25
        assert DEFAULT_WEIGHTS["graph"] == w.graph
        assert DEFAULT_WEIGHTS["rerank"] == w.rerank

    def test_ab_config_dict_has_two_groups(self) -> None:
        """DEFAULT_AB_CONFIG 必须含 A/B 两组"""
        assert "A" in DEFAULT_AB_CONFIG
        assert "B" in DEFAULT_AB_CONFIG
        assert sum(DEFAULT_AB_CONFIG["A"].values()) == pytest.approx(1.0, abs=1e-6)
        assert sum(DEFAULT_AB_CONFIG["B"].values()) == pytest.approx(1.0, abs=1e-6)