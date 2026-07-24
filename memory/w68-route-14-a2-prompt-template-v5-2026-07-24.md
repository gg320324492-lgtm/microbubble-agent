# W68 Route 14 A-2：Prompt Template v5

日期：2026-07-24
范围：仅 docs + memory；0 production code 改动。
锚点范式：第 170 守恒。

## 交付与背景

本路线新增 `docs/w68-dispatch-candidates-v5-2026-07-24.md`，将 W68 第 13 批派工纪要 v4 升级为 v5：保留 v4 全部 5 段门禁，仅在段 5 之后追加两段——段 5 经验反馈循环 + 段 6 主指挥合并顺序表。v5 对 v4 是纯增量，不破坏既有 v1/v2/v3/v4 派工的可追溯性。

## v4→v5 增量结构

| 段 | v4 内容 | v5 增量 |
|---|---|---|
| 段 1 | 角色、范围、不变量 | 不变 |
| 段 2 | 交付物、操作边界 | 不变 |
| 段 3 | 任务描述、前置验证、风险门禁（含 Alembic 双头 + plans 真验证） | 不变 |
| 段 4 | 完成定义、测试、PS 5.1 binding | 不变 |
| 段 5 | 回传格式、commit、交接 | **改名为"经验反馈循环"**：agent 必填"有效段 / 多余段 / 偏离段"反馈 |
| 段 6 | （无） | **新增"主指挥合并顺序表"**：派工时附 Step 1-N 合并链 + alembic 串单链位置 |

v4 段 5 原 "回传格式" 内容并入段 5 的"反馈"前缀；交接 + co-author trailer 仍位于段 5 末尾（保持 v4 兼容）。

## 6 条新铁律

1. **段 5 反馈必填**——agent 完工回传必须含段 5（"有效段 / 多余段 / 偏离段"三类至少各 1 条建议），否则视为"完工未达标"，主指挥合并时不视为有效交付。
2. **段 6 合并顺序表必含 alembic 串单链位置**——派工消息段 6 的"串单链位置"列必须写明 `base=<上游 revision> down_revision=<上游 revision>`，且 `base` 必须等于同表"前置依赖"列指向的 commit 的 alembic revision；agent 不得擅自修改。
3. **v5 默认应用从 W68 第 15 批开始**——任何 W68 第 15 批及以后的派工必须使用 v5；W71 派工也默认 v5。
4. **段 6 表格对单 agent 派工仍强制**——即使本批只有 1 个 agent 派工，段 6 仍必须含一张单行 Step 1 表格（"串单链位置"写"单 agent，base=当前 HEAD"），避免 agent 误以为可以自动 merge。
5. **段 5 反馈汇总后必升级 v6**——主指挥在每批 grand closure 时汇总 N agents 反馈，写入 docs + memory 永久锚点；下一批若新增 v6 段则派工升级到 v6。
6. **反馈循环与顺序表互不替代**——段 5 是"对模板本身的反馈"，段 6 是"对派工具体任务的执行顺序"；二者互不替代，缺一不可。

## v4 兼容矩阵

| 版本 | 段数 | 新增能力 | 适用 |
|---|---|---|---|
| v1 | 3 | 基本角色、范围、交付物 | 历史单 agent 小任务 |
| v2 | 4 | 增加测试、证据、分支边界 | 一般文档/前端任务 |
| v3 | 5 | 五段结构雏形、交接和回滚 | W68 第 12 批 |
| v4 | 5 | 完整五段、前置门禁、证据闭环（Alembic / PS 5.1 / plans 真验证） | W68 第 13 批 + W71 |
| v5 | 6 | v4 + 段 5 反馈 + 段 6 合并顺序 | W68 第 14 批 + W71+ |

v4 → v5 升级仅追加段落，不改原文。

## W68 第 14 批 15 agents 应用 v5（反馈采集阶段）

W68 第 14 批 15 agents（A-1 ~ A-4 + B-1 ~ B-3 + C-1 ~ C-4 + D-1 ~ D-3）在派工时已应用 v5 段 5 + 段 6。本任务先把模板沉淀进 docs / memory；本批反馈采集由 W68 第 14 批 grand closure 收集，汇总后写入 v6 候选。

## 验证与交接

本任务应验证 `docs/w68-dispatch-candidates-v5-2026-07-24.md` 文件存在、关键短语齐全、Markdown diff 无空白错误。`memory/w68-route-14-a2-prompt-template-v5-2026-07-24.md` 文件存在、字段齐全。

不得修改 production code，不动 `docs/w68-13th-batch-prompt-template-v4.md` 与 `memory/w68-route-13-d1-prompt-template-v4-2026-07-24.md`（保持 v4 历史不被覆盖）。

提交信息末尾必须包含 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`。

D7 baseline 守恒验证：`REDIS_URL=redis://localhost:6379/0 bash scripts/ci_qa_bench_baseline.sh` → 71 PASS + 7 SKIP（已实现 Redis 通过 docker run -d 临时启动）。

主指挥合并后需验证远端 ref、两个文件存在、单一 alembic head（本次不涉及迁移）。
