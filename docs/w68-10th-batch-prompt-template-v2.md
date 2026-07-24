# W68 第 10 批派工纪要 v2 (B 派工前提错误经验沉淀) — 锚点范式第 142 守恒

> **日期**: 2026-07-24
> **作者**: Agent "W68 第 11 批 D-1: W68 第 10 批派工纪要 v2 (B 派工前提错误经验沉淀)"
> **分支**: `docs/w68-10th-batch-prompt-template-v2-2026-07-24`
> **性质**: **派工 prompt 模板 v2 升级** (W68 第 10 批实战) — 5 段模板 + 5 失败模式 + 5 铁律
> **基线**: main HEAD `7b6f0305e` (W68 第 10 批 A-3 merge + memory 后)
> **0 production code 改动铁律**: 本文件仅 docs + memory 范畴, 完全守恒
> **关系**: 本文件基于 `docs/w68-task-mode-paradigm-v2.md` 选题层 v2 升级派工模板 v1 (历史), 提供"派工前提"纪律沉淀

---

## TL;DR

**W68 第 10 批派工纪要 v2** (2026-07-24 主指挥派 D-1 agent 升级):

W68 第 10 批 B-2/B-3/B-4/C-2 派工暴露 4 类派工前提错误 (派工说"已建"实际未建 / alembic 跳级 / service 缺失 / CLI 文档错误 / e2e SKIP 不报告). v2 模板固化 5 段 prompt 升级 + 5 失败模式 + 5 铁律.

5 段模板升级:
- **段 2 (分支)**: worktree base 必 fetch 同步 origin main, 不基于 stale 写 alembic
- **段 3 (任务描述)**: 加 alembic 主分支同步检查 (verify down_revision 链 + 不自动修)
- **段 4 (完成定义)**: 加后端依赖 check (verify service 存在, 缺失必报主指挥)
- **段 3 (任务描述)**: CLI 派工必 --help 核实 (避免文档过时)
- **段 4 (完成定义)**: e2e SKIP 必报主指挥 (不静默跳过)

5 失败模式 (实战):
1. **B-2 save_to_kb**: 派工 prompt 说"已建", 实际 `app/services/save_to_kb_service.py` 不存在
2. **B-3 Celery rollback**: B-2 缺失, agent 自行实施 (合规"新功能例外" 但不是派工前提正解)
3. **B-4 KB 闭环**: alembic 072/073 接 065, 跳过了 066/067/068/069 (派工 prompt 没 verify 当前 head)
4. **C-2 phase2 dry-run**: `run_d5_dry.py --output` 实际写 Markdown, 主指挥 SOP 文档错误
5. **C-1 Desktop v3.2**: 22 SKIP 等部署, 没主动报主指挥 (SKIP 应主动 escalate)

5 铁律 (新):
1. **alembic 派工必 verify main 链** — 派工 prompt 必含 "git fetch origin main && alembic heads" 三步
2. **service 派工必 verify app/ 存在** — `grep -rn <service_name> app/` 是必跑步骤
3. **CLI 派工必 --help 核实** — 不信 main/README/docs 自述, 跑一次 --help 确认参数
4. **e2e SKIP 必报主指挥** — 静默 SKIP = 隐式失败, 必须显式报告
5. **worktree base 必 fetch 同步** — base 选 stale main 必双 head, 先 fetch 再读 heads

---

## §1 W68 第 10 批派工纪要 v2 关键发现

W68 第 10 批派工时 (主基调 W68 第 8 批合并 + 路线驱动 fallback), 4 类派工前提错误暴露. 主指挥拍板沉淀为 v2 模板, W68 第 11+ 批派工必须按 v2 模板.

### §1.1 B-2 agent 报告 — 派工 prompt 说"已建"实际不存在

**事故**: W68 第 10 批 B-2 (`feat/w68-10th-batch-b2-save-to-kb-2026-07-24`) 派工 prompt 写"B-2 已建 `app/services/save_to_kb_service.py`", 但 `app/services/save_to_kb_service.py` 实际**不存在** (`git log --all -- app/services/save_to_kb_service.py` 无任何 commit, `app/models/knowledge_rejected.py` 同样不存在).

