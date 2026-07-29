---
name: w71-grand-closure-71st-batch-2026-07-24
description: "W71 第 1 批 15 agents 预期 grand closure — 锚点范式 W70 168 → W71 ~184 单调上升预期 (预测 16 守恒, 0 失败), plans 优先 + 小修搭配 + 路线 fallback + W72 子 plan ③ 起步, 11 批累计预计 158 agents / 53 plans + 30 子 plan ② 闭环 / 8 子 plan ③."
metadata:
  node_type: memory
  type: project
  originSessionId: W71-71st-batch-grand-closure
  modified: 2026-07-24T00:00:00.000Z
---

# W71 第 1 批 15 agents 预期 grand closure (2026-07-24 — 锚点范式 W70 168 → W71 ~184 单调上升预期)

> 本文件是 W71 第 1 批 A-4 在全部 15 agent 完工前写下的**预期版** grand closure。数字、交付状态与锚点范式均明确标注为预测值；待 D-3 拍板、15 worktree 完成审核并合并后，由主拍 (A-1) 补写实际结果。不得把本文件的预期值误读为已完成事实。
>
> **W71 是 W68 第 14 批 D-4 主拍决策的"选项 A"实施** (W68 第 14 批 D-4 决策: `memory/w68-route-14-d4-w71-decision-2026-07-24.md` + `docs/w71-final-decision-2026-07-24.md`)。本批 15 agents 是 W71 选项 A 的完整 PR 派工版, 累计 8-10 文件 ~1673 行净增 (已批 6 类例外).

## TL;DR

W71 第 1 批延续"W68 第 14 批 D-4 选项 A"任务模式 (子 plan ② qa-bench 7 维 + 5 道防线 + KB 闭环 + Dashboard + CI smoke), 派工 15 agents, 分为 A 主拍部署、B 子 plan ② 实施、C 调研与小修、D 收尾四条路线。当前预期锚点范式由 W70 第 168 守恒提升至 W71 第 184 守恒, 单批预计新增 16 个锚点、0 失败。11 批累计预计 158 agents (含 3 hot-fix)、53 plans 闭环 + 30 子 plan ② 闭环, W68 累计 commits 达 255+。

本批坚持 0 production code 改动铁律, 预计 16/15 守恒 (5 例外预算: tests/qa-bench/ 新增 + web/src/views/admin/ 新增 + app/services/ <50 行增量 + .github/workflows/ <5 行增量 + 1 文件重写); W71 文件清单 9 文件 ~1673 行已派 v6 派工前提 5 类失败回滚守恒.

**预期声明**: A-4 不等待其他 14 agent 完工; 以下"完成""守恒""提交"均为派工目标或预测, 实际值由 D-3 完工后补, A-1 主拍审订.

---

## 1. TL;DR

### 1.1 W71 第 1 批 4 路线 15 agents 派工清单

| Agent | 路线 | 任务 | 类型 | 预期锚点/标记 | 0 production code |
|-------|------|------|------|---------------|-------------------|
| A-1 | A | 主拍部署收口 (本批主拍) | 部署/决策 | 主拍板 + 锚点第 169 守恒 | 守恒 |
| A-2 | A | 派工纪要 v7 (子 plan ②+③ 5 段 prompt 模板) | 协调沉淀 | 锚点范式第 170 守恒 | 守恒 |
| A-3 | A | W72 子 plan ③ NavRail 起步 + W72-W73 派工规划 | plans/调研 | 锚点范式第 171 守恒 | 守恒 |
| A-4 | A | 本 grand closure (本任务) | memory | 锚点范式第 195 守恒 | 守恒 |
| B-1 | B | qa-bench 7 维评分 (tests/qa-bench/scoring/seven_dim.py) | qa-bench 实施 | 锚点范式第 172 守恒 | **批准例外 1: qa-bench 新增** |
| B-2 | B | KB 5 道防线 (dedup + length + refusal + sensitive + audit) | KB 闭环实施 | 锚点范式第 173 守恒 | **批准例外 2: qa-bench 新增** |
| B-3 | B | Celery auto_intake_rollback_task + save_to_kb 重写 | Celery/服务 | 锚点范式第 174 守恒 | **批准例外 3: qa-bench 重写 + service 增量** |
| B-4 | B | KB 闭环 (知识入库自动审计触发) | KB 闭环 | 锚点范式第 175 守恒 | **批准例外 4: service 增量** |
| B-5 | B | QaBenchDashboard + CI smoke 200 题 | 前端 + CI | 锚点范式第 176 守恒 | **批准例外 5: web admin view + workflow** |
| C-1 | C | qa-bench D8 七项前置调研深化 | 调研 | 锚点范式第 177 守恒 | 守恒 |
| C-2 | C | sub-agent 编排范式 v2 沉淀 | 协调沉淀 | 锚点范式第 178 守恒 | 守恒 |
| C-3 | C | claude-code notify v2 回归测试 + alarm 监控脚本 | 工具链验证 | 锚点范式第 179 守恒 | 守恒 |
| D-1 | D | 派工纪要 v8 (v7 落地反馈 + 调研收尾反哺) | 协调沉淀 | 锚点范式第 180 守恒 | 守恒 |
| D-2 | D | 6 类文档同步 | 文档同步 | 锚点范式第 181 守恒 | 守恒 |
| D-3 | D | 锚点范式第 184 实际收束 | 记忆沉淀 | 锚点 195 → 184 实际收束预测 | 守恒 |

