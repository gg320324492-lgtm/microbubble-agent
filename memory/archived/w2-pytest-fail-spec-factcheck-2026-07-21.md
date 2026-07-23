---
name: w2-pytest-fail-spec-factcheck-2026-07-21
description: "W2 spec fact-check fail 诚实记录 (W28 报告不存在, 9 文件 baseline 71+7 稳定, 选项 A 接受现状)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 0f277dd1-0a27-4a11-b320-da966057abae
  modified: 2026-07-20T18:53:20.872Z
---

# W2 pytest fail spec fact-check (2026-07-21)

## TL;DR

🎯 **W2 spec 假设的 W28 报告不存在, 9 文件 baseline 71+7 稳定, 0 collection error** — 主指挥决策选项 A (接受现状, 不发起新 PR), 跟 W19 选项 A 一致。

**Why**: W2 spec 凭印象假设 "W28 报告 (待 W1 派活后) 给出 26 fail + 11 error", 实际 W26/W27/W28 commits 都不存在, 最近 worker 是 W25 (commit `b26632e2`)。

**How to apply**: 未来 session 派活前必须 `git log` 验证前置条件, 避免凭印象假设。

## W2 spec fact-check 详情

### W2 spec 假设 (凭印象)

- "W28 报告 (待 W1 派活后) 给出 26 fail + 11 error 详细分类"
- "P0 #1 = pytest 收集错误 11 errors"
- "A 类 test_orm_edge + B 类 test_migration_stale + C 类 test_endpoint_404 + D 类 test_other"

### 事实核查 (W2 worker 主动)

- ❌ **W28 报告不存在** — `ls memory/w28*` 0 命中
- ❌ **W26/W27/W28 commits 都不存在** — 最近 worker 是 W25 (commit `b26632e2`, 2026-07-21)
- ❌ **26 fail + 11 error 不存在** — 9 文件 baseline 71+7 0 fail, pytest collect-only 950 tests collected 0 collection error
- ✅ **9 文件 baseline 71+7 稳定** — 主指挥亲自跑 `71 passed, 7 skipped, 14 warnings in 2.55s` (跟 W2-W25 历史 baseline 一致)

### 3 选项拍板

| 选项 | 决策 | 适用场景 |
|---|---|---|
| **A (推荐)** | 接受当前状态, 不发起 W2 修 P0 #1 任务 | 高产出日 + 系统稳定 (跟 W19 选项 A 一致) |
| B | 派 W1 → W26 → W27 → W28 完整 4 worker 链 (4-8 人天) | 资源充足 + 必须修 |
| C | 主指挥直接给 W28 报告内容, W2 立即修 (1 人天) | 主指挥已人工汇总 |

## 3 新铁律 (W2 spec fact-check fail 沉淀)

1. **派活前必须 `git log` 验证前置条件** — W2 spec 凭印象假设 W28 报告存在, 实际不存在。 任何 spec 提到"前置报告"必须先 `ls memory/<name>*` + `git log --grep="<keyword>"` 验证
2. **"9 文件 baseline 71+7" 是锚点金标准** — 9 文件涵盖核心 backend 流程 (transcript buffer / orphan cleanup / 录音 3 件 / chat history tasks / chat share cleanup / kb dedup), 不在这 9 文件的就是 pytest 全量范围
3. **spec fact-check fail 诚实记录** — 不擅自编造或补全前置报告, 立即上报主指挥拍板 (跟 W2 spec 一致)

## 累计 baseline 状态 (W2 spec fact-check fail 后)

- 9 文件 baseline 71+7 稳定 (主指挥已 7 次 baseline 收口)
- pytest collect-only 950 tests collected 0 collection error
- pytest 全量跑 (SKIP_DB_SETUP=1) 包含 baseline + 其他测试, 真实 fail 数量主指挥未确认 (但 9 文件 baseline 0 fail)
- W26/W27/W28 任务未执行 (W2 spec 提到的 4 worker 链)
- 57 commit + 18 memory + 79 任务 状态不变 (W2 0 改动)

## 未来 session 警惕

任何 spec 提到 "W{N} 报告" / "W{N} 派活" / "W{N} commit" 都要先验证:
```bash
git log --oneline | grep -E "W{N}|<keyword>"
ls memory/w{N}*  # 或 docs/w{N}*
```

不验证 = 凭印象假设 = W2 spec fact-check fail 重复。

## 相关 memory

- `multi-agent-task-orchestration-baseline.md` — 锚点范式
- `orchestrator-mode-coordination-2026-07-20.md` — 5 协调铁律 (铁律 1: 总指挥 ≠ 总执行)
- `w19-future-pr-decision-2026-07-21.md` — 选项 A 拍板先例
- `w22-8-baseline-closure-2026-07-21.md` — 9 文件 baseline 锚点
- **w2-pytest-fail-spec-factcheck-2026-07-21.md** — 本 fact-check fail 记录 (本 commit)