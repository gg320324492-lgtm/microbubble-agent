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


def test_float32_array_converted_to_float16_literal():
    """numpy float32 array 落库前自动 cast 为 float16, 输出 '[f1,...]' 字面量"""
    t = HalfVector(1024)
    arr = np.random.rand(1024).astype(np.float32)
    proc = t.bind_processor(dialect=None)
    out = proc(arr)
    # 2026-09-01 P0 修复: asyncpg halfvec 参数必须是字符串字面量
    assert isinstance(out, str)
    assert out.startswith("[") and out.endswith("]")
    parts = out[1:-1].split(",")
    assert len(parts) == 1024
    # 数值一致 (np.float16 -> float 后)
    expected = float(arr[0].astype(np.float16))
    assert abs(float(parts[0]) - expected) < 1e-5


def test_float16_array_passthrough_literal():
    """numpy float16 array 已是目标类型, 不重复 cast, 输出字面量"""
    t = HalfVector(1024)
    arr = np.random.rand(1024).astype(np.float16)
    proc = t.bind_processor(dialect=None)
    out = proc(arr)
    assert isinstance(out, str)
    assert len(out[1:-1].split(",")) == 1024


def test_none_passthrough():
    """None 透传 (nullable column)"""
    t = HalfVector(1024)
    proc = t.bind_processor(dialect=None)
    assert proc(None) is None


def test_list_input_becomes_literal():
    """上游传 list[float] → '[...]' 字面量 (2026-09-01 P0 修复契约)"""
    t = HalfVector(1024)
    raw = [0.1, 0.2, 0.3] + [0.0] * 1021
    proc = t.bind_processor(dialect=None)
    out = proc(raw)
    assert isinstance(out, str)
    assert out.startswith("[0.1,0.2,0.3,")
    assert out.endswith("]")


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
