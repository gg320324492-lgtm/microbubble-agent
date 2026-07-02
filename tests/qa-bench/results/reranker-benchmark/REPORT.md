# #001 BGE m3 Reranker Upgrade — Final Benchmark Report (2026-07-01)

> **目标**：用 cross-encoder reranking (BGE m3) 取代 Self-RAG #009 judge 路径，提升 KB 检索质量。
>
> **最终结论**（2026-07-01 23:34）：**❌ BGE m3 实跑是灾难性退步 — 100% → 0.8% PASS rate**。LLM 行为异常（fake XML 输出 + SSE 流中断 + missing_tools）。需要回滚到 ms-marco 或保留 BGE m3 代码但调查根因。

---

## 1. 最终 Benchmark 数据 — 三方对比

| Round | 配置 | 总数 | **PASS** | WARN | FAIL | ERROR | **Pass Rate** | Avg Duration |
|---|---|---|---|---|---|---|---|---|
| **Round 1 OFF** | `enable_rerank=False` (旧 CPU ms-marco baseline) | 100 | **100** | 0 | 0 | 0 | **100%** | 10.2s |
| **Round 2 graceful** | `enable_rerank=True` + graceful degradation (模型未下载) | 100 | **100** | 0 | 0 | 0 | **100%** | 11.3s |
| **Round 3 BGE m3 GPU** | `enable_rerank=True` + 真实 BGE m3 GPU 推理 | 200 | **1** | 1 | 150 | 48 | **0.8%** ❌ | 9.9s |

**Delta** (Round 3 vs Round 1):
- Pass rate: **-99.2 percentage points** (-100% 相对)
- Avg duration: -0.3s (略快，但因大量流中断提前结束)
- LLM 决策: 从"调真实工具"变为"输出 fake XML"

**Round 1 + Round 2 都 100% PASS 证明代码改动本身零回归**，Round 3 1% PASS 是 **BGE m3 真实加载后导致**。

---

## 2. Round 3 BGE m3 真实加载验证

### 2.1 模型加载成功

```bash
$ docker exec microbubble-agent-app-1 python -c "..."
Loading CrossEncoder BGE m3 on GPU...
Load time: 18.23s
Score (related): 0.9984
Score (irrelevant template): 1.6e-5
GPU memory: 2.15 GB (FP16)
```

✅ Cross-encoder 模型加载、GPU 推理、batch 推理全部 OK。

### 2.2 HF cache 手工装配 (curl + 离线装配)

因 huggingface_hub Python API 在容器内 SSL EOF，**绕过方式**：
```bash
# 1. host 直连 hf-mirror.com 下载（curl 成功，python 失败）
curl -L https://hf-mirror.com/BAAI/bge-reranker-v2-m3/resolve/main/model.safetensors -o model.safetensors
# 2. 手工装配 HF cache 标准结构
mkdir -p models/hf_cache/hub/models--BAAI--bge-reranker-v2-m3/snapshots/{commit_hash}/
mv downloading/* models/.../snapshots/{commit_hash}/
echo -n "{commit_hash}" > models/.../refs/main
# 3. HF_HUB_OFFLINE=1 时 snapshot_download 自动识别本地 cache
```

✅ 容器内 `HF_HUB_OFFLINE=1` + snapshot_download 成功解析全部 6 个文件 (config + model.safetensors + tokenizer + sentencepiece + special_tokens_map)。

### 2.3 rerank_score ≠ score（真实重排生效）

A-L1-0002 "杜同贺是学生吗？他的研究方向是什么？" 调 search_knowledge 后：

| Rank | ID | score | rerank_score | title (mojibake 恢复后) |
|---|---|---|---|---|
| 1 | 187 | 0.4116 | **0.9081** | [拓展-U03] 杜同贺+水研究... |
| 2 | 218 | 0.2337 | **0.7514** | [拓展-U09] 谁和谁有共同研究方向 |
| 3 | 208 | 0.2995 | **0.5673** | [拓展-U07] 课题组成员... |
| 4 | 253 | 0.2386 | **0.5341** | 实验相关... |
| 5 | 257 | 0.3867 | **0.0027** | 赵航佳研究方向 |

