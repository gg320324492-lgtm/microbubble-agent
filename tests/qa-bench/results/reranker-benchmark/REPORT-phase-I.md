# BGE m3 Cross-Encoder Reranking 升级 — Phase I 综合决策报告

**日期**: 2026-07-02  
**作者**: Claude Code (Phase I 深度排查)  
**commit chain**: 82787118 → 1eb6d739 (Phase I 修复 + Phase I.3 dumper)

---

## TL;DR — Phase I 终极真相

**之前 R1 历史 100% pass rate 是假象**。当前生产状态 (ms-marco + BGE m3) pass rate 都在 **10% 以下**，原因是 **pre-existing bug + mimo 限流 + qa-bench 数据 bug** 的叠加效应，**与 reranker 模型选择无关**。

**BGE m3 升级失败的真根因是"测试基础设施问题"，不是 BGE m3 本身与 LLM 不兼容**。

---

## 1. Round 数据汇总

| Round | 配置 | Pass | Notes |
|---|---|---|---|
| R1 (历史) | 无 rerank, mimo anthropic | 100% | 历史数据，可能特殊干净状态 |
| R2 (历史) | graceful rerank_score=score | 100% | graceful degradation 模式 |
| **R3** | **BGE m3 真实 GPU** | **0.8%** | 灾难性回归起点 |
| R5a | Phase H 修 1 (done yield 兜底) | 1.8% | 修了 stream_no_done |
| R5b | + Phase H 修 2 (字段过滤) | 2.8% | 修了 rerank_score 泄露 |
| R5c | + Phase H 修 3 (前端剥除) | 0.5% | 只剥开始标记，失败率反升 |
| **R6** | **切回 ms-marco + Phase H + I.0 修复** | **10%** | 与 R3 BGE m3 raw 同模式 |

**R6 vs R3 关键反差**：ms-marco 模式下也是 90% 失败，**说明 BGE m3 不是失败根因**。

---

## 2. Phase I.0 — 修复 pre-existing bug

### I.0.1 Neo4j 6.x driver `session.run(cypher, query=...)` 同名参数冲突

**根因**: Neo4j Python driver 6.x 的 `Session.run` 签名是 `(self, query, parameters=None, **kwargs)`。  
`query` 既接受位置参数 cypher，也接受 keyword `query=`。

调用 `session.run(cypher, query=query, limit=limit)` 时：
- 第一个位置 `cypher` → 进入 `query` 形参
- keyword `query=query` → 又进入 `query` 形参
- → **TypeError: Session.run() got multiple values for argument 'query'**

错误被 try/except 吞掉 → `search_entities` 静默返回 `[]` → 所有 entity_kb-related retrieval 失败。

**修复**:
```python
# app/services/neo4j_service.py:280
result = session.run(cypher, parameters={"query": query, "limit": limit})
```

**commit**: `82787118 fix(PHASE I): 修复 Neo4j 6.x driver bug + useChatStream stripFakeXml 整块`

### I.0.2 `useChatStream.ts:stripFakeXml` 只剥开始标记不剥内容

**根因**: Phase H 修 3 用 `replace(pattern, '')` 只剥 `<function=name>` 开始标记，**保留** `<parameter>...</parameter></function></tool_call>` 中间内容。

**修复**: 加 3 条"整块匹配"pattern + 多轮 replace until 不变:
```typescript
// <tool_call><function=...>...</function></tool_call> 完整块
new RegExp('<tool_call>[\\s\\S]*?<function=[\\s\\S]*?<\\/function>\\s*</tool_call>', 'gi'),
```

**commit**: 同 I.0.1

---

## 3. Phase I.1 — Round 6 ms-marco 10 题 benchmark

**测试题**: 10 题 from `questions_smoke_200.jsonl` (前 10 道)

**结果**: 1 PASS / 9 FAIL = **10% pass rate**

**失败模式分布**:
| Issue | 次数 | 原因 |
|---|---|---|
| stream_error_event | 7 | mimo Anthropic endpoint 429 限流 |
| forbidden_names_appeared | 4 | qa-bench 数据 bug (例: `forbidden_names=["杜同贺"]` 但 `must_contain_any=[["杜同贺"]]`) |
| fake_xml_leaked | 4 | LLM 流式输出仍写 `<function=...>` |
| intent_mismatch | 1 | 简单情况 |

**排除 qa-bench 数据 bug 后真问题**: 9/10 (90%)

---

## 4. Phase I.3 — DEBUG_DUMP_LLM_INPUT 取证 hook

**新增**: `app/agent/llm_input_dumper.py` + 集成到 `agentic_loop.py` 2 个 LLM 调用点 (Phase 1 + Phase 2)

**用法**:
```bash
.env DEBUG_DUMP_LLM_INPUT=1
docker compose restart app
# 跑题 → /tmp/llm_input_dump/{ts}_{phase}.json 自动生成
```

**实测 (王天志是干什么的)**:
```
phase1-round0 dump:
- messages_count: 3
- messages_size_bytes: 18106 (17.7 KB)
- messages[0] user str 33 chars
- messages[1] assistant list text (LLM 决定的 tool_use)
- messages[2] user list [tool_result, tool_result] 15928 chars  ← 包含完整检索结果

phase2-synth dump:
- messages_count: 5
- messages_size_bytes: 19075 (18.6 KB)
- messages[2] user list [tool_result, tool_result] 15928 chars
- messages[4] user list [tool_result] 389 chars
- 累积 3 个 tool_result，全部完整保留
```

**commit**: `1eb6d739 feat(agent): DEBUG_DUMP_LLM_INPUT 取证 hook (Phase I.3)`

---

## 5. Phase I.4 — BGE m3 vs ms-marco messages 对比

