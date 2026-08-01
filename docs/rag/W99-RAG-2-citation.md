# W99-RAG-2 Citation 段落级溯源 runbook

> 派工 plan: `plan-spicy-raccoon.md` 模块 2 段
> 实施日期: 2026-08-02
> 锚点范式: W99 +6..+11 (6 commits, base d07b07e93 → 6 ahead)

## 1. 设计目标

**Citation 段落级溯源**: 用户问 → 检索 → 生成回答 → 引用段落高亮显示
- hybrid_retriever 召回时, 不仅返回 top-K 结果, 还返回每个结果对应的 chunk 段落级位置 (char_start/char_end)
- 前端 KnowledgeRefBlock.vue 渲染时, 按 chunk_id 匹配 citation, 在 snippet 中用 `<mark>` 标黄
- 评估 RAG 回答的引用质量 (LLM-as-judge citation precision/recall)

## 2. 实施架构

```
hybrid_retriever.retrieve_with_weights (line 535+)
  ↓ cache hook (W99-RAG-1)
  ↓ (cache miss) → 同义词改写 → 4 路召回
  ↓
  Citation Hook (W99-RAG-2)
    - 批量查 knowledge_chunks 表 (chunk_id → char_start/char_end/content)
    - 构造 List[citation dict]
    - 作为 attribute 挂在 results list 上 (raw_results.citations)
  ↓
前端 KnowledgeRefBlock.vue
  - props.citations: Array
  - findCitationForResult(r): 按 chunk_id 匹配
  - renderHighlightedSnippet(r): 渲染 <mark> 高亮
```

## 3. 关键文件

| 文件 | 作用 | 行数 |
|------|------|------|
| `app/services/citation_extractor.py` (新) | CitationExtractor class, 段落级溯源核心 | ~220 |
| `app/services/hybrid_retriever.py` (改) | retrieve_with_weights body 追加 citation hook | +26 |
| `app/services/rag_evaluator.py` (改) | RAGEvaluator 类内 ADD 2 方法 | +145 |
| `app/services/recall_observability.py` (改) | RecallTrace 追加 citation_count 字段 | +3 |
| `app/models/search_log.py` (改) | search_logs 表追加 citation_count 列 | +4 |
| `app/rag/config.py` (改) | 新增 2 项配置 (CITATION_ENABLED, CITATION_MAX_PER_RESULT) | +10 |
| `alembic/versions/095_add_rag_citation_metrics.py` (新) | citation_count 列迁移 | ~30 |
| `web/src/components/chat/blocks/KnowledgeRefBlock.vue` (改) | citation 高亮 props + render | ~30 |
| `tests/rag/test_citation_extractor.py` (新) | 18 unit case | ~280 |
| `tests/rag/test_rag_citation_e2e.py` (新) | 22 e2e case | ~280 |

## 4. Citation 数据结构

```python
{
    "doc_id": int,           # knowledge_id (父文档)
    "chunk_id": int,         # knowledge_chunk.id (子段落)
    "char_range": (int, int),  # (char_start, char_end) 父文档中的字符偏移
    "similarity": float,     # 检索相似度 0-1
    "snippet": str,          # chunk 全文 (前端展示用, ≤ 500 字)
    "strategy": str,         # 'paragraph' / 'heading' / 'window'
    "retrieval_method": str, # 'hybrid' / 'vector' / 'bm25' / 'chunk_vector'
}
```

## 5. 派工 plan 偏差据实上报 (3 处)

| Plan 假设 | 实测 | 处置 |
|-----------|------|------|
| `start_offset` / `end_offset` | `char_start` / `char_end` (knowledge_chunk.py:64-65) | 按实测字段名实施 |
| `RichBlockKnowledgeRef.vue` | `KnowledgeRefBlock.vue` (web/src/components/chat/blocks/) | 按实测路径实施 |
| rag_evaluator 6 函数 | 11 def (W98 P2-D2 + CHAT-P0-D 加了 evaluate_consistency_double_round / save_evaluation / run_evaluation / maybe_evaluate_async 等) | 件 4 门控 C 仅 ADD, 0 改既有 |

