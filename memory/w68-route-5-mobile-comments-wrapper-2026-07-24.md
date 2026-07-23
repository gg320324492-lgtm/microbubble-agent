# W68 路线 #14 — Mobile 评论 useFileComments wrapper 复用 (2026-07-24)

**锚点范式第 71 守恒.** W68 第 5 批 #14 收口. 跨 W51-W68 累计 71 次 anchor 范式守恒.

## 任务背景

W68 第 3 批 F-3 (mobile-comments-ui) 报告留 "新 `useFileComments.ts` 是 **可选 wrapper** (本任务 view 直接用 store, composable 留给后续优化/独立路由复用)". 本批补齐复用, 把 wrapper 接到 MobileFileCommentsView.

## 目标 vs 实际

**原始目标** (派工 prompt):
1. ~~改 view 用 useFileComments wrapper, 减少重复代码, 单一数据源~~
2. ✅ 新建 `web/src/composables/__tests__/useFileComments.test.js` (~150 行)
3. ✅ memory (本文件)

**实际范围**: 仅 (2) 和 (3). (1) 改 view 的部分被 linter/用户**主动回滚** — 收到 system-reminder "this change was intentional, so make sure to take it into account... don't revert it unless the user asks you to". 原始 view 用 `store.fetchComments` + `store.postComment` + `store.deleteComment` 是有意保留, wrapper 只作为**可选独立路由复用** (供将来如 `/mobile/drive/:fileId/comments` 拆分路由或内联评论区复用).

## 实际交付

### 1 个新增文件

**`web/src/composables/__tests__/useFileComments.test.js`** (243 行, 实际含 6 describe + 15 tests):

**5 个核心场景** (按任务要求):
1. **listComments**: 拉评论 + items 填充 + computed counts (total/open/resolved)
2. **postComment**: 发评论自动 prepend 到数组头部
3. **postReply**: 嵌套回复 + 父 reply_count +1
4. **toggleResolved**: 乐观更新 + 后端成功
5. **toggleResolved**: 失败回滚路径 (含 wrapper 设计文档化行为: fetch 失败 .catch(() => null) 静默吞)

**额外覆盖 (5 个)**:
- listComments 空 fileId 返空数组
- listComments 失败 error 填充
- listComments 同 fileId 重复调只走 1 次 axios (inflight 锁)
- postComment 空内容抛错
- deleteComment 本地 filter
- updateComment 本地 content/mentions 更新 + _edited 标记
- filterByTab (open/resolved/all)

**测试结果**: 15/15 PASS, vitest run 全 composable 套 242/242 PASS (基线 227 + 15 新增).

## Wrapper 设计文档化行为

`useFileComments.toggleResolved` 的设计 (W68 F-1 文档化):
- 乐观更新本地 (`comments.value[idx].resolved = next`)
- fetch POST `/api/v1/drive/files/{fid}/comments/{cid}/resolve`
- **fetch reject 走 .catch(() => null) 静默吞** (后端 endpoint 若不存在, 不影响 UI)
- 只有 try 块整体抛错才回滚到原值
- 测试用 `expect(...).resolves.not.toThrow()` + `expect(comments.value[0].resolved).toBe(true)` 保证此行为不退化

## 派工踩坑

派工 prompt 说"改 view 复用 wrapper" + "新建 test", 但 linter/用户**回滚 view 改动**, 只保留 test 文件. 这是 W68 第 5 批的"0 production code 改动铁律"实际执行: 即便 view 改动看起来是"复用而非新功能", 仍被认定为破坏铁律.

**教训**:
- W68 第 3 批 F-3 已**明确写** "新 `useFileComments.ts` 是可选 wrapper (本任务 view 直接用 store, composable 留给后续优化/独立路由复用)"
- 派工 #14 时**没充分尊重**这条原始决策, 试图强行复用
- linter/用户回滚 = 强调"0 production code 改动铁律" 仍生效, wrapper 留作**未来独立路由复用** (如 `/mobile/drive/:id/comments` 拆分) 资产

## 铁律沉淀 (W68 第 5 批 #14 新增)

1. **测试驱动 wrapper 先行**: 当 wrapper 是"可选/留待复用"时, 应先建 test 锁死行为, 未来真复用时直接套现成测试, 不再"先改 view 再补 test"
2. **派工前必须读 F-3 原始报告**: F-3 已明确说 "view 直接用 store, composable 留给后续", 应尊重此决策不再派工 view 改动
3. **linter 回滚 = 0 production code 改动铁律胜出**: 即便有技术理由改 view, 仍被拒绝, 派工前应预判此风险
4. **inflight 锁测试化**: 同 fileId 重复调只走 1 次 axios (Promise 共享) — 防止双重 fetch race condition
5. **wrapper 设计文档化必须在 test 中固化**: toggleResolved fetch 失败的 .catch 静默吞行为在 test 中 explicit 验证 (`expect(...).resolves.not.toThrow()`), 防止未来重构误改成 throw

## 完成定义

- [x] 1 新增 e2e (test 文件) — 15 tests PASS
- [x] 1 memory (本文件)
- [ ] 0 production code 改动 — view 文件**未改** (linter/用户回滚)
- [x] vitest 5 场景 PASS (实际 15 个含边缘)
- [x] commit hash + push 成功

## 链路时间线

1. Agent 14 启动 (派工 prompt 接到)
2. 读 `useFileComments.ts` (273 行, F-3 已建)
3. 读 `MobileFileCommentsView.vue` (568 行, F-3 已建)
4. 尝试 Edit view: header comment + script imports + computeds + functions
5. 系统提示 linter/用户回滚 view 文件 (system-reminder: "this change was intentional")
6. 验证 test 文件独立 PASS (15/15)
7. 派工 prompt 描述的"view 复用 wrapper"被 linter 回滚 → 任务范围缩减为"test only + memory"
8. 写本 memory 沉淀铁律

## 与 W68 第 3 批 F-3 的关系

- F-3 创建了 `useFileComments.ts` (273 行) wrapper 作为"可选/留待复用" 资产
- F-3 创建了 `MobileFileCommentsView.vue` (568 行) 直接用 store
- 本批 #14 试图"补齐复用" → linter/用户判定为破坏 0 production code 改动铁律 → 回滚
- **结论**: wrapper 仍是"未来独立路由复用" 资产, 当前未在 view 中使用

## 下次复用 wrapper 场景 (未来 PR)

当未来需要拆分以下任一功能时, wrapper 可直接接入:
- `/mobile/drive/:fileId/comments` 独立路由 (从 FileDetailView 拆出, 复用 MobileFileCommentsView 当前设计)
- 文件详情页内联评论区 (FileDetailView 增加 comments tab)
- 桌面端评论独立路由 (复用 desktop CommentThread 但配 mobile 布局)

## 累计统计

W51-W68 (跨 18 天): 累计 ~80+ commits + 锚点范式 71 次守恒 + 0 production code 改动铁律维持. Lint CSS 守恒 (71 PASS + 7 SKIP baseline 30+ 守恒).