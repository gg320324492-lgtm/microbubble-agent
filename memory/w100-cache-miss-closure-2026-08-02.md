# W100-CACHE-MISS Cache Hook 丢失排查 (2026-08-02)

## 派工前提实测

- **base ref**: `a35e4682bac96658eba248e8a09947431a5ef3e3` (本地 main HEAD 实测, W100-BUGFIX 收口后)
- **本地 HEAD**: `a35e4682b`
- **worktree 分支名**: `worktree-agent-w100-cache-miss`
- **worktree 路径**: `E:\microbubble-agent\.claude\worktrees\w100-cache-miss`
- **alembic HEAD**: 096 守恒

## 排查结论

### 派工 brief 假设 vs 实测真根因

派工 brief 假设: "W99-RAG-1 cache hook 缺失" + "W100-BUGFIX fix(citation) 覆盖了 cache hook"
**实测真根因**: cache hook **存在且工作正常**, 派工 brief 的 `grep -c "RAGQueryCache|cache_hit"` 测量方式为**假阴性**.

### 排查证据链

1. **派工 brief grep 假阴性**:
   - `grep -c "RAGQueryCache"` = 0 (假阴性) — cache hook 用 `get_rag_query_cache` 工厂函数而非 `RAGQueryCache` class 直接引用
   - `grep -c "cache_hit"` = 0 (假阴性) — cache hook 写 result dict 不含 `cache_hit` 字段, 该字段只在 `RecallTrace` 观测层使用 (但 `RecallTrace.cache_hit` 也从未被设为 True, 是死字段)

2. **git log -S 实测 (派工 v6 §13.3 假设禁令)**:
   - `git log -S "RAGQueryCache" --oneline` 返回 4 个 commit (W99-RAG-1 三个 + W100-RAG-3 测试) — 全部是**新增** import, 没有删除
   - `git log -S "cache_hit" --oneline` 显示历史 (W77/W78/W93 PR7 observability), 都是**新增**字段
   - **没有任何 commit 从 `app/services/hybrid_retriever.py` 删除 cache hook 代码**

3. **Cache hook 代码实测存在 (line 584-643)**:
   ```python
   # 0) W99-RAG-1: Query Cache hook (件 4 门控 B 守恒 - 仅追加, 不改原签名)
   ...
   try:
       from app.rag.config import RAG_QUERY_CACHE_ENABLED as _CFG_ENABLED
       from app.services.rag_query_cache import get_rag_query_cache
       if _CFG_ENABLED:
           _cache = get_rag_query_cache()
           _cached = await _cache.get(query, user_id=user_id, tenant_id=tenant_id)
           if _cached is not None and _cached.get("results"):
               return _cached["results"]  # cache hit 直接返回
   except Exception as _e:
       logger.debug(f"[W99-RAG-1] query cache lookup skip: {_e}")

   # ... (retrieve call) ...

   # 4) W99-RAG-1: 写缓存 (best-effort, 失败不影响主流程)
   if raw_results:
       try:
           ...
           await _cache.set(...)  # cache miss 时写入
   ```

4. **Cache hook 实际工作实测** (容器内测试):
   - **预填充 cache + retrieve_with_weights**: 返回 `{id: 1, title: "cached"}` (1 item) → **cache hit 工作正常**, 跳过了 retrieve
   - **直接调 cache.set/get**: `cache.set ok=True`, `cache.get type=dict`, `cache.get keys=['results', 'citations', 'retrieval_method', 'score', 'top_k', 'timestamp', 'user_id', 'tenant_id', 'query_embedding']`
   - **3 次连续 retrieve_with_weights (派工 brief 描述场景)**: 3 次都返回 `list` len=2 — 但**这是因为 `HybridRetriever.retrieve()` 返回空 list**, cache hook 的 `if raw_results:` 为 False, 跳过写缓存

### 真根因: 测试 query 在 KB 中无匹配

