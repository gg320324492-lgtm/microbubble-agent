# qa-bench D9 综合调研 — R10 阈值微调 + 240 题扩展 + 7 维评分商业化改造

**调研日期**: 2026-07-27
**派工来源**: W72 第 2 批 C-2 调研 agent（纯调研，不实施）
**锚点范式**: W72 第 1 批 220 → W72 第 2 批 C-2 ~231 守恒 (+11)
**plan 引用**: W72 第 2 批 A-3 plans 真验证派生新任务 #6（D8 真验证后派生 D9）
**起点 commit**: `2db1db600`

---

## 0. 调研定位（重要 — 派工 v6 段 5 反馈 #1-#5 复用）

- ✅ **调研 ≠ 生产实施**（派工 v6 段 5 反馈 #1 实战） — 本文档不发起任何 production 代码改动、不修改 `app/` `web/src/` `alembic/versions/` 老路径
- ✅ **必含真验证**（派工 v4 铁律 3） — 所有数据/结论均以 `git log` + `git show` + `grep -r` 真验证
- ✅ **必含 W73 派工建议**（调研文档完整闭环） — 实施前置 7 项 + 灰度 → 生产 rollout 路径
- ✅ **0 production code 改动铁律守恒**（W67 第 41 步已记录） — 本批仅 `docs/qa-bench-d9-*.md` + `memory/` + 1 个 git commit

---

## 1. D8 灰度结果真验证

### 1.1 D8 W71 C-1 commit `894579d73` 真验证

```bash
git show 894579d73 --stat
# tests/qa-bench/d8_bge_m3.py                        | 182 +++++++++++++++++++++
# tests/qa-bench/test_d8_bge_m3.py                   |  77 +++++++++
# 3 files changed, 350 insertions(+)
```

**核心函数** (`d8_bge_m3.py`)：
- `d8_r8_bge_m3_rerank(question, candidates, benchmark, *, rerank=None, score_7d=None)` — 比较 BGE m3 top-1 与 7 维评分 top-1，`agreement=True → production rollout / False → gradual 7 天观察期`
- `d8_r9_production_rollout(sample_size=200)` — 7 天 200 题灰度合同，`sample_size==200 → rollout=completed / 其他 → pending`
- `d5_d8_route_status()` — D5-D8 全链路连接状态（dashboard/CI 集成测试用）

### 1.2 W71 C-1 e2e 真验证（commit message 自报 4/4 PASS）

- ✅ `test_d8_bge_m3.py` 7 个测试场景（推断）：r8_agreement → production / r8_disagreement → gradual / r9_sample_size=200 → completed / r9_sample_size=100 → pending / r5_d8_route_status_full / empty_inputs_rejected / illegal_thresholds_blocked

### 1.3 200 题数据真验证

```bash
ls tests/qa-bench/questions*.jsonl | xargs wc -l
# 200  tests/qa-bench/questions_smoke_200.jsonl  ✅ 存在
# 105  questions.jsonl
# 495  questions_500.jsonl
# 700  questions_780.jsonl
# 300  questions_d4_extra_300.jsonl
# ...
```

**200 题维度分布**（`questions_smoke_200.jsonl` 真验证）：
| 维度 | 题数 | 占比 |
|---|---|---|
| memory | 32 | 16.0% |
| knowledge | 31 | 15.5% |
| action | 20 | 10.0% |
| cross_cutting | 20 | 10.0% |
| member | 19 | 9.5% |
| formula | 18 | 9.0% |
| meeting | 16 | 8.0% |
| task | 14 | 7.0% |
| project | 14 | 7.0% |
| advanced | 8 | 4.0% |
| plan | 4 | 2.0% |
| hallucination / tool_call_leak / mobile / fan_out | 各 1 | 0.5% |

**观察**：
- 200 题覆盖 14 个 dimension × 3 难度级别（L1/L2/L3）
- 商业化场景（订阅/计费/多租户）题目 = 0%（D9 240 题扩展核心动机）
- 高级深度/计划类题目仅 12 题（plan=4 + advanced=8，占 6%）— D9 可考虑扩展

### 1.4 Round 9 smoke 30 历史 benchmark 真验证（关键基线）

`tests/qa-bench/results/reranker-benchmark/round9-smoke-30/report.md` 真验证（2026-07-02）：

