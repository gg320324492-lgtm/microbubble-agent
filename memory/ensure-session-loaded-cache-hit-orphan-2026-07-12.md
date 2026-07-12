---
name: ensure-session-loaded-cache-hit-orphan-2026-07-12
description: "P0-#1.6 v2 — ensureSessionLoaded v1 修复后用户截图报\"41条仍然看不全\";真根因:v1 把 localStorage 空数组 '[]' 误判为 cache hit 永远不 fetch;v2 修:加 serverFetchedSessions Set 独立追踪 + parsed.length > 0 才视为 cache hit;Playwright .bubble 数 0→41"
metadata: 
  node_type: memory
  type: project
  originSessionId: 987866fd-9014-4a38-b9fe-7f536684352d
---

**触发 (2026-07-12 13:30)**: 用户报告 '41条仍然看不全' — 你好 session list 显示 41 条但主区只看到欢迎语气泡 + 0 条真实消息.

**真根因 (v1 修复的 regression)**:
P0-#1.6 v1 (commit 65d4493b) 修复了 'server-only session 空白' 但**留下第二个 orphan 缓存漏洞**:
```ts
function ensureSessionLoaded(id: string) {
  if (loadedSessions.has(id)) return
  loadedSessions.add(id)
  const saved = localStorage.getItem(`${MESSAGES_KEY_PREFIX}${id}`)
  if (saved) {                              // ← 只看 key 是否存在
    messagesBySession.value[id] = JSON.parse(saved)  // ← '[]' 解析成 []
    return                                  // ← 永远不 fetch!
  }
  messagesBySession.value[id] = []
  void fetchSessionFromServer(id)
}
```

**链路**:
- 修复前 (production v0): `loadedSessions.has(id)` 仅防御 SSE 增量覆盖, **没有** server fetch fallback
- 用户在 v0 阶段已打开 chat + 点击 server-only session → `messagesBySession[id] = []` → 渲染空白
- 同时用户**本地缓存**也写入 `'chat_msgs_{id}' = '[]'`
- v1 部署后: v1 判断 `localStorage 有内容 → cache hit → 不 fetch` 但内容是空数组 → 还是空白
- 用户截图: 看到 list 41 条但实际渲染 0 条 (因为 localStorage 的 '[]' 被当缓存用)

**v2 修法**: 加 `serverFetchedSessions` Set 独立追踪 + 区分**真实缓存** vs **空数组占位**:
```ts
const serverFetchedSessions = new Set<string>()

function ensureSessionLoaded(id: string) {
  if (serverFetchedSessions.has(id)) return  // ★ v2: 只看 server fetch 过与否
  serverFetchedSessions.add(id)
  loadedSessions.add(id)  // 兼容原防 SSE 增量覆盖
  const saved = localStorage.getItem(`${MESSAGES_KEY_PREFIX}${id}`)
  if (saved) {
    const parsed = JSON.parse(saved)
    messagesBySession.value[id] = parsed
    if (Array.isArray(parsed) && parsed.length > 0) {
      // ★ v2: 只有真实内容才视为 cache hit
      return
    }
    // 空数组 (orphan) → 继续走 server fetch
  }
  messagesBySession.value[id] = []
  void fetchSessionFromServer(id)
}
```

**端到端验证**:
- vitest 12/12 PASS (新增 3 回归 case):
  · **v2 核心 case**: localStorage cache '[]' 时仍必须 server fetch (orphan 修复)
  · ensureSessionLoaded 二次调用不重复 fetch (serverFetchedSessions 防御)
  · localStorage 有真实内容时跳过 fetch (常见 path 不退化)
- npm run build → `useChatStream-4ac9581f.js` + `index-171c33e0.js`
- Playwright v2 回归测试: 你好 session **41 条全部可见** ✅
  - 修复前: `.bubble count: 0` (orphan 缓存永远不 fetch)
  - v1 修复后: `.bubble count: 38` (本地 fix 起效但 cache 命中错误没解决)
  - **v2 修复后: `.bubble count: 41`** ✅ (与 server list count=41 完全一致)

**2 新铁律 (永久沉淀)**:
1. **localStorage cache hit 判定必须看内容, 不能只看 key 存在** — `'[]'` 是 orphan 占位, 不应等同真缓存
   - 反例: `if (saved) { use saved }` 把 orphan '[]' 当有效缓存
   - 正例: `if (Array.isArray(parsed) && parsed.length > 0) { use cache }`
2. **cache hit + server fetch 是不同维度, 必须独立 Set 追踪** — '是否真 fetch 过' (serverFetchedSessions) 不能用 'localStorage 是否有值' 替代, 两者语义完全不同
   - 反例: 用 loadedSessions 一个 Set 既防 SSE 增量覆盖又防重复 fetch, 语义耦合
   - 正例: serverFetchedSessions (是否真 fetch 过) + loadedSessions (是否在 messagesBySession 里) 独立

**完整修复链 (P0-#1.6 三版演化)**:
- v0 (修复前, commit <a687cee7 PRE): ensureSessionLoaded 只查 localStorage → server-only session 空白
- v1 (commit 65d4493b, P0-#1.6 v1): 加 fetchSessionFromServer fallback → 修 server-only session, 留 orphan 缓存漏洞
- v2 (commit a687cee7, P0-#1.6 v2 本次): 加 serverFetchedSessions 修 orphan 缓存漏洞 → '41 条全部可见'

**Why 双 Set 不是单 Set**:
- `loadedSessions` 用途: 防后台 SSE 增量覆盖已渲染的消息 (exist 语义)
- `serverFetchedSessions` 用途: 防重复 server fetch (fetch 语义)
- 合并后无法表达 "已 SSR 但未 server fetch" 或 "已 server fetch 但 SSR 失败" 两种边缘状态
- 单 Set 实现需要复杂 flag 组合, 双 Set 简单清晰

**How to apply (同类 bug 自查)**:
- 用户报 "session list 正常但点击空白/少部分消息" → 立即打开 DevTools Application → Local Storage → 找 `chat_msgs_*` 键
- 如果有任何 key value 是 `'[]'` → 就是 orphan 缓存, 修复要求强制 server fetch
- 不要 `localStorage.clear()` 让 user 自行修复 — 这是技术债, 应该改代码不依赖 user 操作

**踩坑教训**:
- 第一版 (v1) 乐观假设 "localStorage 有内容 = 真缓存" 没考虑 bug 状态污染
- 第二版 (v2) 加 serverFetchedSessions Set 与 localStorage 内容解耦
- 类似设计模式: localStorage 可以被旧版本污染, cache hit 判定必须 robust
- 永远不要 100% 信任 localStorage 内容作为 cache hit 唯一依据

**完整 memory chain**:
1. `llm-backend-ollama-residual-connection-error-2026-07-12.md` (P0-#1)
2. `anthropic-msg-dict-wrapper-mimo-reasoning-content-2026-07-12.md` (P0-#1.5)
3. `session-load-server-fetch-fallback-2026-07-12.md` (P0-#1.6 v1)
4. `ensure-session-loaded-cache-hit-orphan-2026-07-12.md` (P0-#1.6 v2 本文件)