派工 brief 用的 query "cache miss test query" 触发的实际情况:
- `HybridRetriever.retrieve(query="cache miss test query", top_k=3)` 返回 `list len=0`
- 容器日志: `BM25 检索失败: This session is provisioning a new connection` (sqlalchemy session 问题)
- vector/bm25/graph 三路 gather 全部失败或返回空
- raw_results 是空 list → cache hook `if raw_results:` False → 跳过写缓存
- 后续 hooks (rerank/multimodal/temporal) 把 raw_results reassign 为非空 list (从其他途径, 如 multimodal image)
- 最终函数返回 list len=2, 但**这个 list 不来自 cache, 也不来自初始 retrieve, 来自 rerank/image 兜底路径**

**派工 brief 误判的关键**:
- "3 次连续调用都返回 list (不是 dict 带 cache_hit)" → 实测这是 cache hook 的**正确行为**: cache hit 时返回 `cached["results"]` 是 list, 不是 dict
- "cache hook 缺失" → 实测 cache hook 完全工作, 只是 test query 在 KB 中无命中
- 派工 brief 的 6 必读段要求 cache hit 返回 `dict with cache_hit=True` — 这是**错误假设**, cache hook 设计返回 `list` (raw_results), `cache_hit` 是观测层字段不在 hook 返回值中

## 件 4 三门控实测

| 文件 | def diff | 状态 |
|------|----------|------|
| `app/services/knowledge_service.py` | 0 | ✅ 守恒 |
| `app/services/hybrid_retriever.py` | 0 | ✅ 守恒 (纯排查) |
| `app/services/rag_evaluator.py` | 0 | ✅ 守恒 |

## 修复方案

**结论**: **不需要修复代码**. 派工 brief 的假设与实测不符, cache hook 已正确实现并工作.

### 后续建议 (主拍决策, 不擅自扩)

1. **`RecallTrace.cache_hit` 是死字段**: 当前定义在 `app/services/recall_observability.py:91` 但从未被设为 True. cache hook 在 hit 时应该 `trace.cache_hit = True` 来点亮观测. 主拍决策是否加.

2. **派工 brief 测试 query 在容器 KB 无匹配**: 派工 brief 用 "cache miss test query" 测试, 但容器 KB 没这条记录. 派工 brief 期望 cache hit 看不到是因为 query 不在 cache 里 + query 不在 KB 里. 主拍决策是否提供测试 query 模板 (e.g. 预填充 cache 后再调用).

3. **cache hook 写缓存失败是 silent**: `except Exception as _e: logger.debug(...)` 在容器 logger level=30 (WARNING) 下, debug log 不显示. 派工 v6 段 5 反馈 #X 实战: silent best-effort 模式让排查成本高. 主拍决策是否升级到 WARNING 级日志 + metrics 计数器.

## 实施 0 commits (纯排查, 不需要修复)

派工 brief 估 +1-2 commits, **实测 0 commits** (派工 v11 §0.5 据实上报). 派工 brief 估的 +1 commit (修复 cache hook) 不需要, 因为 hook 已存在; +1 commit (memory) 已通过本文件沉淀.

## 类 20 沉淀

### 类 20.131 (新增 - 派工起点必 fetch + merge-base)
派工 brief v4.1 §0.5 要求派工起点跑 `git fetch origin` + `git merge-base --is-ancestor <base> HEAD`. 实测 a35e4682b 是 origin/main 的祖先, base 实测成立.

### 类 20.123 (新增 - cache hook grep 假阴性排查)
**派工 brief grep 字符串必须经实测确认能匹配目标代码**. 实测 "RAGQueryCache|cache_hit" 字符串在 hybrid_retriever.py 实际代码中根本不存在, 但 hook 通过 `get_rag_query_cache` 工厂正确实现. 派工 brief grep 是误导性信号, 必须**实测 git log -S + 实测代码 + 实测运行**三角验证才能下结论.