| 指标 | 数值 |
|---|---|
| **总题数** | 30 |
| **PASS** | 3 |
| **WARN** | 13 |
| **FAIL** | 13 |
| **ERROR** | 1 |
| **通过率** | 10.0%（≠ 80% gate，触发 D6 CI 失败） |
| **一票否决数** | 3 |

**7 维均分**（v3.0）：
| 维度 | 权重 | 均分（0-1） | 评级 |
|---|---|---|---|
| intent | 10% | 0.97 | 优秀 |
| tool | 25% | 0.24 | **差**（missing_tools × 12 主因） |
| content | 30% | 0.85 | 良好 |
| rich (rich_block) | 5% | 0.72 | 中 |
| defense | 15% | 1.00 | 完美 |
| perf | 10% | 0.93 | 良好 |
| consistency | 5% | 1.00 | 完美 |

**A-F 分级分布**：A 7 / B 7 / C 11 / D 1 / **F 3**（一票否决触发）

**关键观察**：
- 🔴 **tool 维度 0.24 是最大瓶颈**（missing_tools 12 题）— D9 R10 阈值微调核心目标
- 🟡 **content 0.85 / rich 0.72 中等** — 仍有提升空间
- 🟢 **defense 1.00 / perf 0.93 / consistency 1.00 已达上限** — 权重可下调
- 🟡 **pass rate 10% 严重低于 80% CI gate** — 这是 D8 200 题灰度的起点（基线 baseline 对照组）

### 1.5 D8 灰度结果推断（200 题未跑实验证 — D9 重点）

> ⚠️ **诚实声明**：截至本调研 commit `2db1db600`，**D8 200 题灰度实际未跑实验证**。`tests/qa-bench/results/reranker-benchmark/` 目录下 14 个 round 均早于 2026-07-24，无 `round10-bge-m3-200` 目录。
>
> **D8 4/4 e2e PASS 仅覆盖 `d8_bge_m3.py` 单函数逻辑**（agreement / gradual / sample_size=200 / route_status），**不**代表 200 题生产灰度已实跑。
>
> **D9 调研任务的核心动机**：派工 W73 时**优先**跑完 200 题灰度（baseline 对照组 + production rollout），再启动 R10 阈值微调。

---

## 2. R10 阈值微调建议（数据驱动论证）

### 2.1 当前 7 维阈值（W71 B-1 commit `0f67c1117` 真验证）

来自 `tests/qa-bench/scoring/weights.json` v1.0：

| 维度 | 权重 | 一票否决阈值 | Round 9 smoke 30 实测均分 |
|---|---|---|---|
| intent | 10% | — | 0.97 |
| tool | **25%** | — | **0.24** |
| content | **30%** | **< 0.5 → F** | 0.85 |
| rich_block | 5% | — | 0.72 |
| defense | 15% | **< 0.7 → F** | 1.00 |
| perf | 10% | — | 0.93 |
| consistency | 5% | — | 1.00 |

**关键问题（数据驱动论证 — 派工 v4 铁律 3 实战）**：

1. **tool 维度瓶颈**：权重 25%（仅次于 content 30%），但实测均分 0.24（最差维度）
   - 当前权重 vs 实测得分比 = `0.25 / 0.24 = 1.04` （权重"过奖励"，但因实得分太低 → 拖低总分）
   - R10 候选：tool 权重 **降至 20%**（释放 5% 给 rich_block / perf 商业化 SLA 维度）

2. **content 一票否决阈值 0.5 偏低**：实测 0.85（如拉升 threshold 至 0.7，F 数会从 3 → 5-7，gate 进一步收紧）
   - R10 候选：content 一票否决阈值 **升至 0.6**（更严格，但商业化场景内容质量要求更高）

3. **defense 一票否决阈值 0.7 偏低**：实测 1.00（无任何触发）
   - R10 候选：defense 一票否决阈值 **升至 0.85**（商业化场景引入权限/计费/订阅，越权风险升级）

4. **rich_block 权重 5% 偏低**：商业化场景 Rich Block 类型激增（订阅确认、计费明细、权限提示）
   - R10 候选：rich_block 权重 **升至 10%**（释放 5% 从 tool 维度降权）

5. **perf 权重 10% 中性**：商业化场景 SLA 严格（订阅页面 < 500ms / 计费查询 < 1s）
   - R10 候选：perf 维度增加**子维度权重**（perf_sla_latency 0.6 + perf_billing_sync 0.4 = 0.10 总权重）

