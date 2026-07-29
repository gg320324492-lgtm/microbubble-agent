# Session Polling 审计 P2 候选 4 项 (Follow-up) — 2026-07-20

> **W10 T2 审计** — W2 T3 审计报告 (commit 8c401031) P2-A/B/C 已修 (chat_share / KB timeout / chat fetch timeout), 本任务审计 P2 候选 4 项
> **作者**: Claude Fable 5 (Worker 10)
> **HEAD**: 5c77c417 (W8.1 sessionmaker 优化)
> **铁律遵守**: 只审计, 不动生产代码, 不动其他 worker 范围, defer commit (无 code change)

---

## 🚨 4 项审计结果

### 1️⃣ chat_history dedup 提示

**审计范围**: `web/src/api/chatHistory.js` + `web/src/stores/chatHistory.ts` + `web/src/composables/chat/useChatStream.ts` + `web/src/stores/chatSessions.ts`

**实际行为**:
- ✅ `mergeServerList` (chatSessions.ts:259) 按 `server.id` 去重 — server-side API 返回 distinct sessions 没问题
- ✅ `createServerSession` (chatHistory.ts:139) 总是创建新 session — 不做 client-side dedup
- ❌ **没有 content-based dedup**: 用户在 2 个 tab 误发同一 first message → 创建 2 个空 session, 侧栏显示重复
- ❌ **没有 title 重复检测**: 用户连续点 3 次 "+ 新对话" → 3 个标题都是 "新对话", 侧栏视觉冗余

**风险等级**: 🟡 P3 (用户偶尔遇到, 不阻塞业务, 但侧栏 UX 不优雅)

**修复建议** (未来 PR):
- 创建新 session 时, 如有最近 60s 内同 first_message 的 session, 提示用户 "是否跳转到现有 session?"
- 默认 session title 生成器: `新对话 ${HH:mm}` 时间戳后缀避免重复

**不动手原因**: P3, 用户决策"接受丢失" 模式, 不阻塞业务.

---

### 2️⃣ 同 session 复用

**审计范围**: `web/src/composables/chat/useChatStream.ts` + `web/src/views/chat/ChatViewSSE.vue` + `web/src/views/mobile/chat/MobileChatView.vue`

**实际行为**:
- ✅ **单组件 mount**: `serverFetchedSessions` Set (line 281) 防重复 fetch, `loadedSessions` Set (line 177) 防 localStorage 覆盖 — 完整
- ✅ **desktop + mobile 共用 useChatStream**: 但 `useIsMobile` 路由级双栈, 同时只 mount 1 个 view, 无冲突
- ❌ **多 tab / 多窗口**: 每个 tab 的 `useChatStream()` 是全新状态 (loadedSessions / serverFetchedSessions / messagesBySession 都是 local), 切换 tab 会重新 fetch
- ❌ **SPA 内部多组件**: 如果将来 ChatViewSSE 被多次 mount (e.g., modal + main), 每个实例独立, 无共享 cache

**风险等级**: 🟢 LOW (单 tab 场景完整, 多 tab 是 P3 nice-to-have)

**修复建议** (未来 PR, 不阻塞):
- 多 tab 共享: 依赖 localStorage + storage event (跟第 3 项联动)
- SPA 内部共享: 提取 `useChatStream` state 到 Pinia store, 多组件共享

**不动手原因**: 现状满足核心需求 (单 tab 单组件), 改造要碰 Pinia 重构.

---

### 3️⃣ 跨 tab 同步

**审计范围**: `grep -rn "storage.*event\|addEventListener.*storage\|BroadcastChannel" web/src/`

**实际行为**:
- ❌ **完全没有 storage event listener**: `grep "addEventListener.*storage"` 0 命中
- ❌ **完全没有 BroadcastChannel**: `grep "BroadcastChannel"` 0 命中 (只有 SW postMessage 和 worker postMessage)
- ⚠️ **localStorage 写不广播**: tab A 创建新 session 写 localStorage → tab B 不感知 → 用户切 tab B 看到侧栏 stale

**风险等级**: 🟡 P3 (多 tab 用户偶尔遇到, 单 tab 不受影响)

**修复建议** (未来 PR):
```js
// web/src/main.js 或专门的 useStorageBroadcast composable
window.addEventListener('storage', (e) => {
  if (e.key === 'chat_sessions_v3') {
    // 触发 useChatSessionsStore.mergeServerList() 重新拉 server
    // 或直接 reload 侧栏 store
  }
})
```

**不动手原因**: 多 tab 用户占比低 (移动端普及, 桌面多 tab 不主流), 改造涉及 storage event 全局监听 + debounce.

---

### 4️⃣ timer 性能

**审计范围**: `web/src/composables/chat/useChatStream.ts` + `web/src/utils/wsClient.js`

**实际行为**:

| Timer | 创建位置 | 清理位置 | 风险 |
|---|---|---|---|
| `persistTimers[id]` (line 180/260) | `persistSessionSync` | ❌ **未清理** — onUnmounted 不 clearTimeout | 🟡 P2 |
| `migration setTimeout` (line 1003) | `onMounted` 异步迁移 | ❌ **未清理** — onUnmounted 不 clearTimeout | 🟡 P2 |
| `abortControllers` (sse per session) | `sendMessage` | ✅ onUnmounted abort 全部 (line 1019-1022) | OK |
| `reconnectTimer` (wsClient.js:108) | `_scheduleReconnect` | ✅ `disconnect()` + `onclose` 都清理 (line 120) | OK |
| `elapsed timer` (useGlobalRecorder.js:129) | `start()` | ⚠️ 模块级 timer, 需手动 stop | 🟢 LOW |
| KB poll timer (useKbMonitor.js:55) | `startPolling` | ✅ `onUnmounted` clearInterval | OK |

