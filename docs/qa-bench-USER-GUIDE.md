# qa-bench 用户手册 (USER_GUIDE.md)

> qa-bench v3.1 决策 D7 (W6 文档交付) — W100 +35 (2026-08-03)
> 锚点范式 W100 +35 守恒
> 主指挥协调范式第 84 次派工

## 背景

T6.5 已输出 SOP（跑测/题库/入库/故障排查），本手册在此基础上扩展到 10 章，覆盖 qa-bench 全流程。本手册基于 W1-W6 已收官的实际功能：

- 535 题 (W1 700 + W2 229 手工 + 107 DB 抽真实)
- 10 个检测器（含 3 个 P0 新增: stream_interrupt / tool_error_propagated / first_token_latency）
- 7 维评分 + 一票否决
- Dashboard MVP + GitHub Actions CI smoke 200 题
- 全自动 KB 入库 5 道防线 + 7 天 rollback

---

## 目录

1. 题库结构
2. 跑测命令
3. 7 维评分
4. 检测器
5. 报告生成
6. 题库维护
7. KB 入库
8. 回归基线
9. 故障排查
10. 进阶 (扩展)

---

## 1. 题库结构

qa-bench 题库按"业务域 × 难度"二维矩阵组织：

```
qa-bench/
├── tests/qa-bench/
│   ├── data/
│   │   ├── regression_baseline_v3.0.json  # 当前基线
│   │   └── questions/
│   │       ├── A_members.json          # 成员域 (50 题)
│   │       ├── B_tasks.json            # 任务域 (60 题)
│   │       ├── C_meetings.json         # 会议域 (50 题)
│   │       ├── D_projects.json         # 项目域 (20 题)
│   │       ├── E_knowledge.json        # 知识域 (50 题)
│   │       ├── F_formulas.json         # 公式域 (15 题)
│   │       ├── G_hypotheses.json       # 假设域 (15 题)
│   │       ├── H_memory.json           # 记忆域 (20 题)
│   │       ├── M_multi_turn.json       # 多轮域 (40 题)
│   │       ├── U_chitchat.json         # 闲聊域 (15 题)
│   │       ├── X_cross.json            # 跨域 (30 题)
│   │       ├── Z_extreme.json          # 极端 (15 题)
│   │       ├── P_advanced.json         # 高级 (102 题)
│   │       └── K_cut.json              # 横切 (103 题)
│   └── runner.py
```

### 题号规则

`{domain_letter}_{difficulty}_{seq}`

例: `A_L2_005` = 成员域，难度 L2，第 5 题。

### 难度定义

- **L1** (20%): 单工具 + 简单查询
- **L2** (40%): 单工具 + 复杂条件
- **L3** (30%): 多工具协作
- **L4** (10%): 跨域综合 + 长会话

### 题目字段

```json
{
  "id": "A_L2_005",
  "domain": "members",
  "difficulty": "L2",
  "source": "manual",
  "question": "课题组的副教授有哪几位？",
  "ground_truth": ["王老师", "李老师", "张老师"],
  "expected_tools": ["search_members"],
  "tags": ["faculty", "filter"],
  "created_at": "2026-04-15",
  "updated_at": "2026-06-30"
}
```

---

## 2. 跑测命令

### 基础跑测

```bash
# 跑全量 535 题
python -m pytest tests/qa-bench/ -v --tb=short

# 跑指定域
python -m pytest tests/qa-bench/ -v -k "test_A_*"  # 成员域

# 跑指定难度
python -m pytest tests/qa-bench/ -v -k "L3 or L4"

# 跑 smoke (200 题子集, 跑测 ~1.4h)
python -m pytest tests/qa-bench/ -v -k "smoke"
```

### Runner 模式 (推荐)

```bash
# 用 tests/qa-bench/runner.py, 支持 --rounds 多轮 + verdict 聚合
python tests/qa-bench/runner.py --rounds 3 --top-k 50
```

参数：
- `--rounds N`: 跑 N 轮取众数 (默认 3, 派工 D1 实战)
- `--top-k N`: 单次跑 K 题 (默认 50)
- `--domain X`: 指定域
- `--baseline data/regression_baseline_v3.0.json`: 比较基线

### 报告输出

输出在 `data/qa_bench_report_{timestamp}.json`：

```json
{
  "version": "3.0",
  "timestamp": "2026-08-03T12:00:00Z",
  "rounds": 3,
  "verdict_consensus": "pass",
  "stable_questions_pct": 87.5,
  "per_question": [
    {
      "id": "A_L2_005",
      "verdicts": ["pass", "pass", "pass"],
      "consensus": "pass",
      "tools_used": ["search_members"],
      "latency_ms": [4200, 4150, 4280],
      "score": {"completeness": 1.0, "accuracy": 0.95}
    }
  ],
  "score_summary": {
    "completeness": 0.92,
    "accuracy": 0.88,
    "consistency": 0.875
  }
}
```

---

## 3. 7 维评分