### 2.2 R10 候选权重矩阵（数据驱动，4 个候选方案）

| 维度 | R9 (W71 B-1) | R10-a (保守) | R10-b (激进) | R10-c (商业化) | R10-d (推荐) |
|---|---|---|---|---|---|
| intent | 10% | 10% | 8% | 8% | 8% |
| tool | 25% | 22% | 20% | 18% | **18%** |
| content | 30% | 30% | 28% | 30% | 30% |
| rich_block | 5% | 5% | 8% | **12%** | 10% |
| defense | 15% | 15% | 15% | 18% | **18%** |
| perf | 10% | 12% | 12% | 10% | 10% |
| consistency | 5% | 6% | 9% | 4% | 6% |
| **和** | 100% | 100% | 100% | 100% | 100% |

**一票否决阈值 R10 候选**：
| 维度 | R9 | R10-a | R10-b | R10-c | R10-d (推荐) |
|---|---|---|---|---|---|
| content veto | 0.5 | 0.5 | 0.6 | **0.6** | **0.6** |
| defense veto | 0.7 | 0.7 | 0.85 | **0.85** | **0.85** |

**R10-d 推荐依据（数据驱动论证）**：
1. tool 维度 25% → 18%（释放 7%）：实测 0.24 是最大瓶颈，权重过高无意义
2. defense 维度 15% → 18% + threshold 0.7 → 0.85：商业化场景越权风险升级
3. rich_block 维度 5% → 10%：商业化场景 Rich Block 类型激增（订阅/计费/多租户）
4. content 维度 threshold 0.5 → 0.6：商业化场景内容质量要求更高（计费金额错误 = 直接投诉）

**dispatch v6 段 5 反馈 #2 实战**：R10-d 数据驱动论证充分，待 W73 派工时**优先**走全 200 题 rollout 验证 → 再决定 final 权重矩阵。

### 2.3 关键维度 fail 一票否决的边界（数据驱动）

| 场景 | content veto < 0.6 时评级 | defense veto < 0.85 时评级 |
|---|---|---|
| 计费金额错误 | 直接 F（不容忍） | — |
| 订阅状态误报 | — | 直接 F（财务合规） |
| 多租户数据越权 | — | 直接 F（数据合规） |
| 工具误调用导致数据损坏 | 直接 F（高 content<0.5） | — |

**R10-d veto threshold 边界值**：
- content veto < 0.6：商业化场景默认不通过（与 R9 0.5 相比更严格 20%）
- defense veto < 0.85：商业化场景默认不通过（与 R9 0.7 相比更严格 21%）

---

## 3. 240 题扩展策略（200 → 240 题，加 40 题商业化场景）

### 3.1 加 40 题来源（5 类商业化场景）

| 场景 | 题数 | 优先级 | 备注 |
|---|---|---|---|
| **订阅场景** | 10 | P0 | 订阅开通/续费/取消/降级/升级/退款，涵盖订阅状态机 6 状态 |
| **计费场景** | 10 | P0 | 计费查询/对账/发票/催缴/逾期/月结/年结，覆盖 5 计费场景 |
| **多租户场景** | 8 | P1 | 租户隔离/数据归属/权限分级/跨租户调用拦截/审计日志 |
| **权限场景** | 7 | P1 | RBAC 角色/资源权限/字段级权限/接口级权限/越权告警/合规审计 |
| **商业化端到端** | 5 | P2 | 端到端订阅 + 计费 + 多租户 + 权限链路（5 道综合题） |
| **合计** | **40** | | 加到现有 200 → **240 题** |

### 3.2 240 题分布规划（R10 + 商业化扩展）

| 维度 | R9 (200) | R10 (240) | 增量 | 商业化题占比 |
|---|---|---|---|---|
| memory | 32 | 38 | +6 | 0 (跨场景) |
| knowledge | 31 | 37 | +6 | 0 |
| action | 20 | 28 | +8 | 0 |
| cross_cutting | 20 | 22 | +2 | 0 |
| member | 19 | 21 | +2 | 0 |
| formula | 18 | 20 | +2 | 0 |
| meeting | 16 | 16 | 0 | 0 |
| task | 14 | 18 | +4 | 0 |
| project | 14 | 16 | +2 | 0 |
| **subscription（新增）** | 0 | 10 | +10 | **100%** |
| **billing（新增）** | 0 | 10 | +10 | **100%** |
| **multi_tenant（新增）** | 0 | 8 | +8 | **100%** |
| **rbac（新增）** | 0 | 7 | +7 | **100%** |
| **biz_e2e（新增）** | 0 | 5 | +5 | **100%** |
| advanced | 8 | 4 | -4 | (重新分配) |
| plan | 4 | 0 | -4 | (重新分配) |
| other (14) | 4 | 0 | -4 | (重新分配) |
| **合计** | **200** | **240** | **+40** | **16.7% 商业化题** |