**分布**: A 4 + B 5 + C 3 + D 3 = 15 agents. A-1 是主拍任务; A-4 是本预期 grand closure, D-3 负责锚点实际收束.

---

## 2. W71 第 1 批 4 路线 15 agents 派工总览

### 2.1 A 路线: 主拍与计划前置 (4 agents)

- **A-1 主拍部署收口**: 核对 B-1~B-5 的测试 + 服务增量 + workflow 清单, 容器复制、缓存清理、重启与 baseline 71+7 守恒验证; 所有部署动作由主拍板, agent 不直接 merge main. **职责**: 是本批唯一的"实际 deployment"责任人.
- **A-2 派工纪要 v7**: 把子 plan ②+③ 派工前提 (alembic verify + PS 5.1 + plans 真验证 + 派工前提 + 失败回滚 5 类) 写进派工模板; 不得抹掉 v1-v6 的历史约束.
- **A-3 W72 子 plan ③ NavRail 起步**: W72 子 plan ③ NavRail 起步 + W72-W73 派工规划; 以真实 git log / git show / 文件内容验证计划状态.
- **A-4 grand closure**: 只写 memory, 不实施业务代码; 本文件先保存预测版本, 待主拍后续补实际值.

### 2.2 B 路线: 子 plan ② 实施 (5 agents)

W68 第 14 批 D-4 决策选项 A 推荐的 5 个子 plan ② 任务, 每个对应 W71 选项 A 必交付物:

- **B-1 qa-bench 7 维评分 (`tests/qa-bench/scoring/seven_dim.py` + `weights.json`)**: NEW ~200 行, 七维 (正确性 + 完备性 + 连贯性 + 实用性 + 安全性 + 可解释性 + 时延); 配置权重 (~30 行 JSON); 已派 v6 §2.
- **B-2 KB 5 道防线 (5 NEW 文件, ~310 行)**: `dedup.py` + `length_filter.py` + `llm_refusal.py` + `sensitive_words.py` + `auto_intake_audit.py`; 进入 qa-bench 知识入库审计管线.
- **B-3 Celery auto_intake_rollback_task (NEW ~100 行 service + 重写 save_to_kb.py ~280 行)**: 把 7 维 + 5 道防线 串成 Celery 异步任务; save_to_kb 是 qa-bench 已存 .py 但需按 v7 升级.
- **B-4 KB 闭环 (knowledge auto-intake audit 触发)**: KB 入库后自动审计, 触发 7 维 + 5 道防线; 写入 Celery beat 调度.
- **B-5 QaBenchDashboard.vue + `tests/qa-bench/ci/smoke_200.py` + `.github/workflows/qa-bench-smoke.yml`** (NEW ~580 行): Vue 仪表盘 + 200 题 smoke CI + GitHub Actions; 配置 secret.

### 2.3 C 路线: 调研与小修 (3 agents)

- **C-1 qa-bench D8 七项前置深化调研**: 在实施前核对 benchmark 数据、gate、CI 依赖和缺口; 形成可执行 backlog, 不虚报 D8 已完成.
- **C-2 sub-agent 编排范式 v2 沉淀**: 把 W68-W71 跨主题派工范式 (主拍协调 + 子 plan ② 起步 + 派工纪要 v1-v6) 沉淀到 memory; 不改生产代码.
- **C-3 claude-code notify v2 回归测试 + alarm 监控脚本**: 验证仓库模板在目标环境可安装、触发器可用、PS 5.1 与 shell 路径一致; 不把验证误写成新的业务功能.

### 2.4 D 路线: 收尾与拍板 (3 agents)

- **D-1 派工纪要 v8**: 在 v7 基础上增加 v7 落地反馈 + 调研收尾反哺 + 子 plan ③ 5 段 prompt; 不推倒旧模板.
- **D-2 6 类文档同步**: 同步 CLAUDE.md、ROADMAP.md、CHANGELOG.md、README.md、项目 MEMORY.md 与用户级 MEMORY 索引; 历史文档不重写.
- **D-3 锚点范式第 184 实际收束**: 待全部 15 agent 报告审阅后, 确认第 169-184 锚点; 在实际不足时必须改正预测.

---

## 3. W71 B 路线 5 agents 子 plan ② 实施明细

### 3.1 B-1 qa-bench 7 维评分 (锚点范式第 172 守恒, NEW ~230 行)

**交付清单**:
- `tests/qa-bench/scoring/seven_dim.py` (~200 行) — 7 维评分主函数:
  - 正确性 (correctness): LLM-as-judge 1-5 分
  - 完备性 (completeness): 答案字段覆盖率
  - 连贯性 (coherence): embedding 余弦 + LLM 流利度
  - 实用性 (practicality): 答案长度 + 实际操作步骤比例
  - 安全性 (safety): 敏感词 + prompt injection 检测
  - 可解释性 (interpretability): 推理链长度 + 引用数
  - 时延 (latency): 实测响应时间 (P50 / P95)
- `tests/qa-bench/scoring/weights.json` (~30 行) — 七维权重配置 (默认 0.15 + 0.15 + 0.10 + 0.15 + 0.20 + 0.10 + 0.15); 可热加载
- 单测 `tests/qa-bench/scoring/test_seven_dim.py` (~150 行) — 覆盖每维主路径 + 边界

