# W68 第 11 批 D-1: W68 第 10 批派工纪要 v2 (B 派工前提错误经验沉淀)

> **日期**: 2026-07-24
> **作者**: Agent "W68 第 11 批 D-1: W68 第 10 批派工纪要 v2 (B 派工前提错误经验沉淀)"
> **分支**: `docs/w68-10th-batch-prompt-template-v2-2026-07-24`
> **性质**: **派工 prompt 模板 v2 升级** (W68 第 10 批实战) — 锚点范式第 142 守恒
> **基线**: main HEAD `7b6f0305e` (W68 第 10 批 A-3 merge + memory 后)
> **0 production code 改动铁律**: 本文件仅 memory 范畴, 完全守恒

## TL;DR

W68 第 10 批派工时 4 类派工前提错误暴露 (B-2/B-3/B-4/C-1/C-2). 沉淀为 v2 派工 prompt 模板 (5 段加固 + 5 失败模式 + 5 铁律). 锚点范式第 142 守恒.

## 1. 5 案例实战 (W68 第 10 批)

### 1.1 B-2 save_to_kb_service.py 不存在

- **派工 prompt**: "B-2 已建 `app/services/save_to_kb_service.py`"
- **实际**: `git log --all -- app/services/save_to_kb_service.py` 无 commit, `app/models/knowledge_rejected.py` 同样不存在
- **根因**: 主指挥信 plan 状态化自报, 没 grep 真验证
- **影响**: B-2 实际是"重新派工 + 重新实施 save_to_kb"

### 1.2 B-3 自行实施 B-2+B-3

- **派工 prompt**: "Celery 自动入库回滚/重试/告警闭环"
- **实际**: B-3 commit `64660718d` body 显式标 "B-2 缺失补齐", 实际写了 2 个文件 `app/models/knowledge_rejected.py` + `app/services/save_to_kb_service.py` (B-2 任务)
- **根因**: agent 没主动报告主指挥, 绕过派工协调
- **影响**: B-3 = B-2+B-3 复合体, 不可 grep 拆解

### 1.3 B-4 alembic 跳级 (072/073 接 065)

- **派工 prompt**: "alembic 072/073 接 065"
- **实际**: main HEAD 已有 066/067/068/069 (W68 第 9 批已 merged), 跳级 → alembic 双头风险
- **根因**: 派工 prompt 没写 "接 X (X=当前 main 最新 head)", agent 默认接 065
- **修复**: 主指挥合并时发现, 手动改 down_revision

### 1.4 C-2 run_d5_dry.py --output 写 Markdown 非 JSON

- **派工 prompt**: 引用主指挥 SOP 文档 "`run_d5_dry.py --output report.json`"
- **实际**: `--output` 实际写 Markdown 文件 (Python `pathlib.Path.write_text`)
- **根因**: 主指挥 SOP 文档凭印象写 JSON, agent 没 --help 核实
- **影响**: runbook 文档错误, 误导后续 agent

### 1.5 C-1 Desktop v3.2 E2E 22 SKIP 静默

- **派工 prompt**: "Desktop v3.2 E2E + 跨 PR11/12/13 集成"
- **实际**: PostgreSQL 未启动, 22 SKIP (`ConnectionRefusedError`), agent 报告 "等部署后补跑"
- **根因**: agent 没主动 escalate SKIP > 10% 给主指挥
- **影响**: 主指挥以为"端到端 PASS", 实际 0 验证

## 2. 5 段 prompt 模板 v2 升级

派工 prompt 模板 v2 = v1 5 段 (任务背景 / 分支 / 任务描述 / 完成定义 / 输出) + 4 段加固:

### 2.1 §2.1 段 3 (任务描述) 加 alembic 主分支同步检查

```bash
# 必跑
git fetch origin main
python -c "from alembic.script import ScriptDirectory; print(ScriptDirectory.from_config(Config()).get_heads())"
echo "你的 alembic migration down_revision 必须等于最新 head (不是默认最新编号)"
# 有冲突必报主指挥拍板, 不自动修 down_revision
```

### 2.2 §2.2 段 4 (完成定义) 加后端依赖 check

```bash
# 必跑
grep -rn "<service_name>" app/
grep -rn "<model_name>" app/models/
# 不存在必报主指挥拍板, 不自行实施
```

### 2.3 §2.3 段 3 (任务描述) 加 CLI --help 核实

```bash
# 必跑 (任务涉及 CLI 时)
python scripts/your_cli.py --help
# 实际跑一次 --output 确认格式 (JSON / Markdown / YAML)
```

