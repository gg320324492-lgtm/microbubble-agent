---
name: kb-and-chat-timeout-2026-07-20
description: KB polling + chat fetch 30s timeout 防御 + axios timeout vs AbortController 选择
metadata: 
  node_type: memory
  type: project
  originSessionId: 0f277dd1-0a27-4a11-b320-da966057abae
  modified: 2026-07-20T12:55:22.127Z
---

# KB Polling + Chat Fetch 30s Timeout (2026-07-20)

## TL;DR

🎯 **网络卡顿不能让 SPA 无限挂起** — KB polling (`useKbMonitor.js`) + chat fetch (`chatHistory.js`) 加 30s timeout 防御。

**Why**: W2 T3 审计报告 `8c401031` `docs/session-polling-audit-2026-07-20.md` P2 候选 C — 网络卡顿时 polling/fetch 无限挂起, 用户体验差。

**How to apply**: 见下方 axios timeout 实施 + 2 新铁律 + 不动其他 P2 范围。

## 核心实现 (W2 P2-C)

### useKbMonitor.js
```js
const POLL_TIMEOUT_MS = 30 * 1000  // 30 秒

// axios timeout (axios 原生, 不需要 AbortController)
const res = await axios.get(url, { timeout: POLL_TIMEOUT_MS })
```

### chatHistory.js (listMessages)
```js
return http.get(`/chat/sessions/${sid}/messages`, { timeout: 30000 })
// 跟同文件 syncFromLocal { timeout: 30000 } 对齐
```

## 实施选择说明

### axios `timeout:` vs AbortController
- **axios `timeout:`**: 原生支持, 自动 reject with `code='ECONNABORTED'`, 进 catch 后保留旧 data (复用 W5 T5.4 教训)
- **AbortController**: 更精细控制, 但需要手动管理 AbortSignal, 代码复杂度高

**选择**: axios `timeout:` 更简单, 适合 polling 场景 (不需要精细控制取消)。

### 不引入新常量在 composable 层
- `useKbMonitor.js` 内联 `POLL_TIMEOUT_MS = 30 * 1000` (T4 范围紧凑)
- 不下沉到 `settings` (避免扩张 scope)

## 2 新铁律

### 铁律 1: polling 必须有 timeout
网络卡顿不能让 SPA 无限挂起。任何 `setInterval` + `axios.get` / `fetch` 必须配 timeout。

### 铁律 2: timeout 后优雅降级
- skip 本轮 polling
- 不报错, 不 abort 全部
- 保留旧 data (复用 W5 T5.4 教训: UI 不闪烁)

## 端到端验证 (W2 报告)

- useKbMonitor 单文件: 3/3 PASS
- Stores + chat composables: 35+9 = 44/44 PASS
- 全 composables + api: 209/209 PASS (vs prior 204, +5 from new tests)
- vite build: 0 错误 (95 modules transformed)

## 5 个新测试 case

### useKbMonitor.test.js (3 case)
1. `写入时自动加 expiresAt = now + 90 天` — 等价逻辑
2. `未过期 → 正常加载`
3. `已过期 → 清 key + 返空`

### chatHistory.api.test.js (2 case)
1. `listMessages timeout: 30000 透传`
2. `fetchSessionFromServer 链路 timeout 一致`

## 相关 memory

- `multi-agent-task-orchestration-baseline.md` — 主指挥协调范式
- `w2-t3-session-polling-audit-2026-07-20.md` (待建) — 审计报告 P2 候选 C
- `chat-share-celery-cleanup-2026-07-20.md` — 同批 P2-A