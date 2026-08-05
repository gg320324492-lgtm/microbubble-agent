"""Unit tests for HalfVector SQLAlchemy type (W-N-B 阶段 B.2 步骤 2)

TDD 顺序:
1. 写失败测试 -> 跑 -> PASS -> commit
2. wrapper 在 app/models/types.py 已自实现, 本测试只验证 in-memory behavior
   (bind_processor / result_processor), 不连真实 DB
"""
import math

import numpy as np
import pytest

from app.models.types import HalfVector


def test_get_col_spec_with_dim():
    """HalfVector(1024) -> 'HALFVEC(1024)'"""
    t = HalfVector(1024)
    assert t.get_col_spec() == "HALFVEC(1024)"


def test_get_col_spec_without_dim():
    """HalfVector() -> 'HALFVEC' (untyped, pgvector 也支持)"""
    t = HalfVector()
    assert t.get_col_spec() == "HALFVEC"


def test_float32_array_converted_to_float16_list():
    """numpy float32 array 落库前自动 cast 为 float16, 输出 list[float]"""
    t = HalfVector(1024)
    arr = np.random.rand(1024).astype(np.float32)
    proc = t.bind_processor(dialect=None)
    out = proc(arr)
    assert isinstance(out, list)
    assert len(out) == 1024
    # half 精度损失在 ~1e-3 量级, 但 round-trip through float 可能有微小 diff
    assert math.isfinite(out[0])
    # 数值一致 (np.float16 -> float 后)
    expected = float(arr[0].astype(np.float16))
    assert abs(out[0] - expected) < 1e-5


def test_float16_array_passthrough():
    """numpy float16 array 已是目标类型, 不重复 cast"""
    t = HalfVector(1024)
    arr = np.random.rand(1024).astype(np.float16)
    proc = t.bind_processor(dialect=None)
    out = proc(arr)
    assert isinstance(out, list)
    assert len(out) == 1024


def test_none_passthrough():
    """None 透传 (nullable column)"""
    t = HalfVector(1024)
    proc = t.bind_processor(dialect=None)
    assert proc(None) is None


def test_list_input_passthrough():
    """上游已传 list[float], 直接返回"""
    t = HalfVector(1024)
    raw = [0.1, 0.2, 0.3]
    proc = t.bind_processor(dialect=None)
    out = proc(raw)
    assert out == raw


def test_unsupported_type_raises():
    """非 numpy/list/tuple 抛 TypeError (不静默)"""
    t = HalfVector(1024)
    proc = t.bind_processor(dialect=None)
    with pytest.raises(TypeError, match="unsupported type"):
        proc("not a vector")


def test_result_processor_parses_pg_string():
    """pg 返回 '[f1,f2,...]' 字面量, 解析为 list[float]"""
    t = HalfVector(1024)
    proc = t.result_processor(dialect=None, coltype=None)
    pg_text = "[0.1,0.2,0.3]"
    out = proc(pg_text)
    assert out == [0.1, 0.2, 0.3]


def test_result_processor_handles_none():
    """None 输入透传"""
    t = HalfVector(1024)
    proc = t.result_processor(dialect=None, coltype=None)
    assert proc(None) is None


def test_result_processor_handles_empty():
    """空数组 '[]' -> []"""
    t = HalfVector(1024)
    proc = t.result_processor(dialect=None, coltype=None)
    assert proc("[]") == []


def test_comparator_cosine_distance_operator():
    """cosine_distance 算子 <=> 编译到 SQL"""
    from sqlalchemy import Column, Float, select
    t = HalfVector(1024)
    col_expr = Column("embedding", t)
    # 通过自定义 Comparator.cosine_distance 生成 <=> 算子
    stmt = select(t.Comparator.cosine_distance(col_expr, [0.1] * 1024).label("dist"))
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "<=>" in compiled


def test_comparator_l2_distance_operator():
    """l2_distance 算子 <-> 编译到 SQL"""
    from sqlalchemy import Column, select
    t = HalfVector(1024)
    col_expr = Column("embedding", t)
    stmt = select(t.Comparator.l2_distance(col_expr, [0.1] * 1024).label("dist"))
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "<->" in compiled