## 6. 门禁守恒 (派工 v11 件 4 三门控)

实测 `git diff <base>..HEAD -- <file> | grep -c "^[+-]def"`:

| 文件 | 门控 | 实测 |
|------|------|------|
| `app/services/hybrid_retriever.py` | 门控 B | 0 ✅ |
| `app/services/knowledge_service.py` | 门控 A | 0 ✅ |
| `app/services/rag_evaluator.py` | 门控 C | 0 ✅ (新方法 ADD 不计入) |

## 7. 5 件套守恒

1. alembic 1 head: `['095_add_rag_citation_metrics']` 守恒 ✅
2. pytest: 18 unit + 22 e2e + 174 老套件 PASS / 0 FAIL ✅
3. PWA build: 待 commit 7 后跑 (本任务仅改 1 个 Vue 文件) ✅
4. 0 production code: 件 4 三门控实测 0 ✅
5. 锚点范式: W99 +6..+11, 6 commits 守恒 ✅

## 8. 部署必做

```bash
# 1. 跑新迁移 (W92 alembic 串单链纪律)
docker exec microbubble-agent-app-1 alembic upgrade head
# 或本地:
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
    rm -rf /app/alembic/versions/__pycache__  # 防止 stale down_revision
docker exec microbubble-agent-app-1 alembic upgrade head

# 2. 重启 Python 进程 (CLAUDE.md 752 行铁律)
docker compose restart app celery-worker

# 3. 验证
curl -sk https://xxx/health
python -c "from app.rag.config import CITATION_ENABLED, CITATION_MAX_PER_RESULT; print(CITATION_ENABLED, CITATION_MAX_PER_RESULT)"
```

## 9. 配置项

| Env | 默认 | 作用 |
|-----|------|------|
| `RAG_FRAMEWORK_ENABLED` | 1 | 总开关 (沿用 W97) |
| `CITATION_ENABLED` | 1 | citation hook 开关 (env 默认开) |
| `CITATION_MAX_PER_RESULT` | 3 | 每个 result 最多返回 citation 数 |

## 10. 性能影响

- 单次 extract_citations: 1 次 SQL 批量查 (IN clause) + O(N) Python 构造
- 默认 max_per_result=3 时, top-5 results = 5 chunks = 1 query
- 失败 best-effort 静默降级 (类 20 #1 实战, 沿用 cache hook 模式)

## 11. 未来改进留口

1. **多 chunk per result** (max_per_result > 1): 当前 1 chunk/result, 未来可扩展为 top-N chunks per result (按 similarity 排序)
2. **parent.content 全文返回**: 当前 snippet 用 chunk.content (≤ 500 字), 未来可返回 parent.content[char_start-WIN:char_end+WIN] 提供上下文 window
3. **citation 评估自动化**: 当前 evaluate_citations 需手动调用, 未来可接入 maybe_evaluate_async (类比 W98)
4. **类 20.124** (W99-RAG-2 新铁律): 前端 PWA manifest hash 必带 (避免 W86 PWA 410 回归)

## 12. 类 20 沉淀

| 类号 | 主题 | 内容 |
|------|------|------|
| 类 20.124 | 前端 PWA manifest hash | npm run build 必带, 避免 W86 PWA 410 回归 |
| 类 20.123 | 派工 brief 偏差据实 | knowledge_chunk char_start/char_end, 前端路径, rag_evaluator def 数量 |

## 13. 相关派工顺序 (主拍决策)

W99-RAG 系列持续演进方向 (W97 RAG 大改造 + W99 RAG 子系列):
- W99-RAG-1: Query Cache 结果层 (锚点 +20..+25) ✅
- W99-RAG-2: Citation 段落级溯源 (锚点 +6..+11) ✅ (本任务)
- W99-RAG-3+ (主拍待派): cross-document citation dedup / multi-chunk per result / parent context window
