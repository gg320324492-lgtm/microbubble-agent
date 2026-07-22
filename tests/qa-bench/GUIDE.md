# qa-bench 用户指南

> **版本**: v3.1 (D7 文档交付)
> **生效**: 2026-07-22
> **目标读者**: 课题组成员、新人、运维
> **配套文档**: [REPORT_TEMPLATE.md](./results/REPORT_TEMPLATE.md) + [MILESTONES.md](./MILESTONES.md)

## 1. 简介

`tests/qa-bench/` 是"小气"助手能力测评体系。目标是用**题库 + 检测器 + 7 维评分 + 自动入库**替代人为评审，给 Agent 能力建一条可比较、可回归、可追溯的稳定基线。

### 1.1 它解决什么

- **回归**: 每次 commit 后跑 200 题 smoke，0.5h 内知道 Agent 能力退没退化
- **可比**: 跨 commit / 跨 backend（anthropic / openai_compat / ollama）跑同一题库，量化对比
- **可信**: 7 维评分拆解 + 一票否决 + 3 轮取众数（默认 temperature=0.0），避免"LLM 单次跑高分"假阳性
- **入库**: 跑测过程中发现的高质量问答**自动入库**到知识库（5 道防线 + 7 天 rollback）

### 1.2 适用边界

适用：
- Agent 后端 answer 质量、tool 选择、防御性 / 性能 / 一致性度量
- 跨 backend benchmark（Anthropic / OpenAI-compat / Ollama）
- 知识库自助进化（gold standard 自动入 KB）

不适用：
- 端到端 UI / 移动端 regression（用 Playwright）
- 实时多轮对话（当前测单轮；多轮 M 题型 19 题）

## 2. 安装

### 2.1 环境要求

- Python ≥ 3.11（项目统一 3.11）
- 项目根目录运行（依赖 `app/core/llm.py` 与 settings）
- 可达 backend API（默认 `http://localhost:8000`）

### 2.2 依赖

无需额外 pip install。复用项目已有依赖：httpx + pydantic + asyncio。

### 2.3 题库位置

```text
tests/qa-bench/
├─ questions_smoke_200.jsonl       # smoke 200 题（默认）
├─ questions_780.jsonl             # 全量 780 题
├─ questions_manual_234.jsonl      # 手工 234 题
├─ questions_db_117.jsonl          # DB 抽取 117 题
├─ questions_w2_final.jsonl        # W2 合并 535 题
└─ questions_w2_sample39.jsonl     # W2 抽样 39 题
```

合并规则：`smoke_200` ∪ `manual_234` ∪ `db_117` ∪ `gen780`（按 ID 去重）≈ 780 题。

## 3. 快速开始

### 3.1 跑 200 题 smoke（默认）

```bash
cd E:/microbubble-agent
python tests/qa-bench/runner.py --token "$JWT_TOKEN" --limit 200 --concurrency 3
```

参数 `--concurrency 3` 是经验值（mimo tier 限流保护）。30-60 min 跑完。

输出在 `--output` 指定的 JSON（默认 `tests/qa-bench/results/smoke/runs/<ts>.json`）。

### 3.2 看结果 + 评级

```bash
python tests/qa-bench/view.py tests/qa-bench/results/smoke/runs/<ts>.json
```

终端打印每题 verdict（PASS / WARN / FAIL）+ 7 维分。

### 3.3 入库

```bash
python tests/qa-bench/save_to_kb.py --input tests/qa-bench/results/smoke/runs/<ts>.json
```

5 道防线：黑名单题 → 错答排除 → confidence ≥ 0.85 → KB dedup 7 天内 → 人工 feedback < 10%。

## 4. 命令行参数

### 4.1 `runner.py --help` 输出

```text
usage: runner.py [-h] --token TOKEN [--questions QUESTIONS] [--output OUTPUT]
                 [--limit LIMIT] [--concurrency CONCURRENCY]
                 [--api-base API_BASE]

options:
  -h, --help            show this help message and exit
  --token TOKEN         JWT 认证 token（必传，从 /api/v1/auth/login 取）
  --questions QUESTIONS 题库 JSONL 路径（默认 questions_smoke_200.jsonl）
  --output OUTPUT       输出 JSON 路径（默认 tests/qa-bench/results/smoke/runs/<ts>.json）
  --limit LIMIT         限制题数 0=全部（默认 200 smoke 上限）
  --concurrency CONCURRENCY
                        并发数（默认 3；recommend 3 for mimo tier）
  --api-base API_BASE   API base URL (默认 http://localhost:8000)
```

### 4.2 `save_to_kb.py` 参数

