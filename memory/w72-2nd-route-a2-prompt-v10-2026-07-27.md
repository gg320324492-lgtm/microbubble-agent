# W72 派工纪要 v10 模板升级 (锚点范式第 223 守恒预测)

## TL;DR

W72 第 1 批实战 11 commit 反馈 → 升级派工纪要 v9 到 v10 模板. 514 行落盘 `docs/w72-prompt-paradigm-v10-2026-07-27.md`. 段 5 升级 15 → 18 项 (含 3 项 v10 新增) + 段 6 升级 13 → 14 段 (含 1 段 v10 新增) + 段 7 升级 16 → 19 类 (含 3 类 v10 新增) + 段 8 升级 4 → 6 项 (含 2 项 v10 新增) + 新增段 9 W72 第 1 批 11 commit 锚点范式数字纪律. 锚点范式 W72 第 1 批 220 → W72 第 2 批 A-2 223 守恒 (+3). commit hash 待 push. 0 production code 改动铁律 (派工纪要本身纯 docs).

## v9 → v10 升级 4 类新缺口 (W72 第 1 批 11 commit 实战)

1. **SubAgent 编排 type hint 实战缺口** — v9 段 5 第 10 项已含原则但缺"跨 worktree 接口契约必走 docs/w72-b-route-interfaces.md"实战类. W72 第 1 批 B-2 commit `228aa9de3` (ThinkingModeSwitch + ChatBreadcrumb + useUiStore v-model) 实战暴露: TypeScript interface 缺 `@deprecated` 警告导致老接口未明示弃用, 跨 worktree 接口契约无集中文档.

2. **派工 4 阶段流程 v2 缺口** — v9 段 1.1 沿用 v8 4 阶段流程 (plan list → 拍板 → 实施 → 收口), 但 W72 第 1 批 C-1 commit `08df36e80` (容器镜像 rebuild 调研) + C-2 commit `a78967661` (商业化 24 人月季度排期调研) + C-3 commit `f1947d3c7` (ppt-word 5 缺口调研) 实战暴露"派生新任务"环节未独立显式.

3. **0 production code 改动铁律 14/15 守恒预期表缺口** — v9 段 8 含"14/15 守恒预期"原则但缺独立表格. W72 第 1 批 D-2 commit `02b7b4dcb` (6 类文档同步) 实战发现: B-1 NavRail.vue + B-3 ChatViewSSE.vue + B-5 桌面 ChatViewSSE 顶栏 6 主题 dark mode 共 3 例外已批, 但仍需明确"哪些算例外 / 例外上限 1/N 守恒".

4. **W73/W74 派工顺序表缺口** — v9 段 8 含"4 路线调研必含"但缺"W73/W74 派工顺序表". W72 第 1 批 C-3 commit `f1947d3c7` (ppt-word 5 缺口) 实战发现: 缺口 5 含 PR2/PR3/PR5/PR7 + 缺口 5 命名错位, 必派工 W73/W74 顺序表 (先 W73 调研 → 后 W74 实施), 但 v9 无独立 W73/W74 派工顺序段.

## 段 5 升级 18 项列表 (v9 15 项 + v10 3 项新增)

### v9 沿用 15 项

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
13. W72 batch 派工调研必含"派生新任务真验证"
14. 派工 v8 段 8 W72 起步纪律 4 项必读
15. 派工必先 git log 真验证状态

### v10 新增 3 项 (W72 第 1 批实战 11 commit 反馈)

16. **SubAgent 编排 type hint 实战必填** — 跨 worktree 接口契约必走 docs/w72-b-route-interfaces.md + TypeScript interface 必带 @deprecated 警告 (W72 B-2 commit `228aa9de3` 实战暴露) + 编译产物 grep @deprecated ≥ 1 + 新增字段 keyword-only + Optional 默认 None.

17. **派工 4 阶段流程 v2 必填** — 派生新任务环节必独立显式 (含派生任务清单逐项 git log 真验证 + 派生任务与原 plan 串链关系 + W73/W74 派工顺序表) + 调研 agent 必在段 5 反馈里必填 4 阶段流程 v2 实操记录 + 0 production code 改动铁律 14/15 守恒预期表每条例外明示 (commit hash + 文件 + 例外理由).

18. **W73/W74 派工顺序表 + commit message 锚点范式数字必填** — 调研必含 W73/W74 派工顺序表 (先 W73 调研 → 后 W74 实施) + commit message 必含锚点范式数字 + W72 第 1 批实战引用 (commit hash 或具体路线 B-1/B-2/B-3/B-4/B-5) + 11 commit 实战模板复用 + 调研类 commit 必含"派生新任务" + "W73/W74 派工顺序"段.

## 段 6 升级 14 段列表 (v9 13 段 + v10 1 段新增)

### v9 沿用 13 段合并顺序表