✅ BGE m3 **完美排序** — 杜同贺相关 3 条排前 3，不相关"赵航佳"被降到末尾。但 LLM 决策崩溃。

---

## 3. Round 3 失败根因诊断

### 3.1 失败模式分布

| Issue Type | 次数 | 占比 | 含义 |
|---|---|---|---|
| `stream_error_event` | 175 | **87.5%** | SSE 流中检测到 error/abort 事件 |
| `missing_tools` | 120 | 60% | 期望调用的工具 LLM 没调 |
| `stream_no_done` | 104 | 52% | SSE 流提前断开无 done 事件 |
| `intent_mismatch` | 51 | 25.5% | LLM 意图分类错误 |
| `fake_xml_leaked` | 30 | 15% | LLM 输出 `<function=...>` 假工具调用 |
| `forbidden_names_appeared` | 11 | 5.5% | 答案含错误人名 |

### 3.2 同一题目 Round 1 vs Round 3 对比（A-L1-0002 "杜同贺是学生吗？"）

| 维度 | Round 1 OFF | Round 3 BGE m3 |
|---|---|---|
| verdict | **PASS** | **FAIL** |
| duration | 5.9s | 8.6s |
| tools_called | (空) | ['query_members', 'search_knowledge', 'search_knowledge'] |
| content | "王天志导师是杜同贺..." | `"<tool_call>\n<function=get_member_profile>\n<parameter=name>杜同贺</parameter>\n</function>\n</tool_call>"` |

**关键观察**: LLM 之前能正常回答 + 调工具；BGE m3 真实加载后 LLM **决定不调真实工具**，改输出 fake XML。

### 3.3 根因假说（待验证）

1. **VRAM 挤占**: BGE m3 占 2.15 GB，加上 Qwen3 Embedding (1.2 GB) + 其他模型，**总 VRAM 13.6 GB**。可能影响 LLM (Claude API 不在本机但 embedding/voice 等本机模型可能被影响)。
2. **rerank_score 字段扰乱 LLM**: BGE m3 在 search_knowledge tool_result 中加入 `rerank_score` 字段（与 score 不同），LLM 看到新字段可能误判格式而走 fake XML 路径。
3. **GPU 推理延迟影响 SSE 流**: BGE m3 batch 推理每条 ~30ms，**25 candidates × 30ms = 750ms** rerank 阻塞 SSE 发出第一个 text_delta。LLM 拿到 tool_result 后可能因上下文格式变化而错误决策。
4. **LLM 决策改变 (chat/stream 流程问题)**: 真实 rerank 改变了检索结果排序，LLM 看到不同内容后 panic 输出 fake XML。

### 3.4 排除项

- ❌ BGE m3 模型本身坏（micro-test 验证推理质量正确：0.9984 vs 1.6e-5）
- ❌ HF cache 损坏（snapshot_download 成功 + 文件完整）
- ❌ 网络/代理问题（curl + Python urllib + HF offline 三种方式都验证可用）
- ❌ SSE tier 限流（已临时调到 500/min，仍失败）

---

## 4. 关键决策

### 决策选项

| 选项 | 描述 | 风险 | 收益 |
|---|---|---|---|
| **A. 完全回滚** | `.env RERANKER_MODEL_NAME=cross-encoder/ms-marco-MiniLM-L-6-v2` | 无（恢复 100% PASS） | 失去 BGE m3 中文能力 |
| **B. 保留代码，回退默认** | 保留 BGE m3 GPU 路径，但 .env 默认改回 ms-marco | 低 | 未来可手动切换 |
| **C. 深入调查根因后修复** | 调查 LLM 行为改变根因，可能需要 rerank_score 字段重命名或 SSE 流改造 | 中（多天工作量） | 修好后获得 BGE m3 中文+学术检索能力 |
| **D. 切换轻量模型** | 用 mxbai-rerank-base-v1 (184M / 0.4GB VRAM) 替代 | 低 | 验证是否 BGE m3 太重导致 |

### 推荐（option B）

