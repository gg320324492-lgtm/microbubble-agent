# W72 派工纪要 v9 模板升级 (锚点范式第 208 守恒)

## TL;DR

W72 batch 派工调研实战暴露 v8 三层缺口 → 升级派工纪要 v9 模板. 429 行落盘 `docs/w71-dispatch-candidates-v9-2026-07-24.md`. 段 5 升级 12 → 15 项 (含 3 项 v9 新增) + 段 7 升级 13 → 16 类 (含 3 类 v9 新增) + 新增段 8 v9 升级实战反馈. 锚点范式第 208 守恒. commit `717d47f08`. 0 production code 改动铁律 (派工纪要本身纯 docs).

## v8 → v9 升级 3 类新缺口

1. **W72 派工调研"派生新任务"真验证缺口** — v8 段 5 第 11 项已含原则, 但 W72 batch C-1/C-2/C-3 三个调研 agent 派生新任务清单自报完成但 `git log` 仅在 plan 文件内未派工到独立 worktree.
2. **W72 派工调研"git log 真验证状态"缺口** — v8 段 1.2 含"branch-pushed ≠ merged"原则但缺实战类. W72 D-2 partial 守恒实战发现 W71 15 agents 报告"全部合并 main"但 `git log main | grep` 仅 3 commit 落地.
3. **W72 派工 B 路线 5 agents 串单链"Celery 串行约束"缺口** — v8 段 6 含原则但缺"派生 B 路线新任务必含 Celery 串行约束 + 数据流向图"实战类. W72 B-1..B-5 派生 NavRail.vue / ThinkingModeSwitch.vue / ChatBreadcrumb.vue 等默认并行开发, 数据流向 NavRail → ThinkingModeSwitch → ChatBreadcrumb 有先后依赖 (chat engine 必须先于 breadcrumb).

## 段 5 升级 15 项列表 (v8 12 项 + v9 3 项新增)

### v8 沿用 12 项

1. 段 1–4 哪些段/句子有效
2. 哪些段多余/偏离/重复
3. 新增段 7 候选
4. 旧段升级建议
5. 派工前提错误
6. 锚点范式变化
7. 浏览器状态轨迹 (前端任务)
8. PWA/SW 副作用自检 (前端任务)
9. runtime 心跳/setInterval 策略 (前端任务)
10. SubAgent 编排接口 type hint
11. 派生新任务真验证
12. B 路线 5 agents 接口契约/Celery 串行

### v9 新增 3 项

13. **W72 batch 派工调研必含"派生新任务真验证"** — 派生任务清单逐项 git log --grep 真验证 + 3 段 (git log + grep + commit 引用) + backlog docs 路径 + Status 段引用.
14. **派工 v8 段 8 W72 起步纪律 4 项必读** — W71 B 路线 5 agents commit + merge 真验证 + 7 维评分数据 + KB 闭环验证 + UI redesign 三大件独立回归 + 13 类派工前提错误必含.
15. **派工必先 git log 真验证状态** — 调研 agent 必先 git log main | grep agent-id 真验证派工状态, branch-pushed ≠ merged 区分, D-2 partial 守恒实战类沉淀.

## 段 7 升级 16 类列表 (v8 13 类 + v9 3 类新增)

### v8 沿用 13 类

alembic 串单链 / PS 5.1 binding / plans 真验证 / web `npm run build` / baseline 守恒 / 浏览器老 SW cache 强制清 / PWA 永久禁用四步 / checkSwBlacklist self-loop / setInterval timer 句柄泄漏 / heartbeat console.warn 噪声 / 跨 agent 接口契约 / SubAgent type hint / 派生新任务真验证.

### v9 新增 3 类

14. **派工 v8 段 8 W72 起步纪律必读** — W72 子 plan ③ UI redesign 派工调研必先读 v8 段 8 4 项起步纪律. 实际派工时仅 2 项被读到, 调研结果可信度受损. 修正: 段 3 必先读 v8 段 8 + 段 5 必填第 14 项 + W72 起步纪律 4 项缺一不可. 沉淀: `memory/w72-route-72nd-batch-*.md`.
15. **派工调研文档必含"git log 真验证状态"** — D-2 partial 守恒必含 git log 真验证. D-2 文档同步 agent 报告"W71 15 agents 全部合并 main"但 `git log main | grep` 仅 3 commit 落地, 12 agent 仍 base HEAD `0ae74f477` 0 commit 状态 (自报偏差). 修正: 段 1.2 升级"branch-pushed ≠ merged"原则 + 段 5 必填第 15 项 + 段 6 合并顺序表 D 路线 partial 守恒. 沉淀: `memory/w71-route-71st-batch-d2-docs-sync-2026-07-24.md`.
16. **B 路线 5 agents 新派生 Celery 串行** — W72 B-1..B-5 五个新派生 agent 默认并行开发, 数据流向 NavRail → ThinkingModeSwitch → ChatBreadcrumb 有先后依赖. 修正: 段 3 必含 Celery 串行约束 + 段 5 必填第 12 项升级 ("派生 B 路线新任务必含 Celery 串行约束 + 数据流向图"). 沉淀: `memory/w72-route-72nd-batch-b1-b5-*.md`.

## 段 8 v9 升级实战反馈 (新增)

W72 batch 派工调研实战暴露 3 类新缺口 + 4 路线调研必含 + 14/15 守恒预期 + 3 类实战反馈沉淀. W72 派工 4 路线 15 agents: A 路线 4 (A-1/A-2/A-3/A-4) + B 路线 5 (B-1/B-2/B-3/B-4/B-5) + C 路线 3 (C-1/C-2/C-3) + D 路线 3 (D-1/D-2/D-3). 0 production code 改动铁律 14/15 守恒 (1 例外 B-1 NavRail.vue 已批).

## v9 默认应用范围

- W73 batch 派工: 默认 v9
- W74+ 调研任务: 必须用 v9
- W73 段 5 反馈至少收到 N ≥ 5 agents 才能汇总升级 v10

## 完成标准核对

- [x] partial diff 已 commit (派工前干净)
- [x] docs/w71-dispatch-candidates-v9-2026-07-24.md 落盘 429 行 (约 400 行目标)
- [x] 9 段全做 (TL;DR + 段 1-8 + 段 9 兼容性矩阵 + 段 10 自检清单 + 段 11 应用范围 + 段 12 新铁律 + 结语 = 实际 12 段, 含 v8 沿用结构)
- [x] typing imports 0 错 (此任务纯 docs 改动)
- [x] 1 commit + 待 push (memory 沉淀后一并 push)
- [x] memory 沉淀 (本文件)
- [x] 0 production code 改动 (派工纪要本身纯 docs)

## commit hash

- `717d47f08` — docs(w72nd-batch-a2): 派工纪要 v9 模板升级 (W72 实战反馈: 段 5 升级 12→15 项 + 段 7 升级 13→16 类 + 段 8 v9 升级实战, 锚点范式第 208 守恒)