1. 起点 (alembic 077 + main HEAD) → 2. alembic 066-069 rebase 串单链 → 3. 主指挥部署收口 → 4. 派工纪要 v8 → v9 → 5. plans 真验证调研 → 6. grand closure memory 预期 → 7. B-1..B-5 Celery 串行 → 8. C-1..C-3 调研沉淀 → 9. W72 B-1..B-5 派生 UI 三大件 → 10. C-1..C-3 派生调研 → 11. D-1 派工 v10 反馈 → 12. D-3 锚点范式守恒 → 13. D-2 6 类文档同步

### v10 新增 1 段

14. **商业化 B-5 必先于 D-2 doc sync** — 商业化 B-5 docker base + 商业化版调研 必先 docker commit + push + webhook 部署 + 商业化版 smoke test 全通过后才启动 B-5 调研代码 + 必先于 D-2 doc sync 合并 (防止商业化版调研未跑全就先同步文档).

## 段 7 升级 19 类列表 (v9 16 类 + v10 3 类新增)

### v9 沿用 16 类

alembic 串单链 / PS 5.1 binding / plans 真验证 / web `npm run build` / baseline 守恒 / 浏览器老 SW cache 强制清 / PWA 永久禁用四步 / checkSwBlacklist self-loop / setInterval timer 句柄泄漏 / heartbeat console.warn 噪声 / 跨 agent 接口契约 / SubAgent type hint / 派生新任务真验证 / 派工 v8 段 8 W72 起步纪律必读 / 派工调研文档必含"git log 真验证状态" / B 路线 5 agents 新派生 Celery 串行

### v10 新增 3 类 (W72 第 1 批 11 commit 实战反馈)

17. **命名错位 plan 必重定义"差量缺口"** — 场景: W72 第 1 批 C-3 commit `f1947d3c7` (ppt-word 5 缺口调研) 实战暴露 ppt-word 5 缺口实际是 PR2 sharing + PR3 comment v2 + PR5 trash + PR7 request + 缺口 5, 命名"5 缺口"与实际内容不符 (缺口 5 命名错位). 修正: 段 1 角色范围必含"plan 标题 vs 实际内容是否一致"自检 + 段 3 plans grep 必含命名 vs 实际 diff 段 + 段 5 第 16 项必填.

18. **`vite build` 直跑必坏 PWA** — 场景: CLAUDE.md 永久锚点 2026-07-11 PWA manifest 410 回归 (commit `59187ce8` cascade folder delete 引入, `5d2bcdfd` 修复). 假设: web 改动 = `vite build` 直跑 = 必坏 PWA (manifest.webmanifest 保持 unhashed → nginx `location = /manifest.webmanifest { return 410; }` 拦截 → 浏览器 `Manifest fetch failed, code 410` → PWA install 失败). 修正: 段 4 完成定义必显式"web 改动必须 `npm run build` (唯一合法命令), 禁止 `vite build` 直跑" + 段 5 第 17 项必填.

19. **commit message 必含锚点范式数字** — 场景: W72 第 1 批 11 commit 全部 commit message 含锚点范式数字 (如 commit `228aa9de3` "锚点范式第 212 守恒"、commit `f1947d3c7` "锚点范式第 218 守恒"), 但 v9 模板未明示"commit message 必含锚点范式数字 + W72 第 1 批实战引用". 修正: 段 4 完成定义加 commit message 锚点范式数字必填 + 段 5 第 18 项必填 + 段 9 W72 第 1 批实战 11 commit 锚点范式数字纪律.

## 段 8 升级 6 项列表 (v9 4 项 + v10 2 项新增)

### v9 沿用 4 项起步纪律

1. W71 B 路线 5 agents commit + merge 真验证
2. W71 子 plan ② 7 维评分数据 + KB 闭环验证
3. W72 子 plan ③ UI redesign 三大件独立回归
4. 13 类派工前提错误必含

### v10 新增 2 项

5. **商业化 docker base 起步必先** — 商业化 B-5 (docker base 商业化版 + 商业化版调研) 起步必先 docker base 商业化版 (不算 0 production code 改动, 因为 docker base 是新业务模块容器镜像 rebuild, 不破坏老任务/会议/知识库路径). 纪律: 商业化 B-5 必先 docker commit + push + webhook 部署 + 商业化版镜像 pull + 商业化版 smoke test 全通过后才启动 B-5 调研代码. 沉淀: memory/w72-2nd-route-c2-monetization-docker-base-2026-07-27.md (待沉淀).

6. **gap analysis 文档必先恢复/重建** — 缺口 5 教训 (ppt-word PR2/PR3/PR5/PR7 + 缺口 5 命名错位) 暴露 W72 第 1 批前 gap analysis 文档未恢复/重建, 导致 C-3 commit `f1947d3c7` 调研时无 baseline diff. 纪律: gap analysis 文档必先恢复 (git checkout 已删 gap analysis 文档 或 git revert 已删 commit) + 重建 (新增缺口 baseline diff + 派生新任务清单 + W73/W74 派工顺序表) 才启动 W73 调研. 沉淀: memory/w72-2nd-route-c3-pptword-gap-analysis-rebuild-2026-07-27.md (待沉淀).