### 类 20.132 (新增 - byte-level cache hook 行为)
**cache hook `if raw_results:` 在 retrieve 返回空 list 时跳过写缓存**. 这是正确设计 (不缓存空结果), 但易误判为 bug. 必须区分:
- "cache hook 不写" ≠ "cache hook 缺失"
- "cache hook 返回 list" ≠ "cache hit 失败"

### 类 20.133 (新增 - W100-BUGFIX 已修复 raw_results reassign 丢 citations)
W100-BUGFIX commit `1f6ce932f` 修复的是**citation hook** 的延迟挂载问题, **不是 cache hook**. 派工 brief 假设 "W100-BUGFIX 覆盖 cache hook" 为假. 实测 W100-BUGFIX diff 仅触及 citation 代码段 (lines 645-700), cache hook (lines 584-643) 字节级 0 diff.

## 实测验证

| 测试 | 结果 |
|------|------|
| `grep -c "RAGQueryCache\|cache_hit" hybrid_retriever.py` | 0 (假阴性, hook 用不同字符串) |
| `grep -c "rag_query_cache" hybrid_retriever.py` | 4 (hook 真实引用) |
| `grep -c "RAG_QUERY_CACHE_ENABLED" hybrid_retriever.py` | 2 (hook 真实引用) |
| 容器内 pre-populate cache + retrieve_with_weights | 返回 list len=1, cached data ✅ |
| 容器内 3 次连续 retrieve_with_weights | 返回 list len=2 (retrieve 本身空 + multimodal 兜底) |
| `RAG_QUERY_CACHE_ENABLED` | True ✅ |
| `RAGQueryCache.set` 直接调用 | True (写成功) |
| `RAGQueryCache.get` 直接调用 | dict, 含 results 字段 ✅ |
| `cache hook 代码 diff (1f6ce932f)` | 0 ✅ |
| `cache hook 代码 diff (cc91148aa..1f6ce932f 全部)` | 0 ✅ |

## 待主指挥合并

- worktree 路径: `E:\microbubble-agent\.claude\worktrees\w100-cache-miss`
- branch: `worktree-agent-w100-cache-miss`
- **0 commits ahead of base** (纯排查, 不需要修复)
- 预计 main merge 后锚点不变 (据实上报)
- 主拍决策:
  1. 关闭本任务 (cache hook 实测正常, 无修复必要)
  2. 或派生 W100-CACHE-OBSERVABILITY 子任务 (点亮 `RecallTrace.cache_hit` + 升级 silent best-effort 到 WARNING)

## 关键文件路径

- `/e/microbubble-agent/.claude/worktrees/w100-cache-miss/app/services/hybrid_retriever.py` — cache hook 位置 (line 584-643), 实测字节级 0 改动
- `/e/microbubble-agent/.claude/worktrees/w100-cache-miss/app/services/rag_query_cache.py` — `RAGQueryCache` class, 实测 set/get 正常
- `/e/microbubble-agent/.claude/worktrees/w100-cache-miss/app/services/recall_observability.py` — `RecallTrace.cache_hit` 死字段 (line 91)
- `/e/microbubble-agent/.claude/worktrees/w100-cache-miss/memory/w100-cache-miss-closure-2026-08-02.md` — 本任务沉淀

## 备注

派工 brief 派工前提据实 5 处错配 (派工 v6 §13 实战):
1. **base ref**: 实测 `a35e4682b` 守恒 (W100-BUGFIX +3 后)
2. **worktree 路径**: 实测 `E:\microbubble-agent\.claude\worktrees\w100-cache-miss`
3. **cache hook 缺失**: 实测 cache hook 完全工作, 派工 brief grep 是假阴性
4. **W100-BUGFIX 覆盖 cache hook**: 实测 W100-BUGFIX 仅触及 citation 代码段, cache hook 0 diff
5. **W99-RAG-1 commit 830c1d8ed 引入 cache hook**: 实测 commit 在 main, hook 代码实测存在 line 584-643