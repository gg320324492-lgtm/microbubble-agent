"""修复 `_chunk_late_recall` 的两层静默失效 (2026-11-04)

起因: P1 评测全量日志里 `chunk_late_recall FAILED ... (expected str, got list)`
稳定出现, 但被 best-effort `except` 兜成空集 ⇒ 这条召回臂从落地起就是死的,
而检索整体"看起来在工作" (类 20.220)。

**两层**, 只修第一层会把故障改成更难查的形态:

| 层 | 缺陷 | 只修它的后果 |
|---|---|---|
| 1 | 裸 `text()` 没有 ORM 列类型 ⇒ 传 `List[float]` 被 asyncpg 拒 | 修好后臂能跑, 但…… |
| 2 | 库里 178 行 `chunk_embedding` 是 `backfill_late_embedding.py` 用 **MockForward(np.ones)** 回填的全 1 假向量 | 常量向量与任何 query 距离都相同 ⇒ 召回纯噪声、污染 RRF |

⇒ 判据必须同时验「绑定改对了」和「假向量被挡住」，并且要证明
**真向量仍能召回**（守卫不能把正常数据一起挡掉）。
"""
import ast
import pathlib

import pytest

from app.services.hybrid_retriever import vector_to_pg_literal

REPO = pathlib.Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------- 序列化函数


def test_pg_literal_shape():
    lit = vector_to_pg_literal([1.0, 0.5, -0.25], expected_dim=3)
    assert lit == "[1.0,0.5,-0.25]"
    assert isinstance(lit, str)  # 关键: 不是 list


def test_pg_literal_1024_dims():
    lit = vector_to_pg_literal([0.0] * 1024)
    assert len(lit.split(",")) == 1024


def test_pg_literal_preserves_precision():
    v = [0.123456789, -1e-8]
    lit = vector_to_pg_literal(v, expected_dim=2)
    assert "0.123456789" in lit and "-1e-08" in lit


def test_pg_literal_rejects_wrong_dim():
    """维度校验是 fail-loud: 换嵌入模型时宁可报错, 不许静默查出错误结果。"""
    with pytest.raises(ValueError, match="维度"):
        vector_to_pg_literal([1.0] * 768)


def test_pg_literal_rejects_junk():
    for bad in (None, [], "not-a-vector", ()):
        with pytest.raises(ValueError):
            vector_to_pg_literal(bad)


# ---------------------------------------------------------------- 真库往返


@pytest.mark.asyncio
async def test_string_works_list_fails_on_real_pgvector(db):
    """类 20.161 的可执行替代判据: 同一条裸 SQL, list 炸 / str 通。

    这条是**修复方向的证据**，不是"看代码猜的": 单元 mock 全绿曾经把 bug
    焊死过一次 (tests/integration/test_late_chunking_recall.py 旧断言只数长度)。
    """
    from sqlalchemy import text

    v = [0.0] * 1024
    v[0] = 1.0
    lit = vector_to_pg_literal(v)
    sql = text(
        "SELECT min(x <=> CAST(:q AS vector)) "
        "FROM (SELECT unnest(ARRAY[CAST(:q AS vector)]) AS x) t"
    )
    with pytest.raises(Exception) as exc:
        await db.execute(sql, {"q": v})
    assert "expected str" in str(exc.value) or "DataError" in str(exc.value)

    r = await db.execute(sql, {"q": lit})
    assert r.scalar() == pytest.approx(0.0, abs=1e-6)


@pytest.mark.asyncio
async def test_guard_excludes_constant_vectors_but_not_real_ones(db):
    """守卫必须只挡全 1 假向量, 不能把真向量一起挡了。

    用**纯 SQL 的内存集合**验 (不插表): 与常量方向重合的向量 distance≈0 被挡,
    与常量正交的真向量 distance>0 通过。这正好对应库里 178 行
    MockForward(np.ones) 与将来真模型 backfill 两种数据形态。
    """
    from sqlalchemy import text

    q = [0.0] * 1024
    q[7] = 1.0
    ones = [1.0] * 1024
    qlit, olit = vector_to_pg_literal(q), vector_to_pg_literal(ones)
    stmt = text(
        "SELECT v, (v <=> CAST(:ones AS vector)) AS d "
        "FROM (VALUES (CAST(:fake AS vector)), (CAST(:real AS vector))) AS t(v)"
    )
    rows = (await db.execute(stmt, {
        "ones": olit, "fake": olit, "real": qlit,
    })).fetchall()
    by_d = {round(float(r.d), 6): float(r.d) for r in rows}

    assert 0.0 in by_d, "全 1 假向量与常量方向的 distance 应≈0"
    # 守卫条件 > 1e-6: 假向量被排除, 真向量保留
    kept = [d for d in by_d.values() if d > 1e-6]
    assert kept, "真向量也被守卫挡掉了 —— 将来真模型 backfill 后这条臂永远不会生效"
    assert all(d > 0.9 for d in kept), "真向量与全 1 常量的距离应接近 1 (正交方向)"


# ---------------------------------------------------------------- 结构守卫


def test_chunk_late_recall_passes_strings_and_has_guard():
    """AST: 调用点必须传两个字符串参数, SQL 必须带常量守卫。

    用 AST 而不是 grep —— 本仓注释里大量"提到"这些名字, grep 会假阳性
    (类 20.225)。同时断言调用点**不再直接把 list 塞进 params**。
    """
    src = (REPO / "app/services/hybrid_retriever.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    cls = next(n for n in tree.body
               if isinstance(n, ast.ClassDef) and n.name == "HybridRetriever")
    fn = next(n for n in cls.body
              if isinstance(n, ast.AsyncFunctionDef) and n.name == "_chunk_late_recall")

    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)]
    # vector_to_pg_literal 至少被调两次 (query + ones)
    serializers = [
        n for n in calls
        if getattr(n.func, "id", "") == "vector_to_pg_literal"
    ]
    assert len(serializers) >= 2, "query 或 ones 没经序列化 ⇒ 换参数名复发同一个坑"

    sql_strings = [
        n.value for n in ast.walk(fn)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
        and "knowledge_chunks" in n.value
    ]
    assert sql_strings and any(
        "(v <=> CAST(:ones AS vector)) > 1e-6" in s for s in sql_strings
    ), "常量假向量守卫丢了"

    params = [
        n for n in ast.walk(fn)
        if isinstance(n, ast.Dict)
        and any(isinstance(k, ast.Constant) and k.value == "query_embedding"
                for k in n.keys)
    ]
    assert params, "找不到 execute 的 params 字典"
    for d in params:
        for k, v in zip(d.keys, d.values):
            if isinstance(k, ast.Constant) and k.value in ("query_embedding", "ones"):
                assert not (isinstance(v, ast.Name) and v.id == "query_embedding"), (
                    "仍把原始 list 直接传进 params ⇒ asyncpg 必炸")


def test_mock_backfill_script_is_clearly_marked():
    """把「178 行是假数据」这个事实钉在测试里，防止有人以为是真模型产物。

    这是**给未来读者的护栏**: 若哪天脚本换成真模型, 这条测试会红,
    提醒同步去掉 SQL 里的常量守卫 (或改成有区分度的判据)。
    """
    src = (REPO / "scripts/backfill_late_embedding.py").read_text(encoding="utf-8")
    assert "_build_mock_model" in src, (
        "backfill 脚本不再用 mock 模型了 ⇒ 库里 chunk_embedding 可能是真向量, "
        "应重新评估 _chunk_late_recall 里的常量守卫是否还必要")