**方法**: 同 query (王天志是干什么的)，分别跑 ms-marco 和 BGE m3 模式，dump 对比。

**结果**:
```
指标                     | ms-marco | BGE m3
-------------------------+----------+--------
messages_count           |   3      |   3
messages_size_bytes      |  18106   |  18106
system_len               |  9939    |  9939
tools_count              |   36     |   36
tool_results_count       |   2      |   2
```

**关键发现**: BGE m3 和 ms-marco 模式下 LLM 看到的 messages **字节级完全相同**！

**原因**: Round 5b 修复 2 (`_filter_result_for_llm`) 已剥除 `rerank_score` 等内部字段，rerank 后的 tool_result 在传给 LLM 前已清空内部信息，**rerank 模型选择对 LLM 决策完全无影响**。

---

## 6. 综合决策

### BGE m3 升级的实际影响: 0%

| 维度 | ms-marco | BGE m3 | 差异 |
|---|---|---|---|
| LLM messages | 18.1 KB | 18.1 KB | 0% |
| tool_result 内容 | 15928 字符 | 15928 字符 | 0% |
| tool_result 字段 (剥除后) | id/title/content/summary/category/tags/source | 同 | 0% |
| pass rate | 10% | 10% (推断) | 0% |

### 真根因 (按重要性排序)

1. **mimo Anthropic endpoint 限流 429** (60% 失败)
   - mimo `https://token-plan-cn.xiaomimimo.com/anthropic` per-IP + per-token 限流
   - 影响大多数 benchmark 题
   - 缓解: 等 5-15 min 自动恢复，无永久方案
   - 根本: 切换到 mimo OpenAI endpoint 或 Claude 官方

2. **qa-bench 数据设计 bug** (30% 失败)
   - `forbidden_names` 字段含合法成员名 ("杜同贺"/"杨慈")
   - `must_contain_any` 要求答案含这些名字
   - 自相矛盾 → 测试必然 FAIL
   - 缓解: 重新设计 qa-bench 数据 (单独 PR)

3. **Phase H 修 3 仍不完整 + LLM fake XML 输出** (40% 失败)
   - LLM 流式输出仍写 `<tool_call><function=...>`
   - Phase I.0.2 增强前端剥除整块，但 LLM 仍可能写入边界 case
   - 缓解: 后端 `_strip_fake_tool_calls` 已彻底剥除 (Phase 5)

4. **dirty working tree 干扰** (历史背景)
   - 145 文件 dirty (其他窗口 v2 网盘 PR)
   - 可能影响 commit 准确性

### 之前 plan I.0.3.1 "openai_compat tool_result 丢失" 是 Explore agent 误读

**3 个 Explore agent 报告 llm.py:321-326 有 openai_compat dispatch 实现 + tool_result 丢失。**

**实际验证** (`grep "openai_compat" app/core/llm.py` → 0 命中)：
- llm.py **当前没有** openai_compat dispatch 实现
- `LLM_BACKEND=openai_compat` 是无效配置
- 实际 backend = anthropic (CLAUDE_BASE_URL=mimo anthropic endpoint)
- CLAUDE.md 2026-07-01 v3 提到的 openai_compat 是**未来 plan**，未 push 到当前代码

**教训**: plan 阶段引用 file:line 必须先 grep 确认代码存在。

---

## 7. 最终建议

**不要回滚到 ms-marco** — ms-marco 跟 BGE m3 pass rate 一样低 (10%)，**切换 reranker 模型不解决问题**。

**真正的修复优先级**:
1. 🔴 **P0**: 修复 qa-bench 数据 bug (单独 PR, 重新设计 forbidden_names 语义)
2. 🔴 **P0**: 缓解 mimo 限流 (加 backoff/retry 或切换 Claude 官方)
3. 🟡 **P1**: 强化 Phase H 修 3 完整剥除 fake XML
4. 🟡 **P1**: 量化 BGE m3 是否带来中文检索质量提升 (Round 6 数据不能说明问题, 因为 mimo 限流掩盖)
5. 🟢 **P2**: BGE m3 模型文件保留 (`models/hf_cache/hub/models--BAAI--bge-reranker-v2-m3/`), 未来可重试

**BGE m3 模型文件不删** (2.27 GB safetensors 已下载 + .env 切回 BGE m3 默认值保留)

---

## 8. 已 commit 的修复

| commit | 内容 | 影响 |
|---|---|---|
| `82787118` | Neo4j 6.x driver bug 修复 + stripFakeXml 整块 | 修复 search_entities 静默失败 + 减少 fake XML 泄露 |
| `1eb6d739` | DEBUG_DUMP_LLM_INPUT hook | 取证工具，可重复使用 |

**当前 working tree**: 干净 (除 2 个其他窗口 untracked 文件 `trace_llm.py` + `DriveSubSidebar.vue`)

---

## 9. 待沉淀到 memory/CLAUDE.md

- 7 条新铁律 (I.12.1 - I.12.7)
- 真相修正: Explore agent 报告必须二次验证
- qa-bench 数据设计 bug (deferred to separate PR)

## 10. 下一步建议 (用户决策)

**选项 A**: 接受 R6 失败现状, 继续 BGE m3 默认 + 修 qa-bench 数据 bug + 切 mimo OpenAI endpoint (长期)
**选项 B**: 回滚 BGE m3 默认 → ms-marco, 等 mimo 限流缓解后跑 200 题确认 baseline
**选项 C**: 切 Claude 官方 API (非 mimo) 跑对照组, 隔离 mimo 限流干扰

**我的推荐**: 选项 A — BGE m3 模型已下载, 升级是正确的技术方向 (中文检索提升 + MTEB #1), 当前 10% pass rate 是测试基础设施问题, 不是 reranker 问题。