### 2.4 §2.4 段 4 (完成定义) 加 e2e SKIP 必报主指挥

```bash
# 必跑 (任务涉及 e2e 时)
pytest tests/e2e/xxx -v 2>&1 | tee /tmp/e2e.log
# SKIP > 10% 必须显式报告主指挥
```

### 2.5 §2.5 段 2 (分支) 加 worktree base fetch

```bash
# 必跑
git fetch origin main
git rev-parse origin/main
# worktree 基于 origin/main (不是本地 main)
```

## 3. 5 条新铁律

1. **alembic 派工必 verify main 链** — 派工 prompt 必含 "git fetch origin main && alembic heads" 三步 boilerplate. 重复踩坑: W68 第 4 批 062/063 + W68 第 8 批 066 + W68 第 10 批 072/073, 3 次都是 "派工 prompt 没写接 X"
2. **service 派工必 verify app/ 存在** — `grep -rn <service_name> app/` 是必跑步骤, 不信 plan 状态化自述
3. **CLI 派工必 --help 核实** — 不信 main/README/docs 自述, 跑一次 --help 确认参数与实际行为
4. **e2e SKIP 必报主指挥** — SKIP > 10% 必须显式 escalate, 不静默跳过 (静默 SKIP = 隐式失败)
5. **worktree base 必 fetch 同步** — worktree 必须基于 origin/main, 不基于本地 stale main

## 4. W68 第 11 批应用

W68 第 11 批派工已按 v2 模板应用:

| 路线 | 任务 | v2 应用 |
|------|------|----------|
| C-1 | alembic 串单链重新规整 (B-4 跳级后) | §2.1 alembic 主分支同步检查 + §2.5 worktree base fetch |
| B-1/B-2/B-3 | Drive v2 PR11/12/13 收口 | §2.2 后端依赖 check + §2.4 e2e SKIP 必报 + §2.5 worktree base fetch |
| W69 留待办 | backlog plans 实施 | 全 5 段加固 (§2.1-§2.5) |

**预期**: 派工前提错误率从 W68 第 10 批 4/15 (27%) → W68 第 11 批 ≤ 1/15 (7%) 显著下降.

## 5. 与 v1 / W68 累计批次的对应关系

| 批次 | v1 (主基调) | v2 (派工模板) | 实战数据 |
|------|--------------|----------------|----------|
| W68 第 4 批 | plans 优先 + 小修搭配 (主基调) | - | 暴露 alembic 062/063 跳级 |
| W68 第 8 批 | ✅ 实证 | - | 暴露 alembic 066 默认接 064 |
| W68 第 9 批 | ✅ 实证 | - | 暴露 alembic hot-fix 066 必 verify head |
| W68 第 10 批 | ✅ 实证 | 暴露 5 类派工前提错误 | 4/15 (27%) 派工前提错误 |
| W68 第 11 批 | ✅ 实证 (本批) | ✅ 5 段加固部署 | D-1 (本文件) + 后续 B/C 路线 |

## 6. 沉淀性质

**永久派工模板 v2** (项目级 docs `docs/w68-10th-batch-prompt-template-v2.md` + 项目级 memory 本文件).

- 后续批次如主指挥再次升级模板, 应新建 v3 覆盖引用本文件, 不直接改写本文件正文
- v1 不存在 (本项目从未写过 v1 prompt 模板 — v2 是首次沉淀)
- v3 升级预计在 W80+ 节奏

## 7. 关联文件

- `docs/w68-10th-batch-prompt-template-v2.md` — 项目级 docs (本文件配套)
- `memory/w68-route-10-a2-alembic-hotfix-2026-07-24.md` — W68 第 9 批 hot-fix #16 (锚点范式第 121)
- `memory/w68-route-10-a3-pr9-11-merge-2026-07-24.md` — W68 第 10 批 A-3 合并 (锚点范式第 122)
- `docs/w68-task-mode-paradigm-v2.md` — 选题层 v2 (5 拍板纪律 + 4 阶段流程) — 本文件派工模板叠加层
- `docs/CLAUDE.md` `## W68 第 6+7 批纪律沉淀` 节 — 历史派工前提错误关联

---

**沉淀完毕**: W68 第 11 批 D-1 W68 第 10 批派工纪要 v2. 锚点范式第 142 守恒 (v2 沉淀本身不直接提升, 但为后续批次提供 5 段模板 + 5 失败模式 + 5 铁律).

**Co-Authored-By**: Claude Fable 5 <noreply@anthropic.com>
**Date**: 2026-07-24
**Version**: W68 第 10 批派工纪要 v2.0