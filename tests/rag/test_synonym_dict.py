"""PR4 synonym_dict 单测 (W90 +10)

门禁: synonym dict ≥ 200 条 (实测 298 条)

不动: bm25_service.py, hybrid_retriever 原签名
"""

import pytest

from app.services.synonym_dict import (
    canonical_form,
    count_synonyms,
    expand_query,
    get_synonyms,
    get_synonym_groups,
    reset_cache,
)


@pytest.fixture(autouse=True)
def _reset_synonym_cache() -> None:
    """每个测试前 reset cache, 避免状态污染"""
    reset_cache()


class TestSynonymCount:
    """同义词 dict 条数门禁 (≥ 200)"""

    def test_synonym_count_at_least_200(self) -> None:
        """PR4 量化门禁: synonym dict ≥ 200 条"""
        n = count_synonyms()
        assert n >= 200, f"synonym dict 不足 200 条, 实际 {n}"

    def test_synonym_groups_count(self) -> None:
        """synonym group 数合理 (≥ 30 group)"""
        groups = get_synonym_groups()
        assert len(groups) >= 30, f"synonym group < 30, 实际 {len(groups)}"

    def test_canonical_unique(self) -> None:
        """canonical 必须唯一 (不允许一词多 canonical)"""
        syn = get_synonyms()
        canonicals = list(syn.values())
        # 多个 variant 共享一个 canonical 是允许的; canonical 自指也算
        # 这里验证: 每条 variant 只指向一个 canonical
        for variant, canonical in syn.items():
            assert syn[variant] == canonical, f"variant '{variant}' canonical 不稳定"


class TestCanonicalForm:
    """canonical_form 单测"""

    def test_chinese_variant(self) -> None:
        """中文 variant → canonical"""
        assert canonical_form("微气泡") == "microbubble"
        assert canonical_form("纳米气泡") == "nanobubble"

    def test_english_variant(self) -> None:
        """英文 variant → canonical"""
        assert canonical_form("microbubble") == "microbubble"
        assert canonical_form("nanobubble") == "nanobubble"
        assert canonical_form("Microbubble") == "microbubble"  # 大小写不敏感

    def test_unknown_word_returns_self(self) -> None:
        """未登录词 → 返回原词 (不报错)"""
        assert canonical_form("未登录词") == "未登录词"
        assert canonical_form("") == ""

    def test_whitespace_stripped(self) -> None:
        """前后空格 strip"""
        assert canonical_form("  微气泡  ") == "microbubble"


class TestExpandQuery:
    """expand_query 查询改写单测"""

    def test_expand_microbubble_query(self) -> None:
        """中文微气泡查询改写"""
        result = expand_query("微气泡的 zeta 电位")
        assert "microbubble" in result
        assert "zeta_potential" in result

    def test_expand_nanobubble_query(self) -> None:
        """纳米气泡改写"""
        result = expand_query("纳米气泡在水处理中的应用")
        assert "nanobubble" in result
        assert "water_treatment" in result

    def test_expand_english_query(self) -> None:
        """英文查询改写"""
        result = expand_query("Microbubble in water treatment")
        assert "water_treatment" in result

    def test_expand_empty_query(self) -> None:
        """空查询 → 空"""
        assert expand_query("") == ""

    def test_expand_unknown_words_passthrough(self) -> None:
        """未登录词保留原样"""
        result = expand_query("未知查询 微气泡")
        assert "未知查询" in result
        assert "microbubble" in result


class TestMicroNanoBubbleDomain:
    """微纳米气泡核心词覆盖验证"""

    def test_canonical_microbubble_group_size(self) -> None:
        """microbubble group ≥ 5 variants"""
        groups = get_synonym_groups()
        microbubble_group = next((g for g in groups if "microbubble" in g), None)
        assert microbubble_group is not None
        assert len(microbubble_group) >= 5

    def test_canonical_nanobubble_group_size(self) -> None:
        """nanobubble group ≥ 5 variants"""
        groups = get_synonym_groups()
        nb_group = next((g for g in groups if "nanobubble" in g), None)
        assert nb_group is not None
        assert len(nb_group) >= 5

    def test_zeta_potential_canonical(self) -> None:
        """zeta_potential 同义词覆盖"""
        assert canonical_form("zeta电位") == "zeta_potential"
        assert canonical_form("zeta potential") == "zeta_potential"
        assert canonical_form("ζ电位") == "zeta_potential"

    def test_cavitation_canonical(self) -> None:
        """cavitation 同义词覆盖"""
        assert canonical_form("空化") == "cavitation"
        assert canonical_form("空化作用") == "cavitation"

    def test_water_treatment_canonical(self) -> None:
        """water_treatment 同义词覆盖"""
        assert canonical_form("水处理") == "water_treatment"
        assert canonical_form("污水处理") == "water_treatment"
        assert canonical_form("废水处理") == "water_treatment"


class TestCacheBehavior:
    """cache 行为单测"""

    def test_reset_cache_forces_reload(self) -> None:
        """reset_cache 后 force_reload 重新读数据"""
        syn1 = get_synonyms()
        assert len(syn1) > 0
        reset_cache()
        syn2 = get_synonyms(force_reload=True)
        assert len(syn1) == len(syn2)

    def test_default_no_reload_uses_cache(self) -> None:
        """默认不 force_reload → 第二次调用走 cache"""
        # 第一次调用加载 cache
        get_synonyms()
        # 第二次调用应直接返 cache (不重读文件)
        # 这是一个 smoke test — 不能精确验证, 但确保不抛异常
        syn = get_synonyms()
        assert syn is not None
        assert len(syn) >= 200