# Mobile UX v3.2 开发者指南

> W68 第 8 批 B-3 建立 (移动端 v3.2) + W68 第 9 批 B-3 追加 §4 (桌面端 v3.2 收口).
> 2026-07-24 主指挥协调范式.

评论系统 v3.2 在 v3.1 (评论 thread + resolved) 基础上, 新增 **emoji 表情反应** + **@mention 自动补全预览** + **嵌套 breadcrumb (祖先链)** 三大能力, 桌面 (Element Plus) 与移动 (NutUI) **组件对等 (parity)**, 复用同一批 composable。

## §1 emoji 表情反应

- **12 emoji 白名单** (`useCommentReactions.ts` `EMOJI_WHITELIST` 单一真源):
  `👍 ❤️ 🎉 😂 😮 😢 🔥 💯 ✨ 🙏 🤔 👀`
- 修改白名单必须同步后端 `REACTION_EMOJI_WHITELIST` (PR12)。
- 数据模型: `reactionsByComment[commentId] = [{ emoji, count, reacted_by_me }]`。
- 交互: hover/点击评论 → 弹 12 emoji popover → 点某 emoji → 乐观写入 + POST → 服务端权威 count 校准 (`_reconcile`)。
- 汇总 bar: 只展示 `count > 0` 的 emoji, `reacted_by_me` 高亮 (`.mine` class)。

## §2 @mention 自动补全

- 复用 `useMentionAutocomplete.js` (v2 PR6-P4)。
- 输入 `@` → debounce 150ms → 本地 filter members (wechat_id/username/name) → dropdown (↑↓ 选, Enter/Tab 补全, Esc 关)。
- v3.2 新增 **已 mention 用户预览**: 扫描文本 `@handle` → 匹配 membersList → 底部 chip 列表 (`将提醒: @xxx`)。

## §3 嵌套 breadcrumb (祖先链)

- `useCommentBreadcrumb.ts`: `GET /drive/comments/{id}/breadcrumb` → `[{ id, user_id, username, snippet }]` (顶层在前, 不含自身)。
- snippet 后端截断 ~40 字, 前端 `_truncate` 兜底。
- 性能: 只对嵌套评论 (`thread_depth > 0 || parent_comment_id != null`) 拉, cache by commentId, fileId 切换清 cache。

## §4 桌面端 v3.2 集成 (W68 第 9 批 B-3 追加)

桌面端与移动端**共用同一批 composable** (`useCommentReactions` / `useCommentBreadcrumb` / `useMentionAutocomplete`), 仅 UI binding 不同:

| 能力 | 桌面组件 | 复用 composable | 差异 |
|------|----------|-----------------|------|
| emoji 工具栏 | `DesktopFileCommentsView.vue` (文件级) | `useCommentReactions` | 文件级用虚拟 key `file:<id>` 隔离评论反应 |
| emoji 单评论 | `DesktopCommentThread.vue` | `useCommentReactions` | hover popover (12 emoji) + `.mine` 高亮; 移动端走 long-press |
| @mention 预览 | `DesktopCommentInput.vue` | `useMentionAutocomplete` | 已 mention chip 预览; Cmd/Ctrl+Enter 发送 |
| breadcrumb | `DesktopCommentThread.vue` | `useCommentBreadcrumb` | 嵌套评论顶部渲染, `depth > 0` 才显示 |

### 桌面端数据流

```
DesktopFileCommentsView (onMounted)
  → fetchAll(): fetchFileMeta + listComments + batchResolveMembers
  → loadReactionsAndBreadcrumbs():
      fetchReactions([...commentIds, file:<id>])
      nested.map(c => fetchBreadcrumb(c.id))   # 仅嵌套评论
  → DesktopCommentThread 递归接收 reactionsMap / breadcrumbMap / emojiWhitelist (map 形式透传)
      每节点按 comment.id 取 reactionsMap[id] / breadcrumbMap[id]
      emit('toggle-reaction', id, emoji) → 冒泡到 View → toggleReaction()
```

### map 透传约定 (递归组件)

`DesktopCommentThread` 用 `reactionsMap` / `breadcrumbMap` (对象, 按 commentId 索引) 而非单条数组透传 — 递归子节点各自按 `comment.id` 取自己的数据, 避免逐层拆包。`emojiWhitelist` array 直接透传。

### 桌面/移动 parity 校验点

- emoji 白名单同源 (`EMOJI_WHITELIST` 只在 `useCommentReactions.ts` 定义)。
- 乐观更新 + rollback 逻辑同源 (composable 内, UI 不重复实现)。
- 后端 endpoint 未部署时静默降级 (reactions/breadcrumb 都 try/catch 返回空, 不阻塞列表渲染)。

### 测试

- e2e: `web/tests/e2e/desktop_comment_v32.spec.js` (5 场景: emoji 上传 / mention 预览 / breadcrumb 渲染 / reaction 聚合 / 5 层深链)。
- 回归: `desktop_drive_comments.spec.js` + `desktop_drive_mention.spec.js` (17 test) 全过。
