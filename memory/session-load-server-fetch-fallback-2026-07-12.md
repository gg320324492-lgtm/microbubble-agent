---
name: session-load-server-fetch-fallback-2026-07-12
description: "P0-#1.6 — ensureSessionLoaded 只查 localStorage 不查 server 导致 server-only session (curl 测试残留 / 跨设备登录) 点击空白. 修: localStorage miss → fetchSessionFromServer async fallback + 写回 localStorage. vitest 9/9 + Playwright .bubble 0→36"
metadata: 
  node_type: memory
  type: project
  originSessionId: 987866fd-9014-4a38-b9fe-7f536684352d
---

**触发 (2026-07-12)**: 用户截图 — 左侧 session 列表显示 `hello (8 小时前 2 条)` 但点击进入主区空白 (curl 测试残留 / 跨设备登录 / PR6 持久化的 server-only session).

**根因**: `web/src/composables/chat/useChatStream.ts:273-286` `ensureSessionLoaded` 旧实现只查 localStorage 没服务器 fallback:
```ts
const saved = localStorage.getItem(`${MESSAGES_KEY_PREFIX}${id}`)
if (saved) {
  messagesBySession.value[id] = JSON.parse(saved)
} else {
  messagesBySession.value[id] = []  // ← server-only session 永远走这里
}
```
- server-side 创建的 session (curl 调试 / 跨设备登录 / 升级后首次登录 / PR6 持久化迁移) 本地永远 cache miss
- 直接 `messagesBySession[id] = []` → 主区空白
- 用户看到 session list 显示"2 条"但点击空

**修法**: `ensureSessionLoaded` 加 server fetch 兜底 (4 个分层):
1. localStorage hit → 直接用 (本设备历史常见 path, 不动)
2. localStorage miss → 设占位空数组 + 异步触发 `fetchSessionFromServer(id)`
3. `fetchSessionFromServer` 调 `chatHistoryStore.fetchMessages(id)` (已有 API, 不引新依赖)
4. 成功 → `serverToClient` 映射 + 写回 localStorage (下次启动 cache hit) + 更新 `messagesBySession[id]`
5. 失败 / 空 items → 保留占位数组 + `console.warn` best-effort 不阻塞 UI

**端到端验证**:
- vitest 9/9 PASS (4 新 case + 5 旧):
  · localStorage hit 不调 server (常见 path)
  · localStorage miss → server fetch + populate messages + 写 localStorage
  · server 返空 items → 保留空数组不写 localStorage (避免永久 stale 空缓存)
  · server fetch 失败 → 保留空数组 + `console.warn` best-effort
- npm run build → `manifest.4f8d6b64.webmanifest` + `useChatStream-2683dc1e.js` 含 `fetchSessionFromServer`
- git commit `65d4493b` 同时 force-add dist (CLAUDE.md 7-12 铁律: 源 + dist 必须 1 commit)
- Playwright 30s 后重跑:
  · curl 服务器: served index-28fb514a.js ✅
  · API live: `/api/v1/chat/sessions/user_1782916607641_ddzr/messages` 200 OK
  · UI render: **`.bubble count: 36`** (修复前 0), `主区文本长度: 1108` 显示真实 user/AI 对话 ✅

**Playwright 第一个发现**: 服务器 stale dist (老版本 index-99e5e252.js, 我的新 28fb514a 未上传). 验证必须 `curl /` 然后 `grep -oE 'index-[a-f0-9]+\.js'`,对比 git HEAD hash.

**Why**:
1. **localStorage 不能是 session load 的唯一数据源** — server-side 创建的 session 本地永远无 cache, 必须 fallback server fetch (这是 #043 设计的盲点)
2. **server fetch 失败必须 best-effort** — 占位空数组 + console.warn 不阻塞 UI (用户重试或换设备登录都能恢复)
3. **server 返空不要写 localStorage** — 避免永久 stale 空缓存, 等下次 fetch 又覆盖时才能显示正确状态
4. **server 返成功必须写 localStorage** — 下次启动 cache hit 减少 server 压力 + 离线友好
5. **Playwright 验证 cloud dist 必须看 served index hash** — 服务器可能 stale dist (本会话命中此坑), `curl / | grep index-` 校验新 hash 已部署

**How to apply (同类 bug 自查清单)**:
- 用户报"session 列表'X 条'但点开空白" → 立即 `grep "ensureSessionLoaded\|messagesBySession\[" web/src/composables/chat/useChatStream.ts` 看是否有 server fetch
- 第一反应不要"localStorage 加上 session_id 看是不是没存" — 而是查 "server-side 数据 + 跨设备 + 多浏览器登录 是否被设计支持"
- 加 server fetch fallback 时,记得 `chatHistoryApi.listMessages(id)` 已在 `web/src/api/chatHistory.js:124` 可用,**直接复用**,不要新写 fetch function
- 写完跑 `vitest run useChatStream.test.js` + Playwright spec 双验证 (vitest 测逻辑, Playwright 测用户视角)

**Where to fix (类似设计漏洞自查)**:
- `app/api/v1/chat_history.py:list_messages` 后端 API 已实现 ✅ (本次直接复用)
- `web/src/api/chatHistory.js:listMessages` 已存在 ✅ (本次直接复用)
- `web/src/stores/chatHistory.ts:fetchMessages` 已存在 ✅ (本次直接复用)
- `web/src/composables/chat/useChatStream.ts:serverToClient` 已存在 ✅ (本次直接复用)
- 唯一需要加的: `fetchSessionFromServer` 串联上面 4 段链路 + `ensureSessionLoaded` 加 fallback

**和 P0-#1, #1.5 的关系**:
- P0-#1 改 .env 让 chat 不再 Connection error (commit 20621c83)
- P0-#1.5 wrapper shape 修复让 chat 流不出错 (commit 9b908f50)
- P0-#1.6 server fetch 兜底让历史 session 不再空白 (commit 65d4493b)
- 3 commit 链 = 完整生产可用

**memory chain**:
1. `llm-backend-ollama-residual-connection-error-2026-07-12.md` (P0-#1)
2. `anthropic-msg-dict-wrapper-mimo-reasoning-content-2026-07-12.md` (P0-#1.5)
3. `session-load-server-fetch-fallback-2026-07-12.md` (P0-#1.6 本文件)