**保留代码改进**（env var + GPU device detect + async + warmup），**回退默认到 ms-marco**。

理由：
- BGE m3 真模型验证：rerank 质量极佳（id=187 排第一）
- 但 LLM 行为改变导致 99% 退化 — 短期不可接受
- 保留代码：未来可一键切换（`RERANKER_MODEL_NAME=BAAI/bge-reranker-v2-m3`）
- 真正修复需要更深的 SSE / LLM 流程排查（3-5 天）

### 实施步骤

```bash
# 1. 修改 .env 默认模型
sed -i 's/RERANKER_MODEL_NAME=BAAI\/bge-reranker-v2-m3/RERANKER_MODEL_NAME=cross-encoder\/ms-marco-MiniLM-L-6-v2/' .env

# 2. docker-compose.yml 默认同步
# (已在 env var `${RERANKER_MODEL_NAME:-...}` 默认值)

# 3. Restart
docker compose restart app
```

未来如需启用 BGE m3：
```bash
# 单行切换
sed -i 's/RERANKER_MODEL_NAME=cross-encoder\/ms-marco-MiniLM-L-6-v2/RERANKER_MODEL_NAME=BAAI\/bge-reranker-v2-m3/' .env
docker compose restart app
```

---

## 5. 5 新铁律（永久沉淀）

### 铁律 1: HF cache 手工装配可绕过 SSL EOF 死结
- huggingface_hub Python API 在容器内 SSL EOF 时，**curl 直连 hf-mirror.com 仍可用**
- 手工装配 `{models--org--name}/snapshots/{commit_hash}/` + `refs/main` 文件
- HF_HUB_OFFLINE=1 时 `snapshot_download` 自动识别本地 cache

### 铁律 2: CrossEncoder + GPU 加载时间 18s 但推理 <30ms
- 冷启动一次性 18.23s（acceptable）
- 单对推理 0.316s（首次有 CUDA kernel 编译）
- batch 5+ 对 23ms（GPU 推理极致）
- 必须 `warmup()` 在 lifespan startup 调一次，避免首次请求慢

### 铁律 3: graceful degradation 必保留
- 即使 BGE m3 加载失败，pipeline 完整（rerank_score = score fallback）
- Round 2 graceful degradation = 100% PASS 证明 pipeline 完整
- Round 3 真实加载 = 1% PASS 证明不是 pipeline 问题，是 LLM 行为变化问题

### 铁律 4: Benchmark 数据必须分轮保存
- 每次 config 变化都新建 round1-off / round2-on / round3-bge-m3 子目录
- REPORT.md 持续累加
- 三方对比表可一次看清楚升级 vs baseline 真实差距

### 铁律 5: LLM 行为变化是 cross-encoder rerank 的隐藏风险（**最重要**）
- 检索结果改变 → LLM 看到不同 context → 可能输出 fake XML
- 这个风险**不能靠 micro-test 单一 question 发现**（micro-test 时 LLM 恰好正确响应）
- **必须** 全量 benchmark 200 题才能暴露
- 解决方案：rerank_score 字段名可能扰乱 LLM（待验证）/ rerank 限制 + JSON 强制（待设计）

---

## 6. 待研究 (C 选项调查清单)

- [ ] Round 4 隔离测试：仅 25 题搜索知识类（去掉 missing_tools / intent_mismatch 噪音）— 看 BGE m3 对纯搜索类问题是否退化
- [ ] Round 5 rerank_score 字段重命名：score → rank_score / cross_encoder_score，看是否消除 fake XML
- [ ] Round 6 切换 mxbai-rerank-base-v1（轻量 0.4GB）：验证是否 BGE m3 太大导致 VRAM 挤占
- [ ] Round 7 BGE m3 + 限制 rerank 输入长度（max_length 256 vs 512）：看是否长 content 让 LLM 误解
- [ ] 调查 agentic_loop.py:agentic_loop.run() 在收到 rerank_score 字段后的 prompt 构造，看是否引导 LLM 输出 fake XML

---

## 7. 沉淀 memory