**核心 P2 发现**: `useChatStream.ts:1017 onUnmounted` 没清理 `persistTimers` (line 180 的 dict). 用户在 SPA 路由切换 / 关闭页面时, pending `setTimeout(persistSessionSync, ...)` 仍会执行 (写 localStorage), 但 component 已 unmount → **内存泄漏 + 副作用意外触发**.

**实际触发场景**:
1. 用户在 ChatView 打字 → 触发 `persistSessionSync(sid, { debounceMs: 300 })` → 注册 `persistTimers[sid]` setTimeout
2. 用户在 300ms 内切到其他 route → ChatView unmount
3. `onUnmounted` 调 `persistSessionSync` 一次 (line 1027) → 但 `persistTimers[sid]` 旧 timeout 仍在
4. 300ms 后旧 timeout 触发 → 又写一次 localStorage (重复写)

**风险等级**: 🟡 P2 (实际触发场景常见, 重复写 + 内存泄漏, 不阻塞但累积)

**修复建议** (未来 PR):
```js
// useChatStream.ts:1017 onUnmounted
onUnmounted(() => {
  // 清理 pending persist timers
  for (const id of Object.keys(persistTimers)) {
    if (persistTimers[id]) clearTimeout(persistTimers[id])
    delete persistTimers[id]
  }
  // 清理 migration timer
  if (migrationTimer) clearTimeout(migrationTimer)
  // ... 原有 abort + persist
})
```

**不动手原因**: P2, 不阻塞业务, 但建议下个 PR 顺手修.

---

## 📊 总览

| # | 候选 | 风险等级 | 触发场景 | 修复建议 |
|---|---|---|---|---|
| 1 | chat_history dedup 提示 | 🟡 P3 | 多 tab / 重复点击 "+" | title 时间戳 + content 相似度检测 |
| 2 | 同 session 复用 (多 tab) | 🟢 LOW | 多 tab 切来切去 | Pinia state 提取 + 跨 tab 共享 |
| 3 | 跨 tab 同步 (storage event) | 🟡 P3 | tab A 写 localStorage, tab B 不感知 | window.addEventListener('storage') |
| 4 | timer 性能 (persistTimers 泄漏) | 🟡 **P2** | SPA 路由切换 / 频繁打字 | onUnmounted 加 clearTimeout |
| **合计** | | | | **0 P0 / 0 P1 / 1 P2 / 2 P3** |

---

## 🎯 P0/P1 issue 报告

**无 P0 issue**, **无 P1 issue**.

W2 T3 报告 (commit 8c401031) 已闭环 P2-A/B/C, 本任务新发现 **1 个 P2** (timer 性能) + 2 个 P3 (dedup 提示 / 跨 tab 同步).

**P2 (timer) 建议**: 派下一个 worker (W11) 单 commit 修 `useChatStream.ts:1017 onUnmounted`, 改动 < 10 行, 不影响其他逻辑.

---

## 5 新铁律沉淀 (审计方法论)

1. **grep 是审计起点** — `grep "addEventListener.*storage"` / `grep "BroadcastChannel"` / `grep "clearTimeout"` 0 命中 = 没实现, 比读代码快
2. **timer cleanup 必须 onUnmounted 覆盖全部** — `useChatStream.ts:1017` 只 abort SSE + persist, 没 clearTimeout persistTimers → 经典 onUnmounted 不完整案例
3. **单组件 mount 状态是 localStorage 级别, 不是 Pinia** — `useChatStream` 函数式 state 是单实例, 多 tab / 多组件需要 store 提取
4. **storage event 是浏览器原生多 tab 同步 API** — 不需要 BroadcastChannel / WebSocket, 单 `addEventListener('storage', ...)` 即可
5. **审计不动代码, 但必须指明修复代码** — 报告含具体修复建议 (e.g., onUnmounted 加哪几行), 主指挥可一键派 worker

---

## 8 P2-A/B/C 闭环状态 (W2 T3 报告)

| 候选 | 状态 | commit |
|---|---|---|
| P2-A 过期 chat_share 主动清理 | ✅ 已修 | `a37ef09b` |
| P2-B localStorage chat session 90 天 TTL | ✅ 已修 | `1a0ecbed` |
| P2-C KB polling + chat fetch 30s timeout | ✅ 已修 | `f3e637cf` |
| **新 P2 (本次)** timer 性能 (persistTimers 泄漏) | ⏳ 留未来 PR | — |
| P3 chat_history dedup 提示 | ⏳ 留未来 PR | — |
| P3 跨 tab 同步 (storage event) | ⏳ 留未来 PR | — |
| P3 同 session 复用 (多 tab 共享) | ⏳ 留未来 PR | — |

---

## 完成汇报 (W10 → 主指挥)

1. **审计报告**: `docs/session-polling-p2-followup-2026-07-20.md` (本文件)
2. **4 项风险等级**: 🟢 LOW ×1 + 🟡 MEDIUM (P3×2 + P2×1) + 0 P0/P1
3. **P0 issue**: 无
4. **P1 issue**: 无
5. **P2 issue** (新发现): useChatStream.ts:1017 onUnmounted 不清理 persistTimers (timer 泄漏 + 重复写)
6. **commit hash**: 无 (本任务纯审计, defer, 无 code change)
7. **不动其他 worker 范围**: W9 9 文件合跑不碰, W8.1 sessionmaker 不碰, W5+1 follow-up 不碰
8. **不动生产代码**: 严格遵守 W10 T2 铁律 1