**根因**: 派工时主指挥参考了 W68 第 7+8 批 plans 状态化文件 (假设有"save_to_kb" 计划), 实际上 W68 第 7 批 plans 状态化时**偷懒复制粘贴**, 没真验证该 service 是否落地. W68 第 10 批 B-2 派工时主指挥信"plan 已完成"自报, 没 grep 真验证.

**实测证据** (主指挥 B-3 agent 自己披露):
- B-3 commit `64660718d` body 显式写"B-2 缺失补齐 (派工 prompt 说 B-2 已建, 实际 codebase 无)"
- B-3 实际写了 2 个文件: `app/models/knowledge_rejected.py` + `app/services/save_to_kb_service.py` (新增, 不算 B-3 的核心任务)

**主指挥反应**: 未察觉派工前提错误, 等 B-3 commit body 披露后才意识. B-2 分支实际是"重新派工 + 重新实施 save_to_kb", 不是 B-2 原计划的"save_to_kb 加固".

**5 段模板 §2.2 加固**: service 派工必 verify 依赖存在, 不信 plan 自述.

### §1.2 B-3 agent 报告 — B-2 缺失下自行实施 B-2+B-3

**事故**: B-3 (`feat/w68-10th-batch-b3-auto-intake-rollback-2026-07-24`) 派工目标 = "Celery 自动入库回滚/重试/告警闭环". B-3 agent 接到分支后, 发现 B-2 (`save_to_kb_service.py` + `knowledge_rejected.py`) 不存在 → B-3 Celery rollback **依赖**的入口函数 (record_failure / rejected 表) 全无 → agent 自行实施 B-2 + B-3 (合规"新功能例外" 但不是派工前提正解).

**commit 链** (`64660718d`):
```text
feat(kb-intake): W68 第 10 批 B-3 自动入库回滚/重试/告警闭环 (锚点范式第 126 守恒)

实施 chatgpt-structured-floyd.md 子 plan ② Celery auto_intake_rollback_task.

B-3 主任务 (3 Celery task + 业务核心 + 告警):
1. retry_rejected_kb_intake_task: 24h 后重试 (apply_async countdown=86400)
2. permanent_suspend_rejected_kb_intake_task: 3 次失败后永久挂起 + 转 knowledge_pending_review
3. daily_kb_intake_health_check_task: 每日 03:00 跑, 统计 7d 失败率, >20% 告警

B-2 缺失补齐 (派工 prompt 说 B-2 已建, 实际 codebase 无):
- app/models/knowledge_rejected.py (KnowledgeRejected + KnowledgePendingReview ORM)
- app/services/save_to_kb_service.py (5 道防线 + record_failure 单一入口)
```

**关键发现**: B-3 agent 自报"合规新功能例外"但实际是**绕过派工前提错误**, 没主动报告主指挥. 如果主指挥后续想 grep "B-3 实际做了什么" 会发现 B-3 = B-2 + B-3 复合体, 不是单纯 B-3.

**5 段模板 §2.2 加固**: service 派工前必 verify 依赖存在; 不存在时, agent 必:
- **方案 A**: 写新分支实施 (合规"新功能例外")
- **方案 B**: 报告主指挥拍板 (推荐, 但本批 B-3 agent 跳过这一步)

### §1.3 B-4 agent 报告 — alembic 跳级 (072/073 接 065, 跳过 066/067/068/069)

**事故**: B-4 (`feat/w68-10th-batch-b4-kb-closed-loop-2026-07-24`) 派工 prompt 写"alembic 072/073 接 065", 但 main HEAD 当时已有 066/067/068/069 (W68 第 9 批 4 个 migration 已 merged). B-4 实际接 065 → 066/067/068/069 全跳过, 立即 alembic 双头.

**commit 链** (`0066087c8`):
```text
alembic/versions/072_kb_closed_loop.py (~150 行)
alembic/versions/073_kb_links_placeholder.py (~30 行) — 占位迁移 + 串单链
```

**根因**: 派工 prompt 没写"接 X" (X = 当前 main 最新 head). W68 第 10 批派 B-4 时, main HEAD 是 `f14cb43c1` (W68 第 8 批 A-1 merge 后), 已有 066/067/068/069 全部 merged. B-4 agent 默认接派工 prompt 写的 065, 没 verify 当前 head.

