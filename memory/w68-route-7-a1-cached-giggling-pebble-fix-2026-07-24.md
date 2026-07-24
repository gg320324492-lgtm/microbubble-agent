# W68 第 7 批 A-1: 修复 cached-giggling-pebble 真 MISMATCH (2026-07-24)

> 锚点范式第 75 守恒。W68 第 6 批 Plan 深度审计 #1 发现 Plan Status 段挂错 + P0 改动被反向重写未留文档。
> 主指挥 W68 第 7 批拍板接受现状，仅修 docs + plan 状态（0 production code 改动铁律维持）。

## 任务背景

Plan `cached-giggling-pebble.md`（"转录记录 Tab 加载慢优化"）核心建议
P0 改动 1：**删除** `MeetingDetailView.vue:autoPolishIfNeeded()`（跟 P2 删 setTimeout 一组）。

**真 MISMATCH 时间线**：
- commit `9986eb67d`（2026-06-26）— 确实按 Plan **删除** `autoPolishIfNeeded`
- commit `bb18c9708`（2026-07-08）— **反向重写**，强化版 autoPolishIfNeeded（76 行限流版）重新加入
- 当前 `web/src/views/MeetingDetailView.vue:564` `autoPolishIfNeeded` 76 行实现**完整存在**
- Plan Status 段却标 `COMPLETED`，且挂错 commit hash（写"3rd-wave Agent 4: knowledge 提取"，
  与本 plan 主题完全无关）→ 实际 **PARTIAL_REGRESSION**

## 主指挥拍板（本任务前提）

接受当前强化版 `autoPolishIfNeeded` 存在，**不删除**。
根因：DB `transcript_polished` 字段实际未完全回填（大量历史会议 `IS NULL`），
仍需前端 polish 限流保护。但**修正 plan Status 段 + 加文档说明**。

## 交付物（3 文件）

1. **修改** `C:/Users/pc/.claude/plans/cached-giggling-pebble.md` 顶部 Status 段：
   - 旧: `**COMPLETED**: 3rd-wave Agent 4: knowledge 提取`（挂错 hash）
   - 新: `**PARTIAL_REGRESSION (USER_APPROVED)**: Plan P0 改动 1 (删除 autoPolishIfNeeded)
     被反向重写为强化限流版 (commit bb18c9708, 2026-07-08). 用户决策保留强化版
     (DB transcript_polished 字段未完全回填, 限流保护仍必要). P0 改动 2-3 + P1 + P2 (3/4) 完成.
     主指挥 W68 第 7 批拍板接受现状.`
   - 加指向 `docs/meeting-auto-polish-rationale.md` 的链接

2. **新文档** `docs/meeting-auto-polish-rationale.md`（~150 行，5 节）：
   - 第 1 节 Plan 原始设计（删除的 4 理由）
   - 第 2 节 反向重写原因（DB `transcript_polished` 完整性检查 SQL）
   - 第 3 节 强化版设计（chunked 200 + concurrency 3 + 500+ 跳过）
   - 第 4 节 决策日志（3 行 commit 表 + 主指挥拍板理由）
   - 第 5 节 未来优化（全量回填后可真删除）

3. **本 memory**

## 3 条新铁律

1. **Status 段必须描述真实实施状态** — 不能挂错 commit hash。
   本例 Status 写"3rd-wave Agent 4: knowledge 提取"与 plan 主题（会议转录 tab 优化）
   完全无关，属复制粘贴污染。Plan Status 修改前必须 `git log` 验证 hash 对应正确改动。

2. **Plan P0 改动被反向重写必须留文档说明** — 不能静默消失。
   `autoPolishIfNeeded` 被删（9986eb67d）后又重新加入（bb18c9708），
   两次改动跨 12 天、无交叉引用，导致 Plan 审计时误判 COMPLETED。
   反向重写必须在 docs 留决策链（本例 `docs/meeting-auto-polish-rationale.md`）。

3. **强化版实现 vs 原始建议不一致时主指挥拍板** — 留决策记录。
   当实际实现（强化限流版）与 Plan 原始建议（删除）冲突时，
   不能由 agent 擅自二选一，必须主指挥拍板并在 docs 决策日志 + memory 双沉淀。
   本例接受强化版（前提：DB 字段未回填），未来全量回填后可回归 Plan 原始设计。

## 纪律守恒

- 0 production code 改动铁律维持（仅 plan 头部 + 新 docs + memory = 3 文件）
- W19 选项 A 维持
- 锚点范式第 75 守恒
- 分支 `chore/w68-7th-batch-a1-cached-giggling-pebble-fix-2026-07-24`，不 merge（主指挥来）