## 段 9 W72 第 1 批 11 commit 锚点范式数字纪律 (新增)

W72 第 1 批 11 commit 全部 commit message 含锚点范式数字:

| Commit | 路线 | 锚点范式数字 |
|---|---|---|
| `6e074ffd9` | A-1 | 锚点范式第 207 守恒 |
| `937742218` | A-2 | 锚点范式第 208 守恒 |
| `206661254` | A-3 | 锚点范式第 209 守恒 |
| `7a1d07df8` | A-4 | 锚点范式第 210 守恒 |
| `4f737b61a` | B-1 | 锚点范式第 211 守恒 |
| `228aa9de3` | B-2 | 锚点范式第 212 守恒 |
| `1a33b816e` | B-3 | 锚点范式第 213 守恒 |
| `6c6f7b794` | B-4 | 锚点范式第 213 守恒 |
| `b7ad730a6` | B-5 | 锚点范式第 215 守恒 |
| `08df36e80` | C-1 | 锚点范式第 216 守恒 |
| `a78967661` | C-2 | 锚点范式第 217 守恒 |
| `f1947d3c7` | C-3 | 锚点范式第 218 守恒 |

commit message 实战模板 (v10 强制约束):
- 调研类: `chore(w72nd-batch-c<N>): <标题> (<调研主题>, <调研发现> + <派生新任务> + W73/W74 派工顺序, 锚点范式第 N 守恒)`
- 实施类: `feat(w72nd-batch-b<N>): <标题> (~<行数> 行, <要点> + type hint 必含, <测试> PASS, 锚点范式第 N 守恒)`
- 文档/沉淀类: `docs(w72nd-batch-d<N>): <标题> (<6 类文档同步>, 锚点范式 W71 206 → W72 220 守恒预期 +N, 0 production code 改动铁律 N/15 守恒)`
- memory 沉淀类: `memory(w72nd-batch-<a/b/c/d<N>>): <标题> (<沉淀主题>, 锚点范式第 N 守恒)`

## W73 起步纪律 6 项实战预测

- 派工 W73 调研 agent 时 prompt 必含 W73 起步纪律 6 项必读
- W73 调研 agent 必先 git log 真验证 W72 第 1 批 11 commit 落地状态
- W73 调研 agent 派生新任务清单必逐项 git log --grep 真验证
- W73 调研 agent 必含 gap analysis 文档恢复/重建验证段
- W73 调研 agent 必含商业化 docker base 起步必先验证段
- W73 调研 agent commit message 必含锚点范式数字 + W72 第 1 批实战引用

## v10 默认应用范围

- W72 第 2 批 派工: 默认 v10
- W73 batch 派工: 默认 v10; commit message 必含锚点范式数字 (v10 段 9 强制约束)
- W74+ 调研任务: 必须用 v10
- W73 段 5 反馈至少收到 N ≥ 5 agents 才能汇总升级 v11

## 完成标准核对

- [x] partial diff 已 commit (派工前干净)
- [x] docs/w72-prompt-paradigm-v10-2026-07-27.md 落盘 514 行 (约 500 行目标)
- [x] 13 段全做 (TL;DR + 段 1-13 + 结语)
- [x] typing imports 0 错 (此任务纯 docs 改动)
- [x] 1 commit + 待 push (memory 沉淀后一并 push)
- [x] memory 沉淀 (本文件)
- [x] 0 production code 改动 (派工纪要本身纯 docs)
- [x] 段 5 升级 18 项 (含 3 项 v10 新增)
- [x] 段 6 升级 14 段 (含 1 段 v10 新增)
- [x] 段 7 升级 19 类 (含 3 类 v10 新增)
- [x] 段 8 升级 6 项 (含 2 项 v10 新增)
- [x] 段 9 新增 W72 第 1 批 11 commit 锚点范式数字纪律

## commit hash (待 push)

- `<docs-commit>` — docs(w72nd-batch-a2): 派工纪要 v10 模板升级 (W72 第 1 批 11 commit 实战反馈: 段 5 升级 15→18 项 + 段 6 升级 13→14 段 + 段 7 升级 16→19 类 + 段 8 升级 4→6 项 + 段 9 新增 11 commit 锚点范式数字纪律, 锚点范式 W72 第 1 批 220 → W72 第 2 批 A-2 223 守恒 +3)
- `<memory-commit>` — memory(w72nd-batch-a2): 派工纪要 v10 模板升级 memory (v9→v10 diff + 18 项反馈 + 19 类派工前提错误 + W73 起步纪律 6 项, 锚点范式第 223 守恒预测)