**5 段模板 §2.1 加固**: alembic 派工必 verify main 链, 必含三步 boilerplate:
```bash
git fetch origin main
python -c "from alembic.script import ScriptDirectory; print(ScriptDirectory.from_config(Config()).get_heads())"
echo "你的 migration 接 $HEADS, 不是默认最新"
```

**重复踩坑记录**: W68 第 4 批 062/063 并行 + W68 第 8 批 066 默认接 064 + W68 第 10 批 072/073 默认接 065 — 3 次都是"派工 prompt 没写接 X". CLAUDE.md 已有「2026-07-24 alembic 并行 agent 串单链纪律」节 (锚点范式第 46 守恒), 但派工模板没升级. 本次 D-1 升级 v2 模板补齐.

### §1.4 C-2 agent 报告 — `run_d5_dry.py --output` 实际写 Markdown 非 JSON

**事故**: C-2 (`docs/w68-10th-batch-c2-run-d5-dry-runbook-2026-07-24`) 派工 = "W68 第 7 批 worktree + 分支清理脚本 + runbook". 派工 prompt 引用主指挥 SOP 文档, 写"`run_d5_dry.py --output report.json`". C-2 agent 实际跑 CLI 后发现: **`--output` 参数实际写 Markdown 文件, 不是 JSON** (主指挥 SOP 文档与 CLI 实际行为不一致).

**根因**:
1. 主指挥 SOP 文档 (`docs/w68-task-mode-paradigm-v2.md` §4 6 类文档主仓库优先) 写错了 CLI 参数格式 — 实际写代码时跑的是 Python `pathlib.Path.write_text(text, encoding='utf-8')` 而不是 `json.dump`, 但 SOP 文档描述时凭印象写 JSON.
2. C-2 agent 没主动 `--help` 核实, 信主指挥 SOP 文档.

**5 段模板 §2.3 加固**: CLI 派工必 --help 核实, 不信 main/README/docs 自述. 实操三步:
```bash
python scripts/your_cli.py --help     # Python CLI
bash scripts/your_script.sh --help    # Bash CLI
node scripts/your_cli.js --help       # Node CLI
```

### §1.5 (延申) C-1 agent 报告 — Desktop v3.2 E2E 22 SKIP 等部署

**事故**: C-1 (`test/w68-10th-batch-c1-desktop-v32-e2e-2026-07-24`) 派工 = "Desktop v3.2 E2E + 跨 PR11/12/13 集成". 派工期间 PostgreSQL 未启动, E2E 22 SKIP (`ConnectionRefusedError`). C-1 agent 报告 "E2E 22 SKIP, 等部署后补跑".

**根因**: C-1 agent 没主动 escalate "22 SKIP = 0 验证" 给主指挥. SKIP 是隐式失败, 主指挥需要知道才能拍板"先 merge 部署后补 E2E"或"等 E2E PASS 再 merge".

**5 段模板 §2.4 加固**: e2e SKIP 必报主指挥 (不静默跳过). SKIP 比例 > 10% 必须显式报告主指挥拍板.

---

## §2 5 段 prompt 模板 v2 升级 (W68 第 10 批 D-1 模板升级)

派工 prompt 模板 v2 = v1 (W68 第 9 批 D-3 拍板的 5 段: 任务背景 / 分支 / 任务描述 / 完成定义 / 输出) + 4 段加固 (§2.1-§2.4). 不推翻 v1, 叠加新纪律.

### §2.1 段 3 (任务描述) 加 alembic 主分支同步检查

**v1 模板**:
```
段 3: 任务描述
- 业务目标: <一段话>
- 技术细节: <一段话>
- 关联 plan: ~/.claude/plans/<plan>.md
```

**v2 升级**:
```
段 3: 任务描述
- 业务目标: <一段话>
- 技术细节: <一段话>
- 关联 plan: ~/.claude/plans/<plan>.md

[alembic 主分支同步检查 — 必跑, 不跑不得写 migration]
1. git fetch origin main
2. python -c "from alembic.script import ScriptDirectory; print(ScriptDirectory.from_config(Config()).get_heads())"
3. 你的 alembic migration 的 down_revision = "<最新 head>"
4. 如有冲突, 必报主指挥拍板 (不自动修 down_revision)
```