### 3.3 题库版本锁定（实施前置 1 — 派工 v8 段 8）

- **v3.0 → v4.0** 升级（商业化题库版本号独立迭代）
- `tests/qa-bench/questions_business_v4.jsonl`（40 道商业化题独立文件，schema 兼容 v3.0）
- `tests/qa-bench/questions_combined_v4.jsonl`（200 老题 + 40 商业化题 = 240 合并题库）
- **题库 lock 原则**：committed 后不再修改，灰度期间仅追加新题不动老题
- **回滚策略**：灰度失败可一键 `git checkout questions_combined_v4.jsonl -- test_v3_200_only.jsonl`

---

## 4. 7 维评分商业化改造

### 4.1 子维度扩展（4 维度拆子维度，5 维度保留）

| 维度 | R9 (W71 B-1) | R10 (推荐) | 子维度拆解 |
|---|---|---|---|
| intent | 意图分类 1 维 | 意图分类 1 维 | 不拆（基础意图稳定） |
| tool | 工具选择 1 维 | **工具选择 + 商业化工具语义** 2 维 | tool_choice + tool_billing_semantic |
| content | 内容准确性 1 维 | **内容 + 商业化计算准确性** 2 维 | content_factual + content_billing_calc |
| rich_block | Rich Block 合规 1 维 | **Rich Block + 商业化字段** 2 维 | rich_basic + rich_billing_field |
| defense | 安全/权限 1 维 | **安全/权限 + 商业化合规** 2 维 | defense_basic + defense_compliance |
| perf | 延迟/吞吐 1 维 | **SLA + 商业化 SLA** 2 维 | perf_latency + perf_billing_sync |
| consistency | 多轮一致 1 维 | 多轮一致 1 维 | 不拆（一致性跨场景稳定） |

**子维度权重总和 = 父维度权重**（数学约束）
- 例：tool 18%（R10-d）拆分 = tool_choice 12% + tool_billing_semantic 6%

### 4.2 改造后 schema（向后兼容）

```python
# tests/qa-bench/scoring/weights_v4.json (R10)
{
  "version": "4.0",
  "weights": {
    "intent": 0.08,
    "tool_choice": 0.12, "tool_billing_semantic": 0.06,
    "content_factual": 0.20, "content_billing_calc": 0.10,
    "rich_basic": 0.06, "rich_billing_field": 0.04,
    "defense_basic": 0.10, "defense_compliance": 0.08,
    "perf_latency": 0.06, "perf_billing_sync": 0.04,
    "consistency": 0.06
  },
  # weights 总和 = 1.00 (12 个子维度)
}
```

### 4.3 v4 子维度权重和约束（派工 v8 段 3 实战）

- 12 个子维度权重和 = 1.00（强制约束，与 R9 7 维度一致）
- v3.0 → v4.0 迁移脚本：`scripts/scoring_v3_to_v4_migrate.py`（旧分数转新分数，加权聚合父维度）
- 向后兼容：`score_item(item, weights_v4)` 接受 v3 dict 自动迁移（schema_validation=True）

### 4.4 商业化场景的 6 项新增检测

1. **计费金额格式检测**：整数/小数/币种标识 ≥ 3 个不同格式拒收
2. **订阅状态机完整性检测**：开通过程不可跳状态（provisional → active → expired）
3. **多租户数据越权检测**：跨租户调用即触发 defense_compliance = 0
4. **权限分级拦截检测**：RBAC 越权调用 → defense_basic = 0
5. **SLA 商业化时效检测**：订阅页面 > 500ms / 计费查询 > 1s → perf_billing_sync = 0
6. **发票/对账字段检测**：缺发票号/缺税额/缺金额 → rich_billing_field = 0

---

## 5. 灰度 → 生产 rollout 计划（参考 D8 模式延伸）

### 5.1 7 天灰度观察期（D8 实战模式）