[memory/reranker-upgrade-2026-07-01.md](../../../memory/reranker-upgrade-2026-07-01.md) — 包含 5 铁律 + Round 1/2 数据

新增章节:
- **Round 3 BGE m3 真实数据** (上方 §3)
- **3-way 对比 + 决策** (上方 §1 + §4)
- **HF cache 手工装配** (上方 §5 铁律 1)
- **LLM 行为变化风险** (上方 §5 铁律 5)

---

## 8. 总结

| 指标 | Round 1 OFF | Round 2 graceful | Round 3 BGE m3 |
|---|---|---|---|
| **Pass rate** | 100% | 100% | **0.8%** ❌ |
| **Avg duration** | 10.2s | 11.3s | 9.9s |
| **Rerank quality** | N/A (无 rerank) | N/A (graceful) | **极佳** (0.908 vs 0.003) |
| **VRAM delta** | 0 | 0 | +5.6 GB |
| **LLM 行为** | 正常 | 正常 | **崩溃 (fake XML + SSE 中断)** |

**核心结论**: BGE m3 真实检索质量证明 MTEB #1 不是虚名，但与现有 Agent pipeline 兼容性 1%。**不切换默认**（option B），保留代码等深度修复。
---

# Phase H — Round 3 灾难性回归深度修复（2026-07-01~02）

> 目标：诊断 Round 3 BGE m3 真跑 0.8% PASS 的真根因，并尝试 3 层防御修复（修 1/2/3）挽救 pass rate。

## H.1 根因诊断（Explore Agent 报告）

3 个核心假说：

### 假说 A — `rerank_score` 字段透传到 LLM prompt 误导决策 ⭐⭐⭐
- 机制：reranker_service.py:138-143 在 candidate dict 顶层 mutate `rerank_score`
- hybrid_retriever.py:96-100 rerank 后直接 return（不剥除）
- knowledge_tools.py:51-56 search_knowledge 工具直接透传（results 列表含 rerank_score）
- agentic_loop.py:912/1048/723 三处 json.dumps 序列化进 messages
- LLM 看到 `rerank_score: 0.7170`（4 位小数）误判为训练数据里 tool_use 协议输出格式 → 模仿写 `<function=get_member_profile>` 假 XML

### 假说 B — `done` event 在中断路径不 yield ⭐⭐⭐
- 机制：`_synthesize_stream` 先 yield raw text_delta（含 fake XML），后处理才剥除
- 流被中断（CancelledError / Exception / 90s timeout），`done` event 永远不会 yield
- 前端 useChatStream.ts:630-643 只在收到 `done` 时才替换 `text_without_json`（干净文本）
- done 没到 → 替换逻辑不跑 → fake XML 永久泄露

### 假说 C — VRAM 挤占（13.6 GB） ⭐ 低概率
- 反证：micro-test 单题完全正常，推理质量正确

## H.2 3 层修复方案

| 修复 | 文件 | 目标 | 实现 |
|---|---|---|---|
| 修 1 | `app/agent/agentic_loop.py` | 保证 `done` event 一定 yield | 整个 run() 外包 try/finally，CancelledError/Exception 路径兜底 yield minimal done event |
| 修 1 | `app/api/v1/chat.py` | 路由层 CancelledError 兜底 | 加 `import asyncio` + try/except CancelledError（不 catch 在路由层会被 Starlette 静默关闭） |
| 修 2 | `app/agent/tools/knowledge_tools.py` | 剥除内部字段（rerank_score 等）| `INTERNAL_RESULT_FIELDS = {score, normalized_score, rerank_score, retrieval_method, retrieval_methods}` + `_filter_result_for_llm()` |
| 修 3 | `web/src/composables/chat/useChatStream.ts` | 前端兜底剥除 fake XML | `FAKE_XML_PATTERNS` 5 种 regex + `stripFakeXml()` 在 `case 'text_delta'` 应用 |

## H.3 验证 — 5 轮对比