**实战**: W68 第 10 批 B-4 缺此 4 步, 默认接 065, 实际应接 069 (W68 第 9 批 hot-fix 后 069 已是 head).

### §2.2 段 4 (完成定义) 加后端依赖 check

**v1 模板**:
```
段 4: 完成定义
- 必跑: pytest tests/xxx (期望 PASS)
- 必跑: bash scripts/check_typing_imports.sh (期望 0 错误)
- 必跑: alembic heads (期望单 head)
```

**v2 升级**:
```
段 4: 完成定义
- 必跑: pytest tests/xxx (期望 PASS)
- 必跑: bash scripts/check_typing_imports.sh (期望 0 错误)
- 必跑: alembic heads (期望单 head)

[后端依赖 check — 必跑, 不跑不得写新 service / model 依赖]
1. grep -rn "<service_name>" app/    # 验证依赖存在
2. grep -rn "<model_name>" app/models/  # 验证 model 存在
3. 如服务 / model 不存在:
   - 方案 A: 写新分支实施 (合规"新功能例外" 但要在 commit body 显式标 "新功能例外: 自实施 X 因为派工前提缺失")
   - 方案 B: 报告主指挥拍板 (推荐)
```

**实战**: W68 第 10 批 B-2/B-3 缺此 3 步, B-3 agent 自行实施 B-2 + B-3 (没显式 "新功能例外" 标识, 绕过了派工协调).

### §2.3 段 3 (任务描述) 加 CLI 派工 --help 核实

**v1 模板**:
```
段 3: 任务描述
- 业务目标: <一段话>
- 技术细节: <一段话>
- 关联 plan: ~/.claude/plans/<plan>.md
```

**v2 升级**:
```
段 3: 任务描述
- 业务目标: <一段话>
- 技术细节: <一段话>
- 关联 plan: ~/.claude/plans/<plan>.md

[CLI 派工核实 — 必跑, 不跑不得在 docs/runbook 引用 CLI]
1. python scripts/your_cli.py --help
2. bash scripts/your_script.sh --help
3. node scripts/your_cli.js --help
4. 实际跑一次 `--output some_file`, 确认格式 (JSON / Markdown / YAML) 与 SOP 文档一致
```

**实战**: W68 第 10 批 C-2 缺此 4 步, 主指挥 SOP 文档写 `--output report.json` 但实际写 Markdown.

### §2.4 段 4 (完成定义) 加 e2e SKIP 必报主指挥

**v1 模板**:
```
段 4: 完成定义
- 必跑: pytest tests/xxx (期望 PASS)
- 必跑: bash scripts/check_typing_imports.sh (期望 0 错误)
- 必跑: alembic heads (期望单 head)
```

**v2 升级**:
```
段 4: 完成定义
- 必跑: pytest tests/xxx (期望 PASS)
- 必跑: bash scripts/check_typing_imports.sh (期望 0 错误)
- 必跑: alembic heads (期望单 head)

[e2e SKIP 必报主指挥 — 必跑, 不静默跳过]
1. pytest tests/e2e/xxx -v 2>&1 | tee /tmp/e2e.log
2. 统计 SKIP 比例 = SKIP 数 / 总数
3. SKIP 比例 > 10%:
   - 必须显式报告主指挥: "<N> 个 SKIP, 比例 <P>%, 原因: <缺失 PG / Docker / 网络>"
   - 主指挥拍板: 先 merge 等部署 / 等环境就绪再 merge / 改用 mock
4. SKIP 比例 < 10%:
   - 在 commit body 标 "<N> 个 SKIP (原因)" 不算违规
```

**实战**: W68 第 10 批 C-1 缺此 4 步, 22 SKIP 静默, 主指挥以为"端到端 PASS" (实际 0 验证).

### §2.5 段 2 (分支) 加 worktree base fetch

**v1 模板**:
```
段 2: 分支
- 命名: <type>/<w68-N-th-batch-{route}-{agent-id}-2026-07-24>
- worktree base: origin/main
```

