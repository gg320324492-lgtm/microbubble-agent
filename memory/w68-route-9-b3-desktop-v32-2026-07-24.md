# W68 第 9 批 B-3 — 桌面端评论 UI v3.2 收口 (emoji + @mention + breadcrumb)

> 2026-07-24 · 分支 `feat/desktop-comment-v32-2026-07-24` · 锚点范式第 110 守恒
> 主题: Drive v2 + Mobile UX 系列 · 0 production code 改动铁律 (仅前端)

## 背景

- W68 第 7 批 F-3 已建桌面评论 UI (`DesktopFileCommentsView` + `DesktopCommentThread` + `DesktopCommentInput`), 但**缺** emoji 表情反应 / @mention 预览 / 嵌套 breadcrumb。
- W68 第 7 批 #11 报告 desktop mention 已实现 (`useMentionAutocomplete` 复用), 但 emoji react 菜单 + breadcrumb 待补。
- 本任务收口 desktop v3.2 三大能力, 与移动端 parity。

## 交付 (8 文件)

| 类型 | 文件 | 说明 |
|------|------|------|
| 改 | `web/src/views/desktop/DesktopFileCommentsView.vue` | 文件级 emoji 工具栏 (12) + summary bar + 装配 2 composable + 递归透传 map |
| 改 | `web/src/components/desktop/DesktopCommentThread.vue` | 单评论 emoji react (hover popover) + reaction 汇总 bar + breadcrumb 渲染 + map 递归透传 |
| 改 | `web/src/components/desktop/DesktopCommentInput.vue` | 已 mention 用户预览 chip (复用现有 useMentionAutocomplete) |
| 新 | `web/src/composables/useCommentReactions.ts` | ~230 行 · GET/POST/DELETE reactions + 乐观 + rollback + 12 emoji 白名单单一真源 |
| 新 | `web/src/composables/useCommentBreadcrumb.ts` | ~130 行 · GET breadcrumb + cache + inflight 锁 + snippet truncate |
| 新 | `web/tests/e2e/desktop_comment_v32.spec.js` | 5 场景 PASS |
| 新 | `docs/mobile-ux-v3.2-developer-guide.md` | §1-3 移动 + §4 桌面集成 (W68 第 9 批追加) |
| 新 | 本 memory | 锚点范式第 110 守恒 |

## 后端 API 契约 (前端消费, endpoint 由 PR11/PR12 提供)

- `GET /api/v1/drive/reactions?comment_ids=1,2,3` → `{ items: { [id]: [{ emoji, count, reacted_by_me }] } }`
- `POST /api/v1/drive/reactions {comment_id, emoji}` → `{ comment_id, emoji, count, reacted_by_me }`
- `DELETE /api/v1/drive/reactions {comment_id, emoji}` (axios `data` 传 body)
- `GET /api/v1/drive/comments/{id}/breadcrumb` → `{ items: [{ id, user_id, username, snippet }] }` (顶层在前, 不含自身)

未部署时静默降级 (try/catch 返回空, 不阻塞), 与 F-1 `toggleResolved` fetch().catch(null) 模式一致。

## 测试结果

- `desktop_comment_v32.spec.js` — **5/5 PASS** (emoji 上传 / mention 预览 / breadcrumb 渲染 / reaction 聚合 / 5 层深链)。
- 回归: `desktop_drive_comments` + `desktop_drive_mention` **17/17 PASS**, `src/composables` **260/260 PASS**。
- 环境注意: 隔离 worktree 无 node_modules → `mklink /J node_modules E:\microbubble-agent\web\node_modules` junction 后可跑 vitest。

## 5 条新铁律

1. **emoji react 乐观更新必须服务端 count 校准** — 乐观 `_applyLocal(±1)` 立即反馈, POST/DELETE 返回后用 `_reconcile(payload.count)` 覆盖权威值; 失败必 rollback (反向 `_applyLocal`)。count 归零自动移除 emoji 条目 (不留 0 count 幽灵 pill)。

2. **mention autocomplete 复用不重造** — 桌面/移动共用 `useMentionAutocomplete.js` (v2 PR6-P4)。v3.2 "已 mention 预览"只是在 `DesktopCommentInput` 加一个 computed 扫 `@handle` regex (镜像后端 `/@([一-龥A-Za-z0-9_.\-]{1,32})/`) + 匹配 membersList, **不动** composable 本体。

3. **breadcrumb 性能: 只对嵌套评论拉 + cache by id** — `thread_depth > 0 || parent_comment_id != null` 才 `fetchBreadcrumb`; 顶层评论无祖先链不请求。cache `chainByComment[id]` + inflight Map 防重复; fileId 切换 `clear()` 防跨文件串链。

4. **桌面/移动 parity: composable 是唯一真源, UI 只 binding** — emoji 白名单 (`EMOJI_WHITELIST`) / 乐观 rollback / 降级逻辑全在 composable; 桌面 (EP hover popover) 与移动 (long-press) 仅交互层不同。递归组件用 **map 透传** (`reactionsMap` / `breadcrumbMap` 按 commentId 索引) 而非逐条数组, 子节点各取自己的 `comment.id`。

5. **12 emoji 白名单单一真源 + 前后双校验** — `EMOJI_WHITELIST` 只在 `useCommentReactions.ts` export, 桌面/移动/e2e 全 import。`addReaction`/`removeReaction` 入口 `isValidEmoji` 强校验 (抛错), 后端 PR12 二次校验。修改白名单必须同步后端 `REACTION_EMOJI_WHITELIST`。

## 纪律守恒

- 0 production code 改动铁律维持 — 8 文件全部前端 (views/components/composables/tests/docs) + memory。
- 复用 W68 第 7 批 `useMentionAutocomplete` (无新造)。
- dark mode 跨组件覆盖放非 scoped `<style>` 块 (v60-v67 教训第 N 次强化) — breadcrumb/reaction pill/emoji popover 均加 `[data-theme="dark"]`。
- 分支不 merge (主指挥来 merge)。