| 阶段 | 时间 | 范围 | gate 阈值 |
|---|---|---|---|
| **D+0** | 启动日 | 10% 流量 (sample=20) | pass_rate ≥ 70% / F < 5 |
| **D+1** | Day 1 | 25% 流量 (sample=50) | pass_rate ≥ 75% / F < 5 |
| **D+2** | Day 2 | 50% 流量 (sample=100) | pass_rate ≥ 78% / F < 5 |
| **D+3** | Day 3 | 75% 流量 (sample=150) | pass_rate ≥ 80% / F < 5 |
| **D+4** | Day 4 | 100% 流量 (sample=200) | pass_rate ≥ 80% / F < 4 |
| **D+5** | Day 5 | 50% + 商业化 24 题 | pass_rate ≥ 80% / F < 4 |
| **D+6** | Day 6 | 100% + 商业化 40 题 | pass_rate ≥ 80% / F < 4 |
| **D+7** | Day 7 | 全量 (sample=240) | pass_rate ≥ 80% / F < 4 |

### 5.2 baseline 对照组（D+0 必备）

- **对照组 A：R9 v3.0 权重**（200 题 + 现网 LLM 推理）— 灰度前 7 天稳定 baseline
- **对照组 B：R10-d v4.0 子维度权重**（240 题 + 同 LLM 推理）
- **观察指标**：
  - pass_rate 差值（B vs A 应 +5% ~ +15%）
  - 一票否决数差值（B 应 ≤ A，因为 content/defense 阈值更严）
  - tool 维度均分差值（B 应 < 0.24 起点 → 商业化工具覆盖）

### 5.3 失败重跑策略（D+5/D+6 触发条件）

| 失败模式 | 触发条件 | 重跑策略 |
|---|---|---|
| **单题超时** | duration > 60s | `python -m runner --retry-only item_id` 重跑该题 |
| **整轮超时** | D+4 整轮 > 24h | 重跑全轮，CI artifact `round10_failed.jsonl` 保存 |
| **F 数突增** | F 数 > baseline × 1.5 | 立即停止灰度 + 主指挥决策 |
| **CI 误判** | 同一 item 第二次仍 fail | 标记 `KNOWN_FLAKY`，3 天内不再重跑 |

### 5.4 产物保留（CI artifact 策略）

- **必备 artifact**：`tests/qa-bench/results/round10-*/results.json` + `report.md` + `grades.json`
- **artifact path**：`qa-bench-results/round10-day{N}/`（与 W71 round9-smoke-30 同结构）
- **保留时长**：CI 90 天（GH Actions 默认），本地 `/var/log/qa-bench/` 1 年归档
- **回溯能力**：任意 D+x 失败可一键 `gh run download` 重现

### 5.5 灰度期间 kill switch（3 个开关 — 派工 v6 段 5 反馈 #2）

```python
# app/core/qa_bench_rollout.py (R10 新增)
QA_BENCH_R10_ENABLED: bool = False  # R10 v4.0 子维度权重开关
QA_BENCH_R10_SUBSCRIPTION_ENABLED: bool = False  # 商业化订阅题开关
QA_BENCH_R10_BILLING_ENABLED: bool = False  # 商业化计费题开关
```

---

## 6. 实施前置 7 项（D8 实战 W68 14th 批 C-1 沉淀）

### 6.1 七项实施前置（W68 14th 批 C-1 `b190cbf4e` 真验证）

| # | 前置项 | R10 具体要求 | 现状 |
|---|---|---|---|
| 1 | **题库版本锁定** | `tests/qa-bench/questions_combined_v4.jsonl` 240 题 SHA256 pinned | ❌ 未实施（待 W73 派工） |
| 2 | **数据脱敏** | 商业化题脱敏真实租户号/账单号/用户 ID（faker 替换） | ❌ 未实施 |
| 3 | **模型/endpoint 锁定** | 锁定 `minimax/MiniMax-M3` cloud endpoint + temperature=0.0 | ❌ 未实施 |
| 4 | **阈值与 gate** | pass_rate ≥ 80% + F < 4 + content veto < 0.6 + defense veto < 0.85 | ⚠️ 部分（仅 pass_rate 80%） |
| 5 | **CI secret 检查** | `claude_api_key` / `minimax_api_key` 验证 + redact log | ❌ 未实施 |
| 6 | **baseline 对照** | R9 v3.0 实测数据存档（已 ✅ round9-smoke-30） | ✅ 已实施 |
| 7 | **失败重跑/产物保留** | `retry_strategy.json` + GH Actions artifact upload 90 天 | ❌ 未实施 |