qa-bench v3.0 起支持 7 维评分 + 一票否决：

| 维度 | 描述 | 阈值 | 否决项 |
|------|------|------|--------|
| **Completeness** | 答案是否包含所有 ground_truth 元素 | ≥ 0.8 | 是 |
| **Accuracy** | 答案准确性（错误信息扣分） | ≥ 0.7 | 是 |
| **Consistency** | 多轮稳定性 (3 轮一致比例) | ≥ 0.8 | 否 |
| **Tool Selection** | 工具选择合理性 | ≥ 0.6 | 否 |
| **Latency** | TTFT (Time To First Token) | < 4s P95 | 否 |
| **Stream Continuity** | 流式不中断 | ≥ 0.95 | 是 |
| **Error Recovery** | 工具错误是否传播到用户 | ≥ 0.9 | 是 |

### 评分规则

```
verdict = pass
    if completeness >= 0.8 AND accuracy >= 0.7
       AND stream_continuity >= 0.95 AND error_recovery >= 0.9

verdict = warn
    if 不满足 pass 但 completeness >= 0.5 AND accuracy >= 0.5

verdict = fail
    otherwise
```

---

## 4. 检测器

qa-bench 共 10 个检测器（P0/P1/P2 三档）：

### P0 检测器 (一票否决)

1. **stream_interrupt**: SSE 流在中途是否中断 (>10s 无 chunk)
2. **tool_error_propagated**: 工具错误是否直接暴露给用户（应包装）
3. **first_token_latency**: TTFT < 8s 是基线，超过 12s 标记 fail

### P1 检测器 (权重 -1)

4. **citation_accuracy**: 引用 chunk_id 是否真存在
5. **groundtruth_match**: ground_truth 是否被答案覆盖
6. **tool_call_count**: 工具调用次数合理性 (L1≤3, L2≤5, L3≤10, L4≤15)

### P2 检测器 (权重 -0.5)

7. **language_consistency**: 答案语言是否与问题一致
8. **entity_extraction**: 是否提取了关键实体
9. **json_schema_validity**: 是否符合 expected output schema
10. **polish_quality**: AI 润色是否改善了转录

---

## 5. 报告生成

### 报告位置

跑测完成后报告在 `data/qa_bench_report_{timestamp}.json`。

### Dashboard 实时可视化

```
http://localhost:8000/admin/qa-bench
```

看板上 5 张图：

1. **今日通过率** (按小时分桶)
2. **7 日稳定性** (3 轮一致比例)
3. **域通过率分布** (横轴: 域, 纵轴: pass rate)
4. **流式中断** (按日)
5. **TTFT P95** (vs 阈值 4s)

### 导出 markdown

```bash
python tests/qa-bench/export_report.py data/qa_bench_report_2026-08-03.json > qa_bench_report.md
```

---

## 6. 题库维护

### 加新题

```bash
# 模板化 (推荐)
python tests/qa-bench/gen_question.py --domain E --difficulty L2 --count 10

# 手填
vim tests/qa-bench/data/questions/E_knowledge.json
```

### DB 抽真实题 (W2 模式)

```bash
python tests/qa-bench/db_extractor.py --from meetings --count 100 --output data/questions/M_auto.json
```

源：`meeting_transcripts` / `project_milestones` / `knowledge_references` / `formula_variables`

### 抽样人工复核

```bash
# 抽 10% 人工复读
python tests/qa-bench/sample_review.py --pct 10 --output data/review_queue.json
```

### Schema 校验

```bash
python tests/qa-bench/validate_schema.py tests/qa-bench/data/questions/ -r
```

---

## 7. KB 入库

qa-bench 通过 5 道防线确保只入"对答案"：

1. **Verdict 必须 pass** (≥ 0.8 completeness & accuracy)
2. **稳定性 ≥ 80%** (3 轮一致)
3. **来源过滤** (拒绝 ground_truth 引用)
4. **去重** (pgvector cosine ≥ 0.92 视为重复)
5. **健康监控** (入库 7 天后回访, 命中率 < 50% 触发 rollback)

### 灰度参数

```bash
# W86 mini-13 C: 灰度开关 (env)
export AUTO_KB_INTAKE_ENABLED=false  # 默认 dry-run
export KB_GRAY_SCALE_PERCENT=5       # 5% 抽样写入
```

### 手动入库

```python
from app.services.auto_intake import save_to_kb

save_to_kb(
    question="微纳米气泡的稳态粒径范围？",
    answer="通常为 50-500 nm ...",
    source="manual",
    confidence=0.95,
)
```

### 回滚

```bash
# 7 天内回滚某个入库
python tests/qa-bench/rollback_intake.py --intake-id 12345 --reason "wrong_answer"
```

---

## 8. 回归基线

### 基线文件

`tests/qa-bench/data/regression_baseline_v3.0.json`

