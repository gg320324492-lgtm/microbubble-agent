# W100-CACHE-MISS Cache Hook 实测 runbook (2026-08-02)

## 背景

W99-W100 RAG 升级 6 批合并后, 派工 brief 报告 "W99-RAG-1 cache hook 缺失" 现象:
- 本地 `app/services/hybrid_retriever.py` `grep -c "RAGQueryCache|cache_hit"` = 0
- 容器内 `retrieve_with_weights` 函数体不含 `RAGQueryCache` 引用
- 3 次连续 `retrieve_with_weights(query, top_k=3)` 调用都返回 `list` (不是 `dict` 带 cache_hit)
- 配置 `RAG_QUERY_CACHE_ENABLED=True` 已生效

## 实测真根因 (派工 v6 §13.3 假设禁令)

派工 brief 假设 "cache hook 缺失" 为**假阴性**. 实测:

1. **cache hook 代码完全存在** at `app/services/hybrid_retriever.py:584-643`
2. **cache hook 字节级完整** (W99-RAG-1..W100-BUGFIX 全部 commit 后 0 diff)
3. **cache hook 工作正常** (容器内实测 pre-populate cache + retrieve_with_weights 返回 cached data)
4. **派工 brief grep 字符串错配**:
   - `RAGQueryCache` (class 名): hybrid_retriever.py 不直接引用 class, 用 `get_rag_query_cache()` 工厂
   - `cache_hit`: hybrid_retriever.py 不写该字段, 该字段只在 `RecallTrace` 观测层存在且是死字段

## Cache Hook 设计契约 (实测)

### Hook 位置
```
app/services/hybrid_retriever.py:584-643
async def retrieve_with_weights(...):
    ...
    # 0) W99-RAG-1: Query Cache hook (lookup)
    try:
        from app.rag.config import RAG_QUERY_CACHE_ENABLED as _CFG_ENABLED
        from app.services.rag_query_cache import get_rag_query_cache
        if _CFG_ENABLED:
            _cache = get_rag_query_cache()
            _cached = await _cache.get(query, user_id=user_id, tenant_id=tenant_id)
            if _cached is not None and _cached.get("results"):
                return _cached["results"]  # ← cache hit 返回 list
    except Exception as _e:
        logger.debug(...)
    
    # (retriever.retrieve call)
    
    # 4) W99-RAG-1: 写缓存 (best-effort)
    if raw_results:  # ← 仅当 retrieve 返回非空时写
        try:
            ...
            await _cache.set(query=..., result={...})
        except Exception as _e:
            logger.debug(...)
```

### Cache Hook 行为表

| 输入场景 | Hook 行为 | 返回值类型 |
|----------|-----------|-----------|
| cache hit + raw_results 空 | 返回 `_cached["results"]` | `list` (cache 的 results) |
| cache miss + raw_results 非空 | 写 cache, 继续后续 hooks | `list` (经过 rerank/multimodal/temporal 处理) |
| cache miss + raw_results 空 | 跳过写, 继续后续 hooks | `list` (可能由 multimodal 兜底) |
| `_CFG_ENABLED=False` | 跳过整个 cache 块 | 取决于其他 hooks |

### Cache 模块契约 (`app/services/rag_query_cache.py`)

```python
class RAGQueryCache:
    async def get(query, user_id, tenant_id) -> Optional[Dict[str, Any]]:
        """精确查询缓存命中检查
        Returns:
            命中: dict 含 results/citations/retrieval_method/score/timestamp 等
            未命中: None
        """
    
    async def set(query, user_id, tenant_id, result, ttl=None) -> bool:
        """写缓存 (best-effort)
        Returns:
            True 写成功 / False 失败 — 调用方不必检查
        """
```

`cache.get` 返回 dict, 但 hook 调用 `cached["results"]` 提取 list 后返回.

## 排查方法 (派工 v6 §13 仓库实情真查)

### Step 1: git log -S 验证 cache hook 是否在某次 commit 丢失