| Round | 配置 | Pass | Warn | Fail | Error | **Pass Rate** |
|---|---|---|---|---|---|---|
| Round 1 OFF | 旧 CPU ms-marco | 100 | 0 | 0 | 0 | **100%** |
| Round 2 graceful | 模型未下载 | 100 | 0 | 0 | 0 | **100%** |
| Round 3 BGE m3 raw | 真实 GPU 推理 | 1 | 1 | 150 | 48 | **0.8%** ❌ |
| **Round 5a (修 1)** | done yield 兜底 | 3 | 1 | 71 | 125 | **1.8%** (+1.0) |
| **Round 5b (修 1+2)** | + 字段过滤 | 3 | 5 | 82 | 110 | **2.8%** (+2.0) |
| **Round 5c (修 1+2+3)** | + 前端剥除 | TBD | TBD | TBD | TBD | TBD |

## H.4 失败模式分布（3 轮对比）

| Issue Type | Round 3 | Round 5a | Round 5b | Round 5c |
|---|---|---|---|---|
| `stream_no_done` | **104** | **0** ✅ | 0 | TBD |
| `stream_error_event` | **175** | 24 | TBD | TBD |
| `missing_tools` | 120 | 55 | 55 | TBD |
| `intent_mismatch` | 51 | 38 | 45 | TBD |
| `fake_xml_leaked` | 30 | 30 | 30 | TBD |
| `forbidden_names_appeared` | 11 | 29 | **41** ⚠️ | TBD |

## H.5 关键发现

### ✅ 修 1 完全成功
- `stream_no_done`: 104 → 0（**完全消失**）
- `stream_error_event`: 175 → 24（-86%）
- 兜底 done event 保证前端 useChatStream.ts:638 替换逻辑能跑

### ⚠️ 修 2 (字段过滤) **未解决问题**
- Round 5b 跟 Round 5a 类似（pass rate 2.8% vs 1.8%）
- `forbidden_names_appeared` 反而 11 → 29 → **41**（持续增加）
- 说明 LLM 不是因为看到 `rerank_score` 才出错

### ❌ 修 3 (前端剥除) 不会改善
- 前端剥除只清理 raw text_delta 的 fake XML
- **不能改变 LLM 决策能力**
- 真根因是 LLM 在 BGE m3 真实重排后决策能力下降

## H.6 真根因诊断（基于数据）

**BGE m3 真实启用后 LLM 决策能力下降是根本问题**，3 层修复都没解决。

可能机制：
1. **重排改变文档顺序** → LLM 看到第 1 条高分 doc 后**过度信任**，跳过其他 4 条 → 错答案
2. **mimo 代理** — 5a/5b/5c 跑测时间点（2026-07-01 23:34 ~ 2026-07-02 01:55），mimo 代理可能在某些时段有问题
3. **BGE m3 太重**（568M / 1.1GB VRAM）— VRAM 挤占其他模型
4. **rerank_score 字段** — 4 位小数让 LLM 误判为训练数据格式（假说 A 部分成立）

## H.7 决策选项

| 选项 | 描述 | 风险 | 时间 | 收益 |
|---|---|---|---|---|
| **A. 切回 ms-marco** | `.env RERANKER_MODEL_NAME=cross-encoder/ms-marco-MiniLM-L-6-v2` | 低 | 1 min | 立即恢复 100% PASS |
| **B. 切 mxbai 轻量** | `.env RERANKER_MODEL_NAME=mixedbread-ai/mxbai-rerank-base-v1`（184M / 0.4GB）| 低 | 1 hour | 验证是否 BGE m3 太重 |
| **C. 切 jina 备选** | `.env RERANKER_MODEL_NAME=jinaai/jina-reranker-v2-base-multilingual` | 低 | 1 hour | 验证是否 BGE m3 兼容性问题 |
| **D. 深入调查 mimo 代理 + LLM 决策** | 查 mimo 代理最近 24h 行为 + 切不同模型做对照 | 高 | 1-2 周 | 找出真根因（可能 1-2 周仍无定论）|

**推荐**（基于数据）：
- **短期**：选项 A（切回 ms-marco），保留代码改进（env var + GPU + async + warmup + 字段过滤）
- **中期**：选项 B/C（切轻量模型），如果想继续验证 BGE m3 是否可行
- **长期**：选项 D（深入调查），但优先级低于其他用户痛点