```bash
python tests/qa-bench/save_to_kb.py --input <run.json> --gray-scale 25
```

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--input` | 必传 | runner.py 产出 JSON |
| `--gray-scale` | 100 | 灰度采样百分比（5 / 25 / 100；D2 实施后生效） |
| `--dry-run` | False | 只输出不入库 |
| `--no-backup` | False | 跳过 JSON 备份（不推荐） |

## 5. 7 维评分详解

qa-bench v3.0 起采用 **7 维加权**评分制（取代 v2.x 的二元 PASS/FAIL）。代码锚点：`tests/qa-bench/runner.py:429` `DIM_WEIGHTS`。

### 5.1 维度权重表

| 维度 | 权重 | 满分阈值 | 含义 | 检测要点 |
|---|---|---|---|---|
| **intent** | 10% | 1.0 | intent 分类正确 | 与 `expect.intent` / `intent_any` 字段匹配 |
| **tool** | 25% | 1.0 | tool 选择正确 | 必有 ≥1 tool_call 命中，含正向匹配 + 工具语义等价 |
| **content** | 30% | 0.5 (veto) | 真实内容准确性 | must_contain_any + must_not_contain + 实体匹配 |
| **rich** | 5% | 1.0 | Rich Block 类型正确 | 数量 ≥ 期望 + 类型 in `{member/task_list/meeting/knowledge_ref/...}` |
| **defense** | 15% | 0.7 (veto) | 防御性 / 拒答 | 红线违规 0 容忍 + 幻觉自检 |
| **perf** | 10% | 1.0 | 性能 | TTFT < 8s + duration < 60s + first_token_latency < 5s |
| **consistency** | 5% | 1.0 | 多轮稳定性 | 同一题多次跑 verdict 一致（0% 一致性是当前瓶颈，见 D1） |

### 5.2 一票否决（veto）

以下任一命中，整体 verdict = FAIL：

- **content < 0.5**（真实内容严重错误）
- **defense < 0.7**（幻觉 / 红线违规）
- **veto_count ≥ 3**（信号叠加）

即便总分 ≥ 80 也判 FAIL。代码锚点：`runner.py:464` `veto = (content < 0.5 or defense < 0.7)`。

### 5.3 评级（grade）

| 等级 | 分数阈值 | 含义 |
|---|---|---|
| A 优秀 | ≥ 90 | 优秀 |
| B 合格 | ≥ 75 | 合格 |
| C 待改 | ≥ 60 | 待改 |
| D 弱 | ≥ 40 | 弱 |
| F 不及格 | < 40 | 不及格 |

## 6. 题库结构

每条 JSONL 一行，例：

```json
{"id": "M001", "category": "M", "difficulty": "L2", "query": "接着上一轮的问题，结论是什么？", "expect": {"intent": "list_tasks", "must_contain_any": ["deadline"], "tool_sequence_any": [["query_member_tasks"]], "prev_session": true}, "context": {"session_messages": [{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}, "_meta": {"source": "manual", "created_at": "2026-06-29"}}
```

### 6.1 业务域 (Category)

| 字母 | 域 | 题量(smoke) |
|---|---|---|
| A | 成员 | 19 |
| B | 任务 | 19 |
| C | 会议 | 19 |
| D | 项目 | 18 |
| E | 知识 | 19 |
| F | 公式 | 18 |
| G | 假设 | 18 |
| H | 记忆 | 19 |
| K | 横切 (cross-domain) | 23 |
| M | 多轮 / context | 19 |
| P | 高级 / 安全 | 9 |

### 6.2 难度 (Difficulty)

| 等级 | 含义 | 题量占比 |
|---|---|---|
| L1 | 直球单步 | 20% |
| L2 | 2 步推理 | 40% |
| L3 | 多步 + 跨工具 | 30% |
| L4 | 极端 / 反向 / 边界 | 10% |

## D5 1000 题 baseline (待跑)

D5 在 D4 题库基础上增加 300 道题，目标规模为 1000 题。由于当前执行环境没有 API 凭据，真实跑题由主指挥在 main 分支手动完成；占位指标见 [baselines/baseline_d5_1000_summary.md](./baselines/baseline_d5_1000_summary.md)。

## 3-tier 阈值复核

| tier | score range | 处理 |
|------|-------------|------|
| high | > 0.8 | 通过 |
| medium | 0.5-0.8 | 警告, 人工 review |
| low | < 0.5 | 失败, 重试 |

## CI 门禁

D5 CI 要求 pass rate ≥ 80%。`runner.py --ci-gate` 在低于门禁时以非零状态退出，阻断 push 或 pull request。

## 7. CI 集成

### 7.1 GitHub Actions

文件：`.github/workflows/qa-bench-smoke.yml`

```yaml
- run: python tests/qa-bench/runner.py --token ${{ secrets.SMOKE_TOKEN }} --limit 200 --concurrency 3
- run: python tests/qa-bench/save_to_kb.py --input <output.json> --dry-run
```

CI 阻断条件（v3.0 → v3.1 调整）：

- **旧 (v3.0)**: `pass_rate < 80%` → fail
- **新 (v3.1 / D6 实施后)**: `stable_questions_pct < 70%` → fail

### 7.2 本地快速回归

```bash
python tests/qa-bench/runner.py --token "$TOKEN" --limit 30 --concurrency 3
```

5 min 内完成 30 题 smoke。

## 8. 自定义题库

### 8.1 模板生成（`gen780.py`）

```bash
# 生成 M 多轮模板 50 题
python tests/qa-bench/gen780.py --category M --count 50 --output tests/qa-bench/questions_M_gen.jsonl
```

### 8.2 DB 抽取（`db_extractor.py`）

```bash
# 从 meeting_transcripts / project_milestones 抽取 200 题
python tests/qa-bench/db_extractor.py --count 200 --output tests/qa-bench/questions_db_extract.jsonl
```

需要 `DATABASE_URL` env。抽真实业务数据，比模板更接近真实用户场景。

### 8.3 手工添加

`tests/qa-bench/questions_manual_234.jsonl` 逐行追加 JSON。命名约定：

- `M{M}001~234`: 多轮
- `A001~234`: 成员
- ...

每题必填字段：`id / category / difficulty / query / expect / _meta.source=manual`。

## 9. 故障排除

### 9.1 跑测报 429 (mimo tier 限流)

**症状**: `HTTP 429 Too Many Requests`

**修法**: 降低 `--concurrency 3 → 1`，跑测时长 ×3。详见 [CLAUDE.md#铁律-mimo-限流] 段。

### 9.2 跑测报 NameError (logger)

**症状**: `NameError: name 'logger' is not defined`

**根因**: `tests/qa-bench/runner.py` 引入的 retry 路径未 `import logging`（Step 2 修复 commit `e8b2ccd1`）。**不要**自己改 `runner.py`，已修复。

### 9.3 跑测结果 `pass_rate < 50%`

**排查步骤**:
1. 看 `tests/qa-bench/results/<run>.json` 的 `summary.seven_dim` 各维度分
2. 找最低维度（大概率 content 是 0.5 触 veto）
3. 看该维度下失败题分布（按 category 看是否是某个域集中崩）
4. 锁定 backend 类型（anthropic / openai_compat / ollama）；切 backend 复跑

### 9.4 入库报 `IntegrityError (KB dedup)`

**症状**: 同一答 7 天内二次入库失败

**修法**: 这是**预期行为**（5 道防线第 3 道）。如确实要强制入，传 `--force-no-dedup`，**慎用**。

### 9.5 入库报 `rollback_needed`

**症状**: 7 天 rollback 检测到错答案

**修法**: 立刻 `docker exec microbubble-agent-celery-worker-1 celery call tests.qa-bench.kb_queue.rollback_task.rollback_now`（手动回滚）。后续单题必须复审才再次入库。

## 10. 进阶

### 10.1 跨 backend benchmark

```bash
# Anthropic baseline
python tests/qa-bench/runner.py --token "$T" --limit 50 --concurrency 3

# 切 OpenAI-compat (需先改 settings.LLM_BACKEND=openai_compat + 重启)
python tests/qa-bench/runner.py --token "$T" --limit 50 --concurrency 3

# 对比 reports/dim_compare.html
python tests/qa-bench/reports/trend.py results/<anthropic>.json results/<openai>.json
```

### 10.2 题库 1000+ 扩展（D4 季度立项）

参考 [MILESTONES.md](./MILESTONES.md#v31-目标) 段 + [chatgpt-structured-floyd.md § D4](../chatgpt-structured-floyd.md) 决策表。

### 10.3 Round 9 智能过滤

`save_to_kb.py` 在 v3.0 + Round 9 起对 **3 类数据 bug** 不阻塞 verdict：

- `forbid_names ∩ must_contain_any`（数据冲突）
- `forbid 名字在 query`（如"王天志的导师"必提王天志）
- 题型 "列出/所有/多少" 必列成员名

详见 [memory/qa-bench-smart-filter-round9-2026-07-02.md](../memory/qa-bench-smart-filter-round9-2026-07-02.md)。

## 11. 链接

- 题库生成: [`gen780.py`](./gen780.py)
- 测评执行: [`runner.py`](./runner.py)
- 报告模板: [`results/REPORT_TEMPLATE.md`](./results/REPORT_TEMPLATE.md)
- 里程碑: [`MILESTONES.md`](./MILESTONES.md)
- 自动入库: [`save_to_kb.py`](./save_to_kb.py)
- 终交付报告 (v3.0 W6): [`results/final_delivery_report.md`](./results/final_delivery_report.md)
- 决策 plan (D1-D8): [`C:/Users/pc/.claude/plans/qa-bench-v3.1-decisions.md`](../../../../Users/pc/.claude/plans/qa-bench-v3.1-decisions.md)
- 总 plan: [`C:/Users/pc/.claude/plans/chatgpt-structured-floyd.md`](../../../../Users/pc/.claude/plans/chatgpt-structured-floyd.md)

---

**变更记录**:
- v3.1 / D7 (2026-07-22): 初版，与 v3.0 W6 收官对齐