```bash
cd /e/microbubble-agent
git log -S "RAGQueryCache" --oneline  # 看所有引入/删除该字符串的 commit
git log -S "cache_hit" --oneline       # 同上
git log --all -p -S "RAGQueryCache" -- app/services/hybrid_retriever.py --oneline
```

实测结果 (W99-RAG-1..W100-BUGFIX):
- 4 个 commit 引入 `RAGQueryCache` 字符串 (W99-RAG-1 +20/22/24/25 + W100-RAG-3 test)
- **0 个 commit 从 hybrid_retriever.py 删除 RAGQueryCache 字符串**

### Step 2: 字节级 cache hook 代码验证

```bash
git log --all --oneline -- app/services/hybrid_retriever.py | head -10
# 列出影响 hybrid_retriever.py 的所有 commit
# 实测关键 commit:
#   830c1d8ed W99-RAG-1 W99 +21: feat(rag/cache): hybrid_retriever 入口加 cache hook
#   cc91148aa W99-RAG-2 W99 +7:  feat(rag/citation): hybrid_retriever 入口加 citation hook
#   7f1d21e4d W100-RAG-3 W99 +2:  feat(rag/intent): hybrid_retriever 入口加 intent hook
#   92efd7247 W100-RAG-4 W99 +2:  feat(rag/reranker): hybrid_retriever 入口加 reranker hook
#   0ed1c583b W100-RAG-5 W99 +3:  feat(rag/multimodal): hybrid_retriever 入口加 multimodal hook
#   b6f3b3a08 W100-RAG-6 W99 +2:  feat(rag/temporal): hybrid_retriever 入口加 temporal hook
#   1f6ce932f W100-BUGFIX W100 +1: fix(citation): KnowledgeRefBlock 段落高亮 3 处串联通修
```

```bash
# 检查 1f6ce932f (W100-BUGFIX) 修改范围
git show 1f6ce932f -- app/services/hybrid_retriever.py
# 实测: 仅触及 citation 代码段 (lines 645-700), cache hook (lines 584-643) 0 diff
```

### Step 3: 容器内实测 cache hook 行为

```bash
docker exec microbubble-agent-app-1 bash -c 'python << "PYEOF"
import sys; sys.path.insert(0, "/app")
import asyncio
from app.services.rag_query_cache import get_rag_query_cache
from app.core.database import async_session
from app.services.hybrid_retriever import retrieve_with_weights

async def test():
    cache = get_rag_query_cache()
    test_q = f"test cache hook {asyncio.get_event_loop().time()}"
    
    # Pre-populate
    await cache.set(test_q, None, None, {
        "results": [{"id": 999, "title": "cached"}],
        "citations": [],
        "retrieval_method": "hybrid",
        "score": 0.95,
        "top_k": 3,
    })
    
    # Test retrieve_with_weights - should hit cache
    async with async_session() as db:
        r = await retrieve_with_weights(db, test_q, top_k=3)
        print(f"return type: {type(r).__name__}, len: {len(r) if r else 0}")
        if r and isinstance(r, list):
            print(f"r[0]: {r[0]}")

asyncio.run(test())
PYEOF'
```

实测结果:
- `return type: list, len: 1`
- `r[0]: {'id': 999, 'title': 'cached'}`

**Cache hook 工作正常, 返回 cached data.**

## 派工 brief 假设错配清单 (派工 v6 §13 实战)

1. **base ref 错配**: 派工 brief 假设 base 是 `a35e4682b`, 实测一致 ✅
2. **cache hook 缺失**: 派工 brief 假设 "cache hook 缺失", 实测 cache hook 完全工作 ❌ (派工 brief 错)
3. **W100-BUGFIX 覆盖 cache hook**: 派工 brief 假设 "W100-BUGFIX fix(citation) 覆盖 cache hook", 实测 W100-BUGFIX 仅修 citation ❌ (派工 brief 错)
4. **W99-RAG-1 commit 830c1d8ed 引入 cache hook**: 派工 brief 假设, 实测一致 ✅
5. **3 次连续调用 cache miss**: 派工 brief 假设是 cache hook 问题, 实测是 `retriever.retrieve()` 返回空 list 导致的自然 cache miss ❌ (派工 brief 错)

