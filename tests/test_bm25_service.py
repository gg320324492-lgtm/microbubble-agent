"""BM25 关键词检索服务测试"""
import pytest
from app.services.bm25_service import BM25Service


class TestBM25Service:
    """BM25 服务测试"""

    def test_tokenize_chinese(self):
        """中文分词测试"""
        service = BM25Service()
        tokens = service._tokenize("微纳米气泡的zeta电位是表征其表面电荷的重要指标")
        assert "微纳" in tokens or "纳米" in tokens or "气泡" in tokens
        assert "zeta" in tokens
        assert "电位" in tokens
        # 停用词应被过滤
        assert "的" not in tokens
        assert "是" not in tokens

    def test_tokenize_english(self):
        """英文分词测试"""
        service = BM25Service()
        tokens = service._tokenize("micro-nano bubble zeta potential")
        assert "micro" in tokens
        assert "nano" in tokens
        assert "bubble" in tokens

    def test_build_index(self):
        """构建索引测试"""
        service = BM25Service()
        documents = [
            {"id": 1, "title": "微纳米气泡", "content": "微纳米气泡是一种直径小于50微米的气泡"},
            {"id": 2, "title": "zeta电位", "content": "zeta电位是表征胶体稳定性的重要参数"},
            {"id": 3, "title": "空化效应", "content": "超声空化效应是产生微纳米气泡的主要方法之一"},
        ]
        service.build_index(documents)
        assert service._corpus_size == 3
        assert service._bm25 is not None

    def test_search(self):
        """检索测试"""
        service = BM25Service()
        documents = [
            {"id": 1, "title": "微纳米气泡", "content": "微纳米气泡是一种直径小于50微米的气泡"},
            {"id": 2, "title": "zeta电位", "content": "zeta电位是表征胶体稳定性的重要参数"},
            {"id": 3, "title": "空化效应", "content": "超声空化效应是产生微纳米气泡的主要方法之一"},
        ]
        service.build_index(documents)
        results = service.search("微纳米气泡", top_k=2)
        assert len(results) <= 2
        assert len(results) > 0
        # 第一条和第三条都包含"微纳米气泡"，应该排在前面
        assert results[0]["id"] in [1, 3]

    def test_search_empty_index(self):
        """空索引检索测试"""
        service = BM25Service()
        service.build_index([])
        results = service.search("测试", top_k=5)
        assert results == []

    def test_search_no_match(self):
        """无匹配结果测试"""
        service = BM25Service()
        documents = [
            {"id": 1, "title": "微纳米气泡", "content": "微纳米气泡是一种直径小于50微米的气泡"},
        ]
        service.build_index(documents)
        results = service.search("量子力学", top_k=5)
        # BM25 会返回结果但分数很低
        assert len(results) <= 1