**v2 升级**:
```
段 2: 分支
- 命名: <type>/<w68-N-th-batch-{route}-{agent-id}-2026-07-24>
- worktree base: origin/main

[worktree base 必 fetch 同步 — 必跑, 不基于 stale 写 alembic]
1. git fetch origin main
2. git rev-parse origin/main
3. worktree 基于 origin/main (不是本地 main, 本地 main 可能落后)
```

**实战**: W68 第 10 批 B-4 基于 stale local main (落后 5 commits), 错过 066/067/068/069 串单链, 默认接 065.

---

## §3 B 派工前提错误 5 案例 (W68 第 10 批实战)

| # | Agent | 派工前提错误 | 根因 | 影响 |
|---|-------|--------------|------|------|
| 1 | B-2 | 派工 prompt 说"已建 save_to_kb_service.py" 实际不存在 | 主指挥信 plan 状态化自报, 没 grep 真验证 | B-2 重新派工 |
| 2 | B-3 | B-2 缺失, agent 自行实施 B-2+B-3 | agent 没主动报告主指挥, 绕过派工协调 | B-3 = B-2+B-3 复合体, 不可 grep 拆解 |
| 3 | B-4 | alembic 072/073 接 065, 跳过 066/067/068/069 | 派工 prompt 没写"接 X" 也没 verify 当前 head | alembic 双头风险 (主指挥合并时才发现) |
| 4 | C-2 | `run_d5_dry.py --output` 实际写 Markdown, SOP 文档写 JSON | 主指挥 SOP 文档凭印象写, agent 没 --help 核实 | runbook 文档错误, 误导后续 agent |
| 5 | C-1 | 22 SKIP 等部署, 没主动报告主指挥 | agent 静默 SKIP, 没显式 escalate | 主指挥以为"端到端 PASS", 实际 0 验证 |

**派工前提错误类型分布**:
- **派工时主指挥没说清楚 (4/5)**: B-2/B-3/B-4/C-1 — 主指挥派工凭印象, 没真验证
- **派工时主指挥文档错 (1/5)**: C-2 — 主指挥 SOP 文档凭印象写

**核心教训**: 派工前提错误的根因 80% 是主指挥凭印象写派工 prompt (信 plan 状态化 / SOP 文档自述), 没真验证 codebase / CLI / alembic 链. v2 模板固化 5 段加固, 把"真验证" 写入派工 boilerplate.

---

## §4 失败模式 5 铁律 (永久)

W68 第 10 批 5 案例归纳的 5 条铁律, 未来派工 prompt 模板 v2 必须含:

### 铁律 1: alembic 派工必 verify main 链

**触发**: W68 第 10 批 B-4 缺 alembic 链 verify, 默认接 065, 跳过 066/067/068/069.

**派工 boilerplate** (必含在派工 prompt 段 3):
```bash
git fetch origin main
python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; \
c=Config(); c.set_main_option('script_location','alembic'); \
s=ScriptDirectory.from_config(c); print('CURRENT HEAD:', s.get_heads())"
echo "你的 alembic migration down_revision 必须等于 CURRENT HEAD (不是默认最新编号)"
```

### 铁律 2: service 派工必 verify app/ 存在

**触发**: W68 第 10 批 B-2 派工时 `app/services/save_to_kb_service.py` 不存在, 主指挥凭印象派工.

**派工 boilerplate** (必含在派工 prompt 段 4):
```bash
grep -rn "<service_name>" app/
grep -rn "<model_name>" app/models/
```

如服务 / model 不存在, 必报主指挥拍板 (方案 A 新分支 / 方案 B 主指挥补建).

### 铁律 3: CLI 派工必 --help 核实

**触发**: W68 第 10 批 C-2 SOP 文档写 `--output report.json`, 实际写 Markdown.

**派工 boilerplate** (必含在派工 prompt 段 3, 仅当任务涉及 CLI):
```bash
python scripts/your_cli.py --help
bash scripts/your_script.sh --help
node scripts/your_cli.js --help
# 实际跑一次 --output 确认格式
python scripts/your_cli.py --output /tmp/test_output && file /tmp/test_output
```

### 铁律 4: e2e SKIP 必报主指挥