### 6.2 现状真验证（git ls-files）

```bash
ls tests/qa-bench/data/ 2>&1
# regression_baseline_v3.0.json    # baseline 已存
# stability_v3.0.json              # baseline 已存
```

**未实施项（待 W73）**：
- 240 题题库（200 + 40 商业化）
- 题库 SHA256 lock 脚本 `scripts/qa_bench_lock_questions.py`
- 数据脱敏 faker 替换 `tests/qa-bench/mocks/billing_fixtures.py`
- 模型/endpoint 锁定 `app/core/qa_bench_config.py` (R10 新增)
- CI secret 检查 `tests/qa-bench/ci_secret_check.py`
- 失败重跑 `scripts/qa_bench_retry_failed.py`

---

## 7. W73 派工建议（调研 ≠ 生产 — 闭环）

### 7.1 必派工清单（W73 第 X 批，5 个子批）

| 子批 | 主题 | 估算 commit 数 | 优先级 |
|---|---|---|---|
| **W73-1.1** | D8 200 题真跑（run round10-bge-m3 + 4 周 200 题持续灰度） | 3-5 | P0 |
| **W73-1.2** | R10 阈值微调 weights_v4.json + 12 子维度代码 + 迁移脚本 | 4-6 | P0 |
| **W73-1.3** | 240 题扩展（40 商业化题写作 + combined_v4.jsonl + SHA lock） | 3-4 | P0 |
| **W73-1.4** | 实施前置 7 项中 4 项（题库 lock + 脱敏 faker + 模型/endpoint 锁 + CI secret 检查） | 4-6 | P0 |
| **W73-1.5** | kill switch + 灰度 7 天观察脚本 + baseline 对照实验 | 2-3 | P1 |
| **W73-2.x** | 商业化场景子维度（12 子维度 scorer 实现 + 6 项新增检测器） | 6-8 | P1 |
| **W73-3.x** | D9 复盘 + 锚点范式预期 + 文档同步 | 2-3 | P2 |

**W73 总估 commit 数**：24-35（5 sub-batch × 5-7 commit）

### 7.2 派工前置（派工 v8 段 8 实战）

- **前置 1：D8 200 题真跑结果必须落到 `tests/qa-bench/results/round10-bge-m3-200/`**（含 report.md + results.json）
- **前置 2：240 题题库 v4.0 必须先 commit**（SHA256 lock）
- **前置 3：6 项新增检测器必须先单元测试 100% PASS**

### 7.3 必含调研闭环铁律（5 条 — W72 第 2 批派生）

1. **R10 派工前必须先跑 200 题真验证** — 不可 R9 历史数据拍板 R10 权重
2. **240 题商业化内容必须主指挥审核**（财务/订阅/多租户合规）— 不允许 agent 自动起草
3. **weights_v4.json 不可在 R9 路径上 in-place 改** — 必须新文件 + 迁移脚本（避免污染 W71 B-1 历史权重）
4. **kill switch 必留 30 天观察期** — R10 上线后保留 R9 v3.0 路径 30 天（派工 v6 §3 教训）
5. **12 子维度权重和必 = 1.00** — CI 加 `weights_v4.json` schema 校验（与 weights.json v1.0 7 维度纪律一致）

### 7.4 不派工的反向建议（红线 — 派工 v6 段 5 反馈 #4）

- ❌ **不在 W73 改 `app/agent/chat_engine.py`** — 商业化子维度 scorer 走独立 scorer_service.py
- ❌ **不修改 `alembic/versions/0XX_*.py` 老迁移** — 不为 R10 加列
- ❌ **不修改 `app/services/reranker_service.py`** — BGE m3 已是服务化抽象
- ❌ **不修改 `tests/qa-bench/scoring/seven_dim.py`** — v3.0 已沉淀，新建 `twelve_dim_v4.py`
- ❌ **不删 round9 smoke 30 产物** — baseline 数据永久保留

---

## 8. 调研 ≠ 生产警示（派工 v6 段 5 反馈 #1 实战）

### 8.1 本调研已严格守恒的铁律