## 类 20 实战沉淀

### 类 20.131: 派工起点必 fetch + merge-base
派工 brief v4.1 §0.5 要求派工起点 `git fetch origin` + `git merge-base --is-ancestor <base> HEAD`. 实测 `a35e4682b is ancestor of origin/main` ✅

### 类 20.123: 派工 brief grep 字符串必须经实测确认能匹配
**派工 brief grep "RAGQueryCache|cache_hit" 实测是假阴性**:
- `RAGQueryCache`: hybrid_retriever.py 用 `get_rag_query_cache()` 工厂, 不直接引用 class
- `cache_hit`: hybrid_retriever.py 不写该字段, 该字段只在 `RecallTrace` 观测层

派工 brief 排查 grep 字符串必须**先实测代码 grep 命中**, 否则极易误导排查方向.

### 类 20.132: cache hook `if raw_results:` 跳过空结果
**cache hook 设计契约**: `if raw_results:` 仅在 retrieve 返回非空时写缓存. 这是正确行为 (不缓存空结果). 派工 brief "3 次连续调用返回 list 不是 dict" 误判为 cache hook 缺失, 实测是 cache hit 时返回 `cached["results"]` (list 形态).

### 类 20.133: W100-BUGFIX 修复的是 citation, 不是 cache
W100-BUGFIX commit `1f6ce932f` 修复 `KnowledgeRefBlock` 段落高亮 3 处串联通修 (citation hook 顺序错位 + search_knowledge 老 API + RichContent 未转发), **不涉及 cache hook**.

## 关键文件路径

- `app/services/hybrid_retriever.py:584-643` — cache hook 代码 (实测存在且工作)
- `app/services/rag_query_cache.py:78-380` — `RAGQueryCache` class + `get_rag_query_cache()` 工厂
- `app/services/recall_observability.py:91` — `RecallTrace.cache_hit` 死字段 (主拍决策是否点亮)
- `memory/w100-cache-miss-closure-2026-08-02.md` — 本任务沉淀

## 后续建议 (主拍决策)

1. **`RecallTrace.cache_hit` 点亮** (W100-CACHE-OBSERVABILITY 子任务):
   - cache hook hit 时设置 `trace.cache_hit = True` + `trace.cache_similarity = 1.0` (精确命中)
   - 配合 grafana 7 面板 observability 已就绪 (W93 PR7)

2. **silent best-effort 升级**:
   - 当前 `logger.debug` 在 level=30 (WARNING) 容器下不显示
   - 升级到 WARNING 或加 metrics 计数器 (cache.hit.count / cache.miss.count / cache.write_fail.count)

3. **派工 brief 测试 query 模板**:
   - 提供预填充 cache 的 helper fixture
   - 避免派工 brief 用容器 KB 中无匹配的 query 测试, 误判 cache miss 为 cache hook 缺失

## 验证实测

| 测试 | 命令 | 结果 |
|------|------|------|
| Cache hook 代码存在 | `grep -n "rag_query_cache" app/services/hybrid_retriever.py` | 4 处 ✅ |
| Cache hook config 引用 | `grep -n "RAG_QUERY_CACHE_ENABLED" app/services/hybrid_retriever.py` | 2 处 ✅ |
| Cache module 完整 | `ls -la app/services/rag_query_cache.py` | 13835 bytes ✅ |
| Cache hit 实测 | 容器内 pre-populate + retrieve | 返回 cached data ✅ |
| Cache miss write | 直接 cache.set 调用 | ok=True ✅ |
| Cache hit get | 直接 cache.get 调用 | dict with results ✅ |
| W100-BUGFIX 不改 cache hook | `git show 1f6ce932f -- app/services/hybrid_retriever.py` | 0 cache hook diff ✅ |

详见 `memory/w100-cache-miss-closure-2026-08-02.md`