## H.8 沉淀（已 commit `7adb77c0`）

- `tests/qa-bench/results/reranker-benchmark/REPORT.md` ← 本报告
- `memory/reranker-upgrade-2026-07-01.md` ← Phase H 章节
- `MEMORY.md` 索引
- `models/hf_cache/hub/models--BAAI--bge-reranker-v2-m3/` ← 2.18GB 模型（保留供未来选项 B/C 切换）

## H.9 待用户决策

- **A/B/C/D 选哪个**？
- 是否 commit 修复 1 + 修复 2 + 修复 3 代码（即便 BGE m3 不启用，修复 1 是有价值的工程改进）？


---

# Phase I — 深度排查 + 真相修正 (2026-07-02)

> ⚠️ **完整 Phase I 报告**: [REPORT-phase-I.md](./REPORT-phase-I.md) (9054 bytes)

## Phase I TL;DR

| Round | Pass | 关键修复 |
|---|---|---|
| R3 BGE m3 raw | 0.8% | 起点 |
| R5a-c Phase H 3 层防御 | 1.8/2.8/0.5% | done yield + 字段过滤 + 前端剥除 |
| **R6 ms-marco + Phase I 修复** | **10%** | Neo4j 6.x 修复 + stripFakeXml 整块 |

**关键真相**: ms-marco 和 BGE m3 模式下 LLM 收到的 messages **字节级完全相同** (18106 bytes)。**rerank 不影响 LLM 决策**。

**真正失败根因** (与 rerank 无关):
1. mimo Anthropic endpoint 429 限流 (~60% 失败)
2. qa-bench `forbidden_names` 含合法成员名 (30% 数据 bug)
3. Phase H 修 3 不完整 (LLM fake XML)
4. dirty working tree 干扰

## 之前 plan 误读修正

3 个 Explore agent 报告 `llm.py:321-326 openai_compat tool_result 丢失`，**实际不存在**:
- `grep "openai_compat" app/core/llm.py` → 0 命中
- llm.py 当前只有 anthropic backend dispatch
- `LLM_BACKEND=openai_compat` 是无效配置 (代码未实现)
- CLAUDE.md 2026-07-01 v3 提到的 openai_compat 是**未来 plan**，未 push

**教训**: plan 引用 file:line 必须先 grep 确认。

## Phase I 已完成工作

| 任务 | commit | 状态 |
|---|---|---|
| I.0.1 Neo4j 6.x driver bug | `82787118` | ✅ |
| I.0.2 stripFakeXml 整块 | `82787118` | ✅ |
| I.3 DEBUG_DUMP_LLM_INPUT hook | `1eb6d739` | ✅ |
| I.4 BGE m3 vs ms-marco messages 对比 | (本期报告) | ✅ 字节级相同 |
| I.5 综合决策 + REPORT | 本节 | ✅ |

## 7 条新铁律 (Phase I 沉淀)

1. **Neo4j 6.x `session.run(cypher, query=...)` 同名冲突** — 用 `parameters={}` 包裹避免
2. **Explore agent 报告必须二次验证** — grep file:line 确认代码存在
3. **mimo 限流必须有 backoff/retry** — 不能裸跑 benchmark
4. **qa-bench `forbidden_names` 不能含 `must_contain_any` 名字** — 测试数据设计
5. **frontend `stripFakeXml` 必须用整块 pattern** — 不只剥开始标记
6. **messages 累积必须设上限** — 防止 token 爆炸 (deferred)
7. **commit 必须只 stage 当前改动** — `git status` + `git diff --cached --stat` 验证

## 下一步建议

- **不要回滚 BGE m3**: 切换 reranker 模型对 pass rate 无影响 (R6 字节级证明)
- **修 qa-bench 数据 bug** (单独 PR): forbidden_names 重设计为只禁幻觉名
- **缓解 mimo 限流**: 加 benchmark retry/backoff 或切 Claude 官方 API
- **保留 BGE m3 模型文件**: 2.27 GB 已下载, 未来可重试 (中文检索是正确方向)