```json
{
  "version": "3.0",
  "pass_rate_min": 0.70,
  "stable_questions_pct_min": 0.70,
  "rounds": 3,
  "ttft_p95_max_ms": 4000,
  "stream_interrupt_max_pct": 0.05,
  "consensus_method": "majority",
  "created_at": "2026-06-30",
  "stable_questions_count": 350
}
```

### 更新基线

⚠️ **不擅自更新基线**。需要主拍决策：
1. 跑 200 题 smoke 3 次取众数
2. 看 4 个关键指标 (pass_rate / stable_pct / ttft / interrupt)
3. 主拍拍板：调整阈值 vs 修代码

### CI 阻断

`.github/workflows/qa-bench-smoke.yml`:
- `pass_rate < 0.70` → 阻断
- `stable_questions_pct < 0.70` → 阻断
- `ttft_p95 > 4000ms` → warn 但不阻断

---

## 9. 故障排查

### 故障 1: 跑测 0% pass

**症状**: 全量或大域 pass_rate = 0
**根因**:
- Anthropic API 429 (限流)
- Embedding 模型未加载
- 数据库连接断开

**修复**:
```bash
# 1. 检查 LLM 后端
echo $LLM_BACKEND  # anthropic / openai_compat / ollama
# 2. 测试 embedding
python -c "from app.services.embedding_service import generate_embedding; print(generate_embedding('test')[:5])"
# 3. 测试数据库
psql -U postgres -d microbubble -c "SELECT 1"
```

### 故障 2: 跑测 latency > 30s

**症状**: 单题耗时严重超标
**根因**:
- 无 retrieval cache 命中 (qa-bench 启用 5min TTL 见 D3)
- TTFT > 12s

**修复**:
- 启用 D3 retrieval cache: `LLM_QA_BENCH_ROUNDS=3` + `LLM_TEMPERATURE_QA_BENCH=0.0` 已自动开启
- 查 cfg: `echo $LLM_QA_BENCH_ROUNDS`

### 故障 3: CI smoke 红

**症状**: PR push 后 CI 阻断
**根因**:
- 新代码引入 pass_rate 回归
- 阈值波动

**修复**:
```bash
# 拉 CI 日志
gh run view {RUN_ID} --log
# 重跑
gh workflow run qa-bench-smoke.yml
```

### 故障 4: KB 入库污染

**症状**: 7 天回访发现某条 KB 答案错
**修复**:
```bash
# 单条 rollback
python tests/qa-bench/rollback_intake.py --intake-id 12345

# 批量 rollback (按 source)
python tests/qa-bench/rollback_intake.py --source w6_auto --reason "mass_wrong"
```

### 故障 5: 流式断流

**症状**: SSE chunk 间隔 > 10s
**根因**:
- LLM 端 5xx
- Streaming JSON 解析失败
- 浏览器缓冲

**修复**:
- 查 `agent_traces.stream_interrupt_count`
- 升级 LLM backend (anthropic → openai_compat/mimo 抗 429)

---

## 10. 进阶 (扩展)

### 自定义检测器

```python
from app.qa_bench.detectors import BaseDetector, register

@register("my_detector")
class MyDetector(BaseDetector):
    def evaluate(self, answer: str, ground_truth: List[str]) -> float:
        # 返回 0.0 - 1.0
        return 0.0
```

### 自定义评分维度

```python
from app.qa_bench.scoring import ScoreDimension, register

@register("my_dimension")
class MyDimension(ScoreDimension):
    weight = 0.1
    def score(self, answer: str, q: dict, trace: dict) -> float:
        return 0.85
```

### 题库模板生成

```bash
# 扩 1000+ 题
python tests/qa-bench/gen780.py --count 1000 --template base
```

### 自定义 ground_truth 来源

```python
# DB 真值
from app.services.knowledge_service import search_knowledge
gt = [k.title for k in await search_knowledge(q, top_k=3)]
```

### 报告 CI 集成

`.github/workflows/qa-bench-report.yml`:
```yaml
- name: Run qa-bench
  run: python tests/qa-bench/runner.py --rounds 3
- name: Upload report
  uses: actions/upload-artifact@v4
  with:
    name: qa-bench-report
    path: data/qa_bench_report_*.json
```

---

## 实际新人 1-2 天上手建议

| 时长 | 推荐任务 | 产出 |
|------|----------|------|
| Day 1 morning | 跑 smoke 200 题 | 看 1 份报告 |
| Day 1 afternoon | 读 7 维评分 + 10 检测器 | 写 1 篇笔记 |
| Day 1 evening | 修 1 个检测器 (smallest patch) | 1 PR |
| Day 2 morning | 改 1 个题 + 跑测验证 | 新 score > 老 |
| Day 2 afternoon | 看 Dashboard KPI 5 图 | 1 篇分析报告 |

---

**手册版本**: v3.1 D7
**派工日期**: 2026-08-03 (W100 +35)
**适用 qa-bench 版本**: v3.1
**维护**: 主拍决策变更需更新本文档 (派工 v11 §13.3 假设禁令: 不擅自改 7 维评分)
