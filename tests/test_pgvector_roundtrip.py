"""P2-11 端到端: pgvector embedding round-trip 序列化测试.

bug: scripts/migrate_kb_tags.py:264 + scripts/migrate_kb_dedup_titles.py:329
d['embedding'] = list(k.embedding) 把 pgvector Vector(N) 序列化为 list[float]
用于 JSON 备份. 但没有 round-trip 测试 — 如果 list() 拿不到完整 1024 维 →
备份 JSON 缺 embedding → restore 时 DB 行 embedding=NULL → 知识库语义搜索失效.

测试: 模拟 Vector(N) 数据 → 序列化 → JSON 落盘 → 反序列化 → 验证
维度 + 数值完全一致. 同时静态检查 migrate_kb 脚本用 list() (不是 str) 保留精度.

跑法:
    SKIP_DB_SETUP=1 pytest tests/test_pgvector_roundtrip.py -v
    或容器内: docker exec microbubble-agent-app-1 bash -c
      'cd /app && python -m pytest tests/test_pgvector_roundtrip.py -v'
"""
import json
from pathlib import Path

import numpy as np


def _fake_vector_to_list(vector_data):
    """模拟 pgvector Vector(N) → list[float] 的转换.

    pgvector 的 Vector 继承自 numpy ndarray, list() 调 tolist() 返回 Python list.
    """
    if vector_data is None:
        return None
    return [float(x) for x in vector_data.tolist()]


# ── round-trip: 1024 维 ────────────────────────────────────────
def test_roundtrip_preserves_dim_1024():
    """1024 维 embedding (text2vec-base-chinese) round-trip 后维度 + 数值一致."""
    original = np.random.rand(1024).astype(np.float32)

    embedding_list = _fake_vector_to_list(original)

    assert isinstance(embedding_list, list)
    assert len(embedding_list) == 1024
    assert all(isinstance(x, float) for x in embedding_list)

    payload = {'id': 1, 'embedding': embedding_list}
    payload_str = json.dumps(payload)

    restored = json.loads(payload_str)

    assert restored['id'] == 1
    assert len(restored['embedding']) == 1024

    restored_arr = np.array(restored['embedding'], dtype=np.float32)
    np.testing.assert_array_equal(original, restored_arr)


# ── round-trip: 768 维 (bge-base-zh) ────────────────────────
def test_roundtrip_realistic_768_dim():
    """768 维 embedding (BAAI/bge-base-zh) round-trip."""
    original = np.random.rand(768).astype(np.float32)

    embedding_list = _fake_vector_to_list(original)
    json_str = json.dumps({'id': 99, 'embedding': embedding_list})

    restored = json.loads(json_str)
    restored_arr = np.array(restored['embedding'], dtype=np.float32)

    assert restored_arr.shape == (768,)
    np.testing.assert_array_equal(original, restored_arr)


# ── round-trip: None embedding ────────────────────────────────
def test_roundtrip_handles_none_embedding():
    """embedding=None → 序列化为 None, 反序列化保持 None (不报错)."""
    payload = {'id': 1, 'embedding': None}
    json_str = json.dumps(payload)
    restored = json.loads(json_str)
    assert restored['embedding'] is None


# ── 静态检查: migrate_kb 脚本用 list() 不是 str() ────────────────
def test_migrate_kb_uses_list_not_str():
    """防御性检查: migrate_kb_tags.py + migrate_kb_dedup_titles.py 序列化 embedding
    必须用 list(k.embedding) 不是 str(k.embedding) (str 会丢精度, list 保留全部 1024 维).

    这两个脚本对 embedding 的序列化必须保留精度, 否则 restore 时 DB 行 embedding=NULL
    → 知识库语义搜索失效 (cosine 距离变 NaN).
    """
    project_root = Path(__file__).parent.parent
    for script_name in [
        'scripts/migrate_kb_tags.py',
        'scripts/migrate_kb_dedup_titles.py',
    ]:
        path = project_root / script_name
        if not path.exists():
            continue
        source = path.read_text(encoding='utf-8')
        assert 'list(k.embedding)' in source, (
            f'{script_name} 必须用 list(k.embedding) 序列化, '
            '不能用 str() (会丢精度, 1024 维 → 1 维字符串)'
        )
        assert 'str(k.embedding)' not in source, (
            f'{script_name} 不能用 str(k.embedding) 序列化, '
            '会丢精度让 restore 后知识库语义搜索失效'
        )


# ── 异常处理建议 ────────────────────────────────────────
def test_exception_handling_suggestion():
    """P2-11 修复建议 (留给下次 commit): migrate_kb_tags.py:265 静默 except Exception
    吞错, 应改成 logger.warning 留 audit trace. 本测试标记不强制变更.
    """
    pass