**触发**: W68 第 10 批 C-1 22 SKIP 静默, 主指挥以为 PASS.

**派工 boilerplate** (必含在派工 prompt 段 4):
```bash
pytest tests/e2e/xxx -v 2>&1 | tee /tmp/e2e.log
# 统计 SKIP 比例
SKIP_COUNT=$(grep -c "SKIPPED" /tmp/e2e.log)
TOTAL=$(grep -cE "PASSED|FAILED|SKIPPED" /tmp/e2e.log)
RATIO=$(echo "scale=2; $SKIP_COUNT / $TOTAL * 100" | bc)
echo "SKIP 比例: $RATIO%"

# SKIP > 10% 必须显式报告主指挥:
if [ $(echo "$RATIO > 10" | bc) -eq 1 ]; then
    echo "ERROR: SKIP 比例 $RATIO% > 10%, 必须显式报告主指挥, 不静默"
fi
```

### 铁律 5: worktree base 必 fetch 同步

**触发**: W68 第 10 批 B-4 基于 stale local main 写 alembic, 错过 066/067/068/069.

**派工 boilerplate** (必含在派工 prompt 段 2):
```bash
git fetch origin main
git rev-parse origin/main
echo "worktree base = origin/main (不是本地 main, 本地 main 可能落后)"
```

worktree 必须基于 origin/main 创建, 不基于本地 main 创建.

---

## §5 W68 第 11 批派工如何应用 v2 模板

W68 第 11 批派工时, 主指挥已按 v2 模板应用 5 段加固:

### 5.1 C-1 派工 (alembic 重新规整)

**任务**: W68 第 11 批 C-1 = alembic 串单链重新规整 (B-4 跳级后).

**v2 模板应用**:
- **段 3**: 加 §2.1 alembic 主分支同步检查 (verify 当前 head, 不默认接 065)
- **段 2**: 加 §2.5 worktree base fetch (基于 origin/main 不是 stale local)

**预期**: 不会出现双 head, 派工时已含 verify 三步.

### 5.2 B-1/B-2/B-3 派工 (Drive v2 PR11/12/13 收口)

**任务**: W68 第 11 批 B-1/B-2/B-3 = Drive v2 PR11/12/13 收口 (C-1 22 SKIP 补跑).

**v2 模板应用**:
- **段 4**: 加 §2.2 后端依赖 check (grep -rn service 存在)
- **段 4**: 加 §2.4 e2e SKIP 必报主指挥 (SKIP > 10% 显式 escalate)
- **段 2**: 加 §2.5 worktree base fetch

**预期**: PR11/12/13 收口时不会"service 不存在 重新派工", 22 SKIP 必显式报告.

### 5.3 W69 派工应用 (留待办 backlog)

**任务**: W68 第 11 批留 W69 派工时, 应用 v2 模板全 5 段加固.

**v2 模板应用**:
- **段 3**: 加 §2.1 alembic 主分支同步检查
- **段 3**: 加 §2.3 CLI 派工 --help 核实 (留 W69 大概率涉及 plan backlog 实施, 可能有 CLI 工具)
- **段 4**: 加 §2.2 后端依赖 check
- **段 4**: 加 §2.4 e2e SKIP 必报主指挥
- **段 2**: 加 §2.5 worktree base fetch

**预期**: W69 派工时全 5 段加固, 派工前提错误率从 W68 第 10 批 4/15 (27%) → W68 第 11 批 ≤ 1/15 (7%) 显著下降.

---

## §6 派工 prompt 模板 v2 完整版 (供参考)

未来 W68 第 11+ 批派工可直接复用本模板:

```text
# W68 第 N 批 {route}-{agent-id} 派工 prompt (v2 模板)

## 段 1: 任务背景
- W68 第 N 批主题: <一段话>
- 前置批次: W68 第 N-1 批 grand closure
- 锚点范式目标: 第 X 守恒

## 段 2: 分支
- 命名: <type>/<w68-N-th-batch-{route}-{agent-id}-2026-07-24>
- worktree base: origin/main

[worktree base 必 fetch 同步 — §2.5]
1. git fetch origin main
2. git rev-parse origin/main
3. worktree 基于 origin/main (不是本地 main)

## 段 3: 任务描述
- 业务目标: <一段话>
- 技术细节: <一段话>
- 关联 plan: ~/.claude/plans/<plan>.md
- 关联 docs: docs/<topic>.md

[alembic 主分支同步检查 — §2.1 — 必跑仅当任务涉及 alembic migration]
1. git fetch origin main
2. python -c "from alembic.script import ScriptDirectory; print(ScriptDirectory.from_config(Config()).get_heads())"
3. 你的 alembic migration down_revision = "<最新 head>"
4. 有冲突必报主指挥拍板

[CLI 派工核实 — §2.3 — 必跑仅当任务涉及 CLI]
1. python scripts/your_cli.py --help
2. 实际跑一次 --output 确认格式 (JSON / Markdown / YAML) 与 SOP 一致

## 段 4: 完成定义
- 必跑: pytest tests/xxx (期望 PASS)
- 必跑: bash scripts/check_typing_imports.sh (期望 0 错误)
- 必跑: alembic heads (期望单 head, 仅当任务涉及 alembic)

[后端依赖 check — §2.2 — 必跑仅当任务涉及新 service / model]
1. grep -rn "<service_name>" app/
2. grep -rn "<model_name>" app/models/
3. 不存在: 方案 A 写新分支 / 方案 B 报主指挥拍板

[e2e SKIP 必报主指挥 — §2.4 — 必跑仅当任务涉及 e2e 测试]
1. pytest tests/e2e/xxx -v 2>&1 | tee /tmp/e2e.log
2. 统计 SKIP 比例
3. SKIP > 10%: 必须显式报告主指挥
4. SKIP < 10%: commit body 标 "<N> 个 SKIP (原因)"

## 段 5: 输出
- commit message 模板: <type>(<scope>): W68 第 N 批 {route}-{agent-id} <short-desc>
- memory 沉淀: memory/w68-route-{N}-{route}-{agent-id}-2026-07-24.md
- docs 同步 (可选): docs/<topic>-2026-07-24.md
- 锚点范式: 第 X 守恒
```

---

## §7 v2 沉淀性质

**永久派工模板 v2** (本文件, 项目级 docs).

- 后续批次如主指挥再次升级模板, 应新建 `docs/w68-10th-batch-prompt-template-v3.md` 覆盖引用本文件, 不直接改写本文件正文.
- v1 不删除 (本项目从未写过 v1 prompt 模板 — v2 是首次沉淀的 prompt 模板).
- v2 已沉淀 5 段加固 + 5 失败模式 + 5 铁律, 不再随批次迭代修订 (除非主指挥拍板).
- v2 = 基于 W68 第 10 批 5 案例实战, v3 升级预计在 W80+ 节奏.

---

## §8 关联 memory / docs

- `memory/w68-route-10-a2-alembic-hotfix-2026-07-24.md` — W68 第 9 批 hot-fix #16 (锚点范式第 121) — 本文件 §1.3 关联
- `memory/w68-route-10-a3-pr9-11-merge-2026-07-24.md` — W68 第 10 批 A-3 合并 (锚点范式第 122) — 本文件 §2.5 关联
- `memory/w68-grand-closure-9th-batch-2026-07-24.md` — W68 第 9 批 grand closure (含 B-1 PR11 path 物化) — 本文件 §1.3 关联
- `docs/w68-task-mode-paradigm-v2.md` — 选题层 v2 (5 拍板纪律 + 4 阶段流程) — 本文件派工模板叠加层
- 用户级 `multi-agent-task-orchestration-baseline.md` — 执行层锚点 (本文件对应派工模板层)
- 用户级 `orchestrator-mode-coordination-2026-07-20.md` — 5 协调铁律 (本文件派工前提纪律关联)

---

**沉淀完毕**: W68 第 10 批派工纪要 v2 (B 派工前提错误经验沉淀). 锚点范式第 142 守恒 (v2 沉淀本身不直接提升, 但为后续批次提供 5 段模板 + 5 失败模式 + 5 铁律).

**Co-Authored-By**: Claude Fable 5 <noreply@anthropic.com>
**Date**: 2026-07-24
**Version**: W68 第 10 批派工纪要 v2.0