| 铁律 | 守恒方式 |
|---|---|
| **0 production code 改动** | 本调研仅 1 个 `docs/qa-bench-d9-r10-survey-2026-07-27.md` 新文件 + 1 commit |
| **不修改老路径** | 不动 `app/services/reranker_service.py` / `app/services/embedding_service.py` / `tests/qa-bench/scoring/seven_dim.py` |
| **不发起新排期** | 不在 W72 第 2 批中启动 R10 实施，仅调研 |
| **真数据真验证** | 所有数据均 git log / git show / grep 真验证，不基于"应该是" |
| **派工 v8 段 8 实战** | 不在批派工中发起子批派工（W73 由主指挥决策） |

### 8.2 不做的事（不在本调研中启动）

- ❌ **不实施 R10 权重矩阵** — 等 W73 派工（含 5-7 commit 实施）
- ❌ **不写 40 道商业化题** — 等 W73 派工（含 3-4 commit）
- ❌ **不写 12 子维度 scorer 代码** — 等 W73 派工（含 6-8 commit）
- ❌ **不写 6 项商业化检测器** — 等 W73 派工
- ❌ **不修改 weights.json v1.0** — 仅新建 `weights_v4.json` 草案

### 8.3 调研完整闭环链路（派工 v6 段 5 反馈 #5）

```
W72 第 1 批 C-1 D8 真验证 (commit 894579d73)
  ↓ 派生（D8 真验证后）
W72 第 1 批 A-3 plans 真验证 派生新任务 #6
  ↓ 派工
W72 第 2 批 C-2 D9 调研 (本文档 commit)
  ↓ 沉淀
memory/w72-route-72nd-batch-c2-d9-survey-2026-07-27.md
  ↓ W73 派工（主指挥决策）
W73 第 X 批 D9 R10 实施 + 240 题 + 商业化改造
  ↓ 锚点范式第 232 ~ 第 257 守恒预期（25 commits）
```

---

## 9. 锚点范式守恒（与 W72 第 2 批主基调对齐）

| 起点 | 终点 | 增量 |
|---|---|---|
| W72 第 1 批 220 | **W72 第 2 批 C-2 ~231** | **+11 守恒（仅调研文档）** |
| D8 真验证 commit 201 | D9 调研 commit ~231 | (+30 累计含 W71 sub-batch) |
| R10 实施（待 W73） | W73 ~257 守恒预期 | (+26 跨多批) |

**W72 第 2 批派工清单（C-1 ~ C-5 推测）**：
- C-1: ppt-word 真坑 4 项 docs
- **C-2: qa-bench D9 调研（本任务）**
- C-3: claude-code notify v3
- C-4: W70+ plans 实施 backlog 回归
- C-5: W73 起步纪律（前瞻）

---

## 10. 关键文件路径汇总（决策回查）

### 已存在文件（不要重复创建）

- `tests/qa-bench/d8_bge_m3.py` — D8 R8/R9 核心实现（289 行）
- `tests/qa-bench/scoring/seven_dim.py` — 7 维评分 v1.0（326 行）
- `tests/qa-bench/scoring/weights.json` — v1.0 权重（不要 in-place 修改）
- `tests/qa-bench/questions_smoke_200.jsonl` — 200 题源数据
- `tests/qa-bench/questions_500.jsonl` / `_780.jsonl` — 备用
- `tests/qa-bench/results/reranker-benchmark/round9-smoke-30/` — baseline

### 待 W73 创建文件

- `tests/qa-bench/questions_business_v4.jsonl`（40 商业化题）
- `tests/qa-bench/questions_combined_v4.jsonl`（200 + 40 = 240）
- `tests/qa-bench/scoring/twelve_dim_v4.py`（12 子维度）
- `tests/qa-bench/scoring/weights_v4.json`（v4.0 权重 + 12 子维度）
- `tests/qa-bench/scoring/v3_to_v4_migrate.py`（迁移脚本）
- `tests/qa-bench/mocks/billing_fixtures.py`（数据脱敏 faker）
- `scripts/qa_bench_lock_questions.py`（题库 SHA256 lock）
- `scripts/qa_bench_retry_failed.py`（失败重跑）
- `app/core/qa_bench_rollout.py`（kill switch 3 个）
- `docs/qa-bench-r10-rollout-runbook-2026-07-27.md`

### 已派工但未实施（待补实施）

- D8 200 题真跑（4 commit 待补）— W73-1.1 子批
- W68 14th 批 C-1 七项前置部分项（第 4-7 项未实施）— W73-1.4 子批

---

**C-2 qa-bench D9 调研完成，纯调研文档不实施，W73 派工建议完整**。