**派工前提 (派工 v6 段 7 #3)**:
- 必须先验 weights.json schema (`json.loads` 能 parse)
- 必须先验 7 维打分函数 signature 一致 (LLM-as-judge 接收 (q, a, ref) → float)
- baseline 71+7 守恒预期: 新增单测 0 失败

### 3.2 B-2 KB 5 道防线 (锚点范式第 173 守恒, NEW ~310 行)

**交付清单**:
- `tests/qa-bench/kb_queue/dedup.py` (~80 行) — 知识条目去重 (embedding 余弦 ≥ 0.95 合并, hash 兜底)
- `tests/qa-bench/kb_queue/length_filter.py` (~40 行) — 长度过滤 (< 50 字 / > 5000 字 直接 reject)
- `tests/qa-bench/kb_queue/llm_refusal.py` (~60 行) — LLM 拒绝回答类 ("我无法..." 类)
- `tests/qa-bench/kb_queue/sensitive_words.py` (~50 行) — 敏感词 (内部项目代号 + 人名 + 薪资)
- `tests/qa-bench/kb_queue/auto_intake_audit.py` (~80 行) — auto-intake 串行入口 (call 5 防线顺序)

**派工前提**:
- 5 道防线必须串行 (前序失败短路), 不可并行
- dedup 必须有 summary cache, 避免 LLM 重算
- sensitive_words 词表必须从 `app/services/knowledge_service.py` 复用 (W68 第 9 批 §3 永久纪律)

### 3.3 B-3 Celery auto_intake_rollback_task (锚点范式第 174 守恒, NEW ~100 行 + 重写 ~280 行)

**交付清单**:
- `app/services/qa_bench_tasks.py` (NEW ~100 行) — Celery auto_intake_rollback_task (5 防线 reject 自动 revert knowledge.status='failed_audit'); beat schedule 24h
- `app/config.py` (MOD +3) — 3 个 settings (QA_BENCH_AUTO_INTAKE_AUDIT_ENABLED / _INTERVAL_HOURS=24 / _RETENTION_DAYS=7)
- `tests/qa-bench/save_to_kb.py` (重写 ~280 行) — 按 v7 升级, 触发 7 维 + 5 防线 (不再只 save_to_kb)

**派工前提**:
- `app/services/qa_bench_tasks.py` 不污染 `app/services/knowledge_service.py` (CLAUDE.md "0 production code 改动铁律" — knowledge_service 是老路径, 不动)
- Celery worker 必须有 NullPool + asyncio.run 重启 (W68 第 12 批 §3 永久纪律)
- save_to_kb 重写必须保留原 function signature (`save_to_kb(item: dict) -> bool`), 否则回归失败

### 3.4 B-4 KB 闭环 (锚点范式第 175 守恒, service ~30 行 + script ~50 行)

**交付清单**:
- `app/services/qa_bench_tasks.py` (MOD +30) — KB 闭环: knowledge 入库 → 7 维 + 5 防线 → 失败 auto_revert; 成功 send notification (Web Push)
- `app/services/notification_service.py` (MOD +20) — 新增 `notify_kb_audit_failed(knowledge_id, reason)` 函数; 不改老 notify_* 函数 (0 production code 铁律)
- `tests/qa-bench/kb_queue/auto_intake_audit.py` (MOD +25) — 闭环入口写库 (audit_log 表)

**派工前提**:
- 必须先验 Celery worker + Redis 状态 (W68 第 11 批 §2 永久纪律)
- notification_service.py 增量必须 fix_amount = 老接口 0 改动 (新增函数不算改老)

### 3.5 B-5 QaBenchDashboard + CI smoke (锚点范式第 176 守恒, NEW ~580 行)

**交付清单**:
- `tests/qa-bench/dashboard/index.html` (NEW ~150 行) — qa-bench 仪表盘 (七维分 + 5 防线命中 + KB 闭环成功率; ECharts 雷达图; 复用项目 Coral 主题 token)
- `tests/qa-bench/ci/smoke_200.py` (NEW ~150 行) — 200 题 smoke CI (从题库随机 200 + 7 维 + 5 防线 + gate)
- `web/src/views/admin/QaBenchDashboard.vue` (NEW ~400 行) — Vue 嵌入页面 (路由级 admin 入口, 不侵入老 admin)
- `web/src/api/qaBenchDashboard.js` (NEW ~60 行) — API 绑定 (GET /qa-bench/dashboard + /metrics)
- `.github/workflows/qa-bench-smoke.yml` (NEW ~30 行) — GitHub Actions workflow (cron nightly + 手动 trigger; mimo secret 注入)

**派工前提**:
- QaBenchDashboard.vue 必走 web 例外 (CLAUDE.md 永久纪律: vue 例外清单允许, 不动老 view)
- smoke_200.py 必须从题库 v3.0 真实随机 (W62 后 baseline 题库 ~700 题)
- GitHub Actions 必须 fail fast (任一 assert 失败立即 exit 1, 不 catch)

---

## 4. W70 锚点范式 W70 168 → W71 ~184 守恒预期

### 4.1 预期锚点编号

| 锚点 | 任务 | 预期守恒 |
|------|------|----------|
| 第 169 | A-1 主拍部署收口 | 单守恒 |
| 第 170 | A-2 派工纪要 v7 | 单守恒 |
| 第 171 | A-3 W72 子 plan ③ 起步 | 单守恒 |
| 第 195 | A-4 本 grand closure 预期版 | 1 暂存 (主拍补实际) |
| 第 172 | B-1 qa-bench 7 维评分 | 单守恒 |
| 第 173 | B-2 KB 5 道防线 | 单守恒 |
| 第 174 | B-3 Celery auto_intake_rollback_task | 单守恒 |
| 第 175 | B-4 KB 闭环 | 单守恒 |
| 第 176 | B-5 QaBenchDashboard + CI smoke | 单守恒 |
| 第 177 | C-1 qa-bench D8 七项前置深化 | 单守恒 |
| 第 178 | C-2 sub-agent 编排范式 v2 沉淀 | 单守恒 |
| 第 179 | C-3 claude-code notify v2 回归 | 单守恒 |
| 第 180 | D-1 派工纪要 v8 | 单守恒 |
| 第 181 | D-2 6 类文档同步 | 单守恒 |
| 第 184 | D-3 锚点范式实际收束 | 单守恒 |
| 第 182-183 | (预留 D-3 内嵌锚点) | 2 守恒 |

**预期总数**: W70 第 168 守恒 → W71 第 184 守恒, **新增 16 个锚点 (169-184), 0 失败**.

### 4.2 四维度核对预期 (派工 v7 必含)

每个锚点收束时必须同时核对:

1. **编号连续性** — 不跳号; 重复或占位都算失败
2. **agent 任务映射** — 每个锚点对应 1 个 agent commit hash; 不能挂错标签
3. **可复现证据** — `git log --grep="<anchor-keyword>"` + `git show <hash>` 必须能找到
4. **0 production code 守恒/批准例外** — 每个 agent 必须明确标注守恒或例外类别

---

## 5. W71 0 production code 改动铁律 16/15 守恒预期

### 5.1 5 例外预算

| Agent | 改动范围 | 守恒/例外 | 例外类别 |
|-------|----------|-----------|----------|
| A-1 | 部署命令、核对、拍板 | 守恒 | — |
| A-2 | memory/派工模板 | 守恒 | — |
| A-3 | plans 调研 | 守恒 | — |
| A-4 | 本 memory | 守恒 | — |
| **B-1** | `tests/qa-bench/scoring/*` (7 维) | **批准例外 1** | qa-bench 新增 |
| **B-2** | `tests/qa-bench/kb_queue/5 道防线` | **批准例外 2** | qa-bench 新增 |
| **B-3** | `app/services/qa_bench_tasks.py` + `tests/qa-bench/save_to_kb.py` 重写 + `app/config.py` +3 | **批准例外 3** | service 增量 + qa-bench 重写 |
| **B-4** | `app/services/qa_bench_tasks.py` + `app/services/notification_service.py` 增量 | **批准例外 4** | service 增量 (< 50 行) |
| **B-5** | `tests/qa-bench/dashboard/` + `web/src/views/admin/QaBenchDashboard.vue` + `web/src/api/qaBenchDashboard.js` + `.github/workflows/qa-bench-smoke.yml` | **批准例外 5** | web admin view + workflow (< 5 行 workflow) |
| C-1 | qa-bench D8 调研 | 守恒 | — |
| C-2 | sub-agent 编排范式沉淀 | 守恒 | — |
| C-3 | notify v2 回归测试 + alarm 脚本 | 守恒 | — |
| D-1 | memory/派工纪要 v8 | 守恒 | — |
| D-2 | 六类文档同步 | 守恒 | — |
| D-3 | 锚点 memory | 守恒 | — |

**预期结论**: 11/16 agents 不改 production code (含本任务 A-4 守恒); 5/16 agents 已批例外 (B-1~B-5). 例外不扩大到老路径重构; B-3 必须保证 `knowledge_service.py` 0 改动, B-4 必须保证 `notification_service.py` 老接口 0 改动. 派工 v6 §5 失败回滚 5 类必须 in-prompt.

**铁律来源**: W68 第 8 批 §3 "0 production code 改动铁律例外清单" 6 类允许:
- Drive v2 系列 ✅
- Mobile UX 系列 ✅ (本批不涉)
- qa-bench 系列 ✅ (本批 B-1/B-2/B-3 重写 + B-4 部分)
- alembic 迁移本身 ✅ (本批不涉)
- Plan 闭环实施 ✅ (本批不涉)
- scripts/ 自动化脚本 ✅ (本批 C-3 alarm 脚本 + B-5 smoke)

---

## 6. W71 派工实战数据 (15 agents × 估时)

### 6.1 单 agent 估时表

| Agent | 估时 | 难度 | 关键阻塞 | 派工 v6 段 7 复盘校验 |
|-------|------|------|----------|----------------------|
| A-1 | 0.5d | 低 | baseline 71+7 守恒 | v6 #1 #5 |
| A-2 | 0.5d | 低 | — | v6 #4 |
| A-3 | 1d | 中 | plans 真验证 | v6 #3 |
| A-4 | 0.5d | 低 | 显式 defer | v6 #2 |
| B-1 | 1.5d | 中-高 | weights.json schema + 7 维 gating | v6 #5 |
| B-2 | 1.5d | 中-高 | 5 防线串行 + sensitive 词表 | v6 #5 |
| B-3 | 2d | 高 | save_to_kb 重写 + Celery worker 兼容 | v6 #5 |
| B-4 | 1.5d | 中-高 | KB 闭环 + notification_service 老接口保护 | v6 #5 |
| B-5 | 2d | 高 | QaBenchDashboard.vue + GH Actions | v6 #5 |
| C-1 | 1d | 中 | 七项前置深化 | v6 #4 |
| C-2 | 1d | 中 | 范式凝练 + memory 索引 | v6 #4 |
| C-3 | 1d | 中 | notify 5 触发器回归 | v6 #3 |
| D-1 | 0.5d | 低 | v7 落地反馈回收 | v6 #4 |
| D-2 | 1d | 中 | 6 类文档 + 历史不动 | v6 #4 |
| D-3 | 0.5d | 低 | 锚点实际值 | v6 #5 |

**累计**: ~16.5d / 2 周 (按 ~50% 并行计算). 0 production code 铁律 16/16 守恒预期.

### 6.2 累计 14 agents 实战数据 (W68 第 13 批 + 第 14 批)

| 批次 | agents | plans 闭环 | 调研/小修 | 锚点范式 |
|------|--------|------------|-----------|----------|
| W68 第 5 批 | 15 + 3 hot-fix | 1 | 14 | 71→75 |
| W68 第 6 批 | 5 (审计) | 1 | 4 | 75 |
| W68 第 7 批 | 15 | 5 | 10 | 75→85 |
| W68 第 8 批 | 15 | 3 | 11 | 90→102 |
| W68 第 9 批 | 15 | 1 | 12 | 102→119 |
| W68 第 10 批 | 15 | 1 | 13 | 120→134 |
| W68 第 11 批 | 15 | 8 | 14 | 135→144 |
| W68 第 12 批 | 15 | 10 | 15 | 147→156 |
| W68 第 13 批 | 15 | 8 | 16 | 158→169 |
| W68 第 14 批 | 15 | 5 | 15 | 169→175 |
| **累计 10 批 (W68 第 5-14)** | **143 + 3 hot-fix** | **43** | **124** | **71→175 (104 守恒)** |
| W68 累计 commits | 240+ | — | — | — |

### 6.3 W71 第 1 批后预计累计

| 批次 | agents | plans 闭环 | 锚点范式 |
|------|--------|------------|----------|
| W68 第 5-14 批 | 143 + 3 hot-fix | 43 | 71→175 |
| **W71 第 1 批 (预期)** | **15** | **30 子 plan ②** | **175→184 (新增 9)** |
| **累计 11 批 (预期)** | **158 + 3 hot-fix** | **73 (53 + 20 子 plan ② 闭环)** | **71→184 (113 守恒)** |
| **W68 累计 commits (预期)** | **255+** | — | — |

> 说明: 30 子 plan ② 闭环 = W71 选项 A 5 agents 实施的累计子任务数 (B-1~B-5 每个含 5-8 子任务); 不与 W68 第 14 批的 53 plans plans 计划数冲突 (后者是 W66-W68 plans 总数).

---

## 7. W71 alembic 链守恒预期

### 7.1 W68 第 14 批后链状态

```text
W68 第 13 批后链: 070 → 074 → 075 → 076 → 077
W68 第 14 批后链: 077 → 078 → 079 → 080 (Drive v2 PR17/18/5)
W71 第 1 批前链: 080 (终点, 无新增)
```

### 7.2 W71 第 1 批 alembic 守恒

- **B-1~B-5 5 agents 0 alembic 改动**: 全部实施内容在 `tests/qa-bench/` + `app/services/qa_bench_tasks.py` (新) + `app/services/notification_service.py` (增量) + `web/src/views/admin/` + `.github/workflows/`; 不涉及 schema 变更.
- **链守恒预期**: 主链 `076 → 077 → 078 → 079 → 080` 5 个 head 不变.
- **派工 v6 段 7 #1 派工前提**: W71 第 1 批派工 prompt 必须显式写明 "本批 0 alembic 改动, 接 080"; 否则 B-3 在 save_to_kb 重写时如误加列, 自动失败.

### 7.3 alembic 链验证命令 (派工 v7 必含)

```bash
docker exec microbubble-agent-app-1 alembic heads
# 期望: 单 head ('080_drive_chunked_upload_revision_id')
# 异常: 2+ heads → 双头 → 主拍 rebase 改编号 (派工 v6 §3.1)
```

---

## 8. W71 调研发现新派工任务

### 8.1 A-3 W72 子 plan ③ 起步 + W72-W73 调研

W68 第 14 批 D-4 决策: W72 子 plan ③ NavRail (NEW ~250 行 vue component) + ThinkingModeSwitch (NEW ~80 行) + ChatBreadcrumb (NEW ~60 行) = 3 NEW + 8 MOD 共 12 文件 ~696 行. W71 第 1 批 A-3 必含派工规划:

- W72 子 plan ③ 5 段 prompt 模板 (alembic verify + PS 5.1 + plans 真验证 + 派工前提 + 失败回滚)
- W72 12 文件 ~696 行净增例外清单 (W68 第 8 批 §3 6 类允许)
- W72 → W73 派工衔接 (是否启动 B 路线 4 选项)

### 8.2 C-1 qa-bench D8 七项前置深化

W68 第 14 批 C-1 调研发现 7 项前置 (题库版本锁定 + 数据脱敏 + 模型/endpoint 锁定 + 阈值与 gate + CI secret 检查 + baseline 对照 + 失败重跑/产物保留策略); W71 第 1 批 C-1 深化:

- 题库 v3.0 → v4.0 迁移路径 (W62-W68 累计 700 题, 数据脱敏 80% 完成)
- 模型/endpoint 锁定: 主线 mimo, 备线 claude-sonnet-4-6, baseline 对照表
- CI secret 检查: mimo API key 注入 GitHub Actions secrets
- baseline 对照: 71 PASS + 7 SKIP (W62-W68 永久 baseline)
- 失败重跑策略: pytest -x + 保存 artifacts (jsonl + html)

### 8.3 C-2 sub-agent 编排范式 v2

W68-W71 跨主题派工范式 (主拍协调 + 子 plan ② 起步 + 派工纪要 v1-v6) 沉淀到 `memory/w71-sub-agent-orchestration-paradigm-v2.md`. 沉淀内容:

- 4 阶段流程 (出指令 → 监控 → 审核 → 上线沉淀)
- 5 协调铁律 (派工前提验证 + plans 真验证 + alembic 链 + baseline 守恒 + 失败回滚)
- 11 主拍协调范式铁律 (W2/W5/W7/W10 累计)
- 跨 session hot-fix 范式 (W68 第 8 批 §2.4)

### 8.4 派生新任务 (W72+ 派工 backlog)

A-3 + C-1 + C-2 调研 + 派生新任务 必含 plan 中未完成 + 派生新任务:

- **qa-bench D8 gate 实施**: 待 C-1 七项前置深化 + W71 B-1~B-5 实施后启动
- **W72 选项 A 3 agents 子 plan ③**: 待 W71 选项 A 实施收尾后启动
- **W73 backlog**: Drive v2 PR19-22 (W68 第 14 批 D-4 §1.2 选项 D); qa-bench D9 chatgpt style 评分
- **派工纪要 v8 调研收尾反哺**: D-1 v8 升级

---

## 9. W71 W19 选项 A 维持

本批不因 B 路线新增 qa-bench 测试/dashboard 或 C 路线小修而发起 W19 四个留未来 PR 的新排期. 继续维持选项 A:

- **Phase 8.5 dedup 模型重训**: 不启动, 等待标注数据与 GPU 资源条件
- **P3 dedup 跨 tab**: 不启动, W59 已完成部分实施, 先观察真实需求
- **P3 跨 tab session sync**: 不启动, 当前 localStorage/server 拉取兜底足够
- **7 项 E2E**: 按 Drive PR 与 Mobile/desktop 已有路线逐步补, 不另设独立大排期

D-3 的 W72-W73 拍板只负责确认触发条件与 backlog 优先级, 不得将"调研完成"写成"生产实施完成".

---

## 10. W71 任务模式基调延续

延续"W68 第 4 批主拍拍板基调 + W68 第 9 批 D-3 升级 v2 + W68 第 12 批 D-1 升级 v3 + W68 第 13 批 D-1 升级 v4 + W68 第 14 批 A-2 v5 + W68 第 14 批 D-1 v6" 5 拍板纪律:

1. **plans 优先** — 派工以已有 plans 实施为主 (本批 B-1~B-5 全部对应 子 plan ② 已知 backlog)
2. **小修搭配** — B 路线实施时调研发现的小修复合 C-1~C-3 (5 道防线补强 + 调研发现 fix)
3. **路线 fallback** — 当部分 plan 阻塞时, C-2 范式沉淀 / C-3 工具链验证补位 (永不无限扩大范围)
4. **W72 子 plan ③ 起步** — W72 选项 A NavRail + ThinkingModeSwitch + ChatBreadcrumb 起步由 A-3 调研后主拍拍板
5. **1 commit + defer message** — A-4 预期版 1 commit 落盘, defer 实际值给 D-3 完工后补

详细基准见 `memory/w68-task-mode-paradigm-plans-first-2026-07-24.md` + `docs/w68-task-mode-paradigm-v2.md` + `docs/w68-13th-batch-prompt-template-v4.md` + `docs/w68-14th-batch-prompt-template-v5.md`.

---

## 11. W71 派工沉淀新铁律预期 (12 条)

### 铁律 1 (派工 v7 段 1): 子 plan ② 5 段 prompt 必含 alembic verify

B-1~B-5 派工 prompt 段 1 必含 `docker exec microbubble-agent-app-1 alembic heads` 期望 1 个 head 验证; A-1 主拍部署前必跑. (W68 第 13 批 D-1 升级 v4)

### 铁律 2 (派工 v7 段 2): 子 plan ② 5 段 prompt 必含 PS 5.1

B-1~B-5 派工 prompt 段 2 必含 `powershell -Version 5.1` 路径一致性验证; A-1 主拍在云端部署前必跑 (CLAUDE.md 永久纪律).

### 铁律 3 (派工 v7 段 3): 子 plan ② 5 段 prompt 必含 plans 真验证

B-1~B-5 + A-3 派工 prompt 段 3 必含 `git log --all --grep="<plan-keyword>"` + `git show <commit>` + `grep -r "<feature>" app/ web/ tests/` 三步并行; 计划自报 status 仅作线索 (W68 第 7 批 §2.2 永久纪律).

### 铁律 4 (派工 v7 段 4): 子 plan ② 5 段 prompt 必含派工前提 4 条

B-1~B-5 派工 prompt 段 4 必含 4 条派工前提:
- commit partial diff (B-3 W68 第 14 批教训)
- 不动 v1-v6 历史约束
- 预期版必显式 defer
- 0 production code 改动铁律例外清单

### 铁律 5 (派工 v7 段 5): 子 plan ② 5 段 prompt 必含失败回滚 5 类

B-1~B-5 + A-1 派工 prompt 段 5 必含 5 类失败回滚:
- alembic 双头 → 主拍 rebase 改编号
- baseline 退化 → git revert
- 6 点 curl 502 → 修 nginx / SSH tunnel
- PWA manifest 404 → 跑 npm run build
- 端到端 fail → git revert + 派 hot-fix agent
(W68 第 14 批 D-4 §3 永久纪律)

### 铁律 6 (W71 实战 #1): qa-bench 7 维评分权重必 JSON 热加载

B-1 weights.json 必可热加载 (`json.loads` + 校验 7 维权重和=1.0); 否则 dashboard 显示 N/A. (本批 D-2 文档同步必写明)

### 铁律 7 (W71 实战 #2): KB 5 道防线必串行

B-2 5 道防线必须顺序执行 (dedup → length → refusal → sensitive → audit), 任一 reject 直接 return; 不允许并行 (否则 sensitive 词命中也入库, 安全违规). (本批 D-2 文档同步必写明)

### 铁律 8 (W71 实战 #3): Celery auto_intake_rollback_task 必 NullPool 重启

B-3 部署 qa_bench_tasks.py 必 `docker compose restart celery-worker` (NullPool + asyncio.run; W68 第 12 批 §3 永久纪律). save_to_kb 重写必保持原 signature.

### 铁律 9 (W71 实战 #4): QaBenchDashboard.vue 必走 admin 路由

B-5 QaBenchDashboard.vue 必挂 `router.beforeEach` admin 路由守卫 (`requiresAdmin` meta); 不允许普通用户访问 (涉及内部 qa-bench 数据).

### 铁律 10 (W71 实战 #5): GitHub Actions workflow 必 fail fast

B-5 `.github/workflows/qa-bench-smoke.yml` 必 `set -e` + 关掉 continue-on-error; 200 题 smoke 任一 fail 立即 exit 1. (CLAUDE.md §"GitHub Actions 5 触发器" 永久纪律)

### 铁律 11 (W71 部署 1): 10 步 deployment checklist 必含 baseline 71+7 守恒验证

A-1 主拍部署 10 步 (W68 第 14 批 D-4 §4) 第 3 步 `bash scripts/check_baseline.sh` (vitest 71 PASS + pytest 7 SKIP) 必须先跑; 否则部署自动失败. (`docs/w71-final-decision-2026-07-24.md` §6 完整)

### 铁律 12 (派工 v6 段 7 实战 #3 #4): 显式 defer + 不动历史约束

A-4 预期版显式 defer 全部实际值 (本文件); 不动 v1-v6 历史约束 (派工 v6 第 4 条铁律); 0 production code 改动铁律维持 (派工 v6 第 5 条铁律).

---

## 12. 派工实战 #4 W70 锚点范式 W70 168 → W71 ~184 守恒预期 (摘录自 §4)

### 12.1 单批新增锚点 (16 个预测)

169 (A-1) + 170 (A-2) + 171 (A-3) + 195 暂存 (A-4) + 172 (B-1) + 173 (B-2) + 174 (B-3) + 175 (B-4) + 176 (B-5) + 177 (C-1) + 178 (C-2) + 179 (C-3) + 180 (D-1) + 181 (D-2) + 184 (D-3) + 182-183 (D-3 内嵌)

### 12.2 0 失败守恒预期

- 每锚点必 4 维度核对 (编号 + agent + 证据 + 守恒)
- 任一失败 → D-3 必须改预测值并补写实际值
- 主拍 A-1 必须在全部 15 worktree 合并完成后, 回头修订本预期文件

---

## 13. W71 派工沉淀文件清单 (预期)

| 类别 | 文件/产物 | 责任 agent | 交付状态 |
|------|-----------|------------|----------|
| memory | `memory/w71-grand-closure-71st-batch-2026-07-24.md` (本文件) | A-4 | 本预期文件 |
| memory | 派工纪要 v7/v8 | A-2/D-1 | 待各自报告 |
| memory | W72 子 plan ③ 起步 + W72-W73 派工规划 | A-3 | 待派工 |
| memory | qa-bench D8 七项前置深化 | C-1 | 待调研 |
| memory | sub-agent 编排范式 v2 | C-2 | 待沉淀 |
| memory | claude-code notify v2 回归 + alarm | C-3 | 待验证 |
| tests | `tests/qa-bench/scoring/seven_dim.py` + `weights.json` | B-1 | 待实施 |
| tests | `tests/qa-bench/kb_queue/{dedup,length_filter,llm_refusal,sensitive_words,auto_intake_audit}.py` | B-2 | 待实施 |
| service | `app/services/qa_bench_tasks.py` (NEW + MOD) | B-3/B-4 | 待实施 |
| service | `app/services/notification_service.py` (增量) | B-4 | 待实施 |
| tests | `tests/qa-bench/save_to_kb.py` (重写) | B-3 | 待重写 |
| config | `app/config.py` (+3 settings) | B-3 | 待增量 |
| web | `web/src/views/admin/QaBenchDashboard.vue` + `qaBenchDashboard.js` | B-5 | 待实施 |
| tests | `tests/qa-bench/dashboard/index.html` + `ci/smoke_200.py` | B-5 | 待实施 |
| workflow | `.github/workflows/qa-bench-smoke.yml` | B-5 | 待实施 |
| docs | 6 类文档同步 (D-2) | D-2 | 待同步 |

本任务 (A-4) 自身仅新增 1 个 memory 文件 (`memory/w71-grand-closure-71st-batch-2026-07-24.md`); 不写 alembic, 不写 production code, 不改 main.

---

## 14. 不在本批范围

- 不提前实施 W72 子 plan ③ 中尚未经过 A-3 调研 + 主拍拍板的计划
- 不发起 qa-bench D8 gate 实施 (待 C-1 七项前置 + B-1~B-5 实施后)
- 不增加 B-1~B-5 5 agents 之外的 qa-bench 业务范围
- 不修改 nginx、Docker、生产配置或老路径 (notification_service.py 老接口 / knowledge_service.py)
- 不等待全部 15 agent 完工才写本预期文件
- 不合并到 main; A-4 分支仅供主拍审核与后续合并

---

## 15. 待主拍补写的 closure 字段 (A-1 收尾必补)

D-3 完成、15 agent 报告收齐 + 主拍 A-1 全部合并后, 应补写:

- 实际锚点编号 (169-184) 与是否确为 16 守恒
- 实际 5 例外预算是否成立 (B-1 qa-bench NEW + B-2 qa-bench NEW + B-3 service 增量+qa-bench 重写 + B-4 service 增量 + B-5 web admin view + workflow)
- 实际 11/16 agents 不改 production code 是否成立
- save_to_kb 重写是否保留原 function signature
- baseline 71+7 是否守恒
- alembic 链 1 个 head 是否保持 (本批无 alembic 改动)
- 6 点 curl 验证 (HTML + sw.js + manifest + QaBenchDashboard SPA fallback + pwa-192.png)
- PWA manifest 410 + 200 验证
- qa-bench smoke 200 题真跑结果
- 任何未完成、延期或偏离预期的 agent, 在 TL;DR、数据表、结尾同步修订

---

## 16. 参考

- `memory/w68-route-14-d4-w71-decision-2026-07-24.md` — W68 第 14 批 D-4 主拍 W71+W72 决策
- `docs/w71-final-decision-2026-07-24.md` — W71 选项 A 最终拍板文档
- `memory/w68-grand-closure-14th-batch-2026-07-24.md` — W68 第 14 批预期版模板
- `memory/w68-grand-closure-13th-batch-2026-07-24.md` — W68 第 13 批实际版模板
- `memory/w68-task-mode-paradigm-plans-first-2026-07-24.md` — plans 优先 + 小修搭配 + 路线 fallback
- `memory/w68-alembic-chain-discipline-2026-07-24.md` — 并行 migration 串单链纪律
- `memory/verified-plans-w68-2026-07-24.md` — plans 真验证口径
- `memory/future-pr-roadmap-2026-07-21.md` — W19 选项 A 与四项留未来 PR
- `docs/w68-13th-batch-prompt-template-v4.md` — 5 段 prompt 模板 (alembic verify + PS 5.1 + plans 真验证)
- `docs/w68-14th-batch-prompt-template-v5.md` — 派工 v5 反馈循环 + 合并顺序表
- CLAUDE.md — 项目生产代码、部署、migration 与文档同步铁律 + §"W68 第 6+7 批纪律沉淀 (永久锚点)"

---

**预期结论**: W71 第 1 批以 15 agents、四路线、子 plan ② 实施 + 调研收尾反哺为基调, 预期将锚点范式从 W70 第 168 推至 W71 第 184 (新增 16, 0 失败), 累计 158 agents (含 3 hot-fix)、73 plans 闭环 + 30 子 plan ② 闭环, W68 累计 commits 达 255+. 0 production code 改动预计 16/16 守恒, B-1/B-2/B-3/B-4/B-5 共 5 个已批例外 (qa-bench / service 增量 / web admin view / workflow). 派工纪要 v7 + 派工纪要 v8 双版本升级 (5 段 prompt 模板 + 调研收尾反哺). 5 类失败回滚 (alembic 双头 + baseline 退化 + 6 点 curl 502 + PWA manifest 404 + 端到端 fail) 必 in-prompt.

W71 是 W68 第 14 批 D-4 选项 A 完整 PR 派工版; W72 选项 A (3 agents 子 plan ③ NavRail) 由 A-3 调研后主拍拍板启动.

**派工状态**: 本文件按任务要求提前落盘, 不等待其他 14 agent 完工; 不合并 main.

**Commit message**: `memory(w71st-batch-a4): W71 grand closure memory 预期版 (15 agents 派工 + 4 路线 + 锚点范式 W70 168 → W71 ~184 守恒, 0 production code 改动铁律 16/15 守恒预期, 待 A-1 主拍补实际值)`

**Co-Authored-By**: Claude Fable 5 <noreply@anthropic.com>
**Date**: 2026-07-24
