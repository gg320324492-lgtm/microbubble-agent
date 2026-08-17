"""自定义 SQLAlchemy pgvector 类型 (W-N-B 阶段 B.2)

提供 HalfVector wrapper, 接受 numpy float16/float32 数组, 落库前自动 cast 为 float16.
自实现 UserDefinedType (不依赖 pgvector Python 包 0.7+ 的 HalfVector class, 当前 pip 0.5.0
无此导出, DB ext 已是 0.7.0 支持 halfvec).

## 设计

- 写入: numpy.ndarray -> .astype(np.float16).tolist() -> '[f1,f2,...]' 字面量
- 读取: pg 返回 '[f1,f2,...]' -> list[float]
- 距离操作: 与 pgvector 0.7+ 兼容, 使用 <=> (cosine) <-> (l2) <#> (ip)
- numpy 兼容: 自动 .astype(np.float16) (避免 type mismatch on bind)
- None 处理: 透传 (nullable column)

## 派工 brief vs 实测错配 (类 20.XX 沉淀)

- 派工 brief 假设 `from pgvector.sqlalchemy import HalfVector as _PgHalfVector` (继承)
- 实测 pgvector pip 0.5.0 无 HalfVector 导出, DB 0.7.0 已支持
- 决策: 自实现 UserDefinedType, 模仿 `pgvector.sqlalchemy.Vector` 源码模式
- 不动 `app/services/embedding_service.py` (阶段 C 任务)
"""
from typing import Any, List, Optional

import numpy as np
from sqlalchemy import Float, String
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.sql.type_api import TypeEngine, UserDefinedType


class HalfVector(UserDefinedType):
    """SQLAlchemy halfvec(N) wrapper with numpy compatibility.

    落库 SQL: ``HALFVECTOR(dim)`` (pgvector 0.7+ 注册)
    bind:    numpy.float16/float32 array -> list[float] (lossy cast if needed)
    result:  pg returns ``'[f1,f2,...]'`` -> list[float]
    """

    cache_ok = True
    _string = String()

    def __init__(self, dim: Optional[int] = None) -> None:
        super().__init__()
        self.dim = dim

    def get_col_spec(self, **kw: Any) -> str:
        if self.dim is None:
            return "HALFVEC"
        return f"HALFVEC({self.dim})"

    def bind_processor(self, dialect: Dialect) -> Any:
        def process(value: Any) -> Optional[List[float]]:
            if value is None:
                return None
            if isinstance(value, np.ndarray):
                # float16 已是目标类型, 但若上游是 float32, lossy cast
                if value.dtype != np.float16:
                    value = value.astype(np.float16)
                return value.tolist()
            if isinstance(value, (list, tuple)):
                # 上游已传 list[float], 直接返回
                return list(value)
            raise TypeError(
                f"HalfVector.bind_processor: unsupported type {type(value).__name__}"
            )
        return process

    def literal_processor(self, dialect: Dialect) -> Any:
        string_literal_processor = self._string._cached_literal_processor(dialect)

        def process(value: Any) -> Any:
            arr = value if isinstance(value, list) else (
                value.tolist() if isinstance(value, np.ndarray) else value
            )
            return string_literal_processor(str(arr).replace(" ", ""))
        return process

    def result_processor(self, dialect: Dialect, coltype: Any) -> Any:
        def process(value: Any) -> Optional[List[float]]:
            if value is None:
                return None
            if isinstance(value, str):
                # pg returns '[f1,f2,...]'
                inner = value.strip("[]")
                if not inner:
                    return []
                return [float(x) for x in inner.split(",")]
            if isinstance(value, (list, tuple)):
                return [float(x) for x in value]
            raise TypeError(
                f"HalfVector.result_processor: unsupported type {type(value).__name__}"
            )
        return process

    class Comparator(TypeEngine.Comparator[Any]):
        """Distance operators (pgvector 0.7+ 兼容 halfvec)."""

        def l2_distance(self, other: Any, /) -> Any:
            return self.op("<->", return_type=Float)(other)

        def max_inner_product(self, other: Any, /) -> Any:
            return self.op("<#>", return_type=Float)(other)

        def cosine_distance(self, other: Any, /) -> Any:
            return self.op("<=>", return_type=Float)(other)

        def l1_distance(self, other: Any, /) -> Any:
            return self.op("<+>", return_type=Float)(other)

    # 关键: comparator_factory 让 SQLAlchemy InstrumentedAttribute.comparator
    # 用我们的 Comparator (含 cosine_distance / l2_distance / etc.)
    # 否则 InstrumentedAttribute 用默认 ColumnProperty.Comparator,
    # 访问 .cosine_distance 抛 AttributeError (W-N-B 漏修, 2026-08-17 e2e 实战发现)
    comparator_factory = Comparator
