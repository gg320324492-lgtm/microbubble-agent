---
name: session-polling-audit-2026-07-20
description: sessionPollingInterval 守卫审计 + 5 项审计 + P2 候选清单
metadata: 
  node_type: memory
  type: project
  originSessionId: 0f277dd1-0a27-4a11-b320-da966057abae
  modified: 2026-07-20T12:55:22.161Z
---

# Session Polling 守卫审计 (2026-07-20)

## TL;DR

🎯 **sessionPollingInterval 守卫审计 P1 待做完成** — 锚点 memory CLAUDE.md 提到的历史 P1 待做项, 本次审计回归到真实代码语义, 给出 5 项审计 + P2 候选清单 (A/B/C, 全部在 2026-07-20 当日完成)。

**Why**: 锚点 memory 描述的 `sessionPollingInterval` 字面量在代码库 0 匹配, 但相关 session polling/refresh/TTL 机制分散存在, 值得系统性审计。

**How to apply**: 见下方 5 项审计结果 + P2 候选清单 + 5 新铁律。

## 核心发现

**`sessionPollingInterval` 字面量在当前代码库中不存在**。

```bash
$ grep -rn "sessionPollingInterval\|session_polling" .
# No matches found
```

锚点 memory 描述的 P1 待做项大概率指**实际存在的 session 相关 polling/refresh 机制**, 而非字面量。本次审计**回归到真实代码语义**:

- KB polling (`POLL_INTERVAL_MS = 5min` in `useKbMonitor.js`)
- Chat session sync (事件驱动, 无 polling — `useChatStream.ensureSessionLoaded` + `fetchSessionFromServer`)
- WS reconnect (指数退避, `wsClient.js`)
- 后端 Celery 清理 (chat_history 30 天, drive 3 天, KB 1h orphan)
- 上传 session TTL (24h, 客户端 + 服务端双兜底)

## 5 项审计结果

### 1. sessionPollingInterval 默认值是否合理
- **🟢 LOW**: KB polling 5min 合理, chat session 事件驱动无 polling, WS reconnect 指数退避

### 2. 老 session 守卫是否覆盖所有调用点
- **🟢 LOW**: chat_history 30 天清理 + drive 3 天清理 + KB 1h orphan 三层覆盖
- localStorage chat session 90 天 TTL 修复后 (P2-B) 完整闭环

### 3. session 过期时是否清理后端资源
- **🟡 MEDIUM**: chat_share 24h TTL 依赖 Redis 过期, 无主动清理 → **P2-A 修复**

### 4. session 轮询失败时是否降级
- **🟡 MEDIUM**: KB polling 无 timeout → **P2-C 修复**

### 5. session 轮询 timeout 配置
- **🟢 LOW**: chatHistory 已有部分 timeout, KB polling 缺 → **P2-C 修复覆盖**

**总览**: 0 P0 / 0 P1 / 3 P2 / 1 P3

## P2 候选清单 (全部在 2026-07-20 完成)

### P2-A: 过期 chat_share 主动清理 Celery beat
- **commit**: `a37ef09b feat(chat-share): Celery beat 主动清理过期 share`
- **文件**: `app/services/chat_share_tasks.py` (新) + `app/core/celery.py` (改) + `tests/test_chat_share_cleanup.py` (新)
- **测试**: 8/8 PASS

### P2-B: localStorage chat session 客户端 90 天 TTL
- **commit**: `1a0ecbed feat(chat): localStorage chat session 90 天 TTL 防御 (W2 T3 P2-B)`
- **文件**: `web/src/stores/chatSessions.ts` (改) + `web/src/stores/__tests__/chatSessions.test.js` (改)
- **测试**: 20/20 PASS (13 旧 + 7 新)

### P2-C: KB polling + chat fetch 30s timeout
- **commit**: `f3e637cf feat(config): KB polling + chat fetch 30s timeout 防御 (P2-C)`
- **文件**: `web/src/composables/useKbMonitor.js` + `web/src/api/chatHistory.js` + 2 测试
- **测试**: 3+31+9 = 43 PASS

## 5 新铁律 (W2 T3 沉淀)

1. **锚点 memory 描述有时不准确** — `sessionPollingInterval` 字面量在代码库不存在
2. **审计应回归到真实代码语义** — 不盲从 memory 字面量, grep 验证后再下结论
3. **memory 写"待做项"应描述代码语义而非字面量** — 避免语义漂移导致审计失效
4. **5 项审计清单是 polling/refresh/TTL 审计标准** — 默认值 / 守卫覆盖 / 资源清理 / 失败降级 / timeout
5. **P2 候选清单闭环是 audit 报告价值体现** — 不只列问题, 给修复路径 + commit hash

## 实施细节说明

### P2-A 核心: where_clause 必须 IS NOT NULL 守卫
```python
where_clause = and_(
    ChatShare.expires_at.isnot(None),  # NULL = 永不过期业务语义
    ChatShare.expires_at < now()
)
```
漏守卫直接删永久链接 = 数据丢失事故。

### P2-B 核心: lazy migration + 真删 localStorage key
```ts
// 写入时自动加 expiresAt
const payload = { sessions, currentId, expiresAt: Date.now() + 90 * 24 * 60 * 60 * 1000 }

// 读取时检查 TTL + 清 3 key (sessions + current + legacy)
if (!parsed.expiresAt || parsed.expiresAt < Date.now()) {
  localStorage.removeItem(newKey)
  localStorage.removeItem(STORAGE_KEY_BASE)
  localStorage.removeItem(userKey(CURRENT_KEY_BASE, userId))
  return { sessions: [], currentId: null }
}
```

### P2-C 核心: axios timeout 比 AbortController 简单
```js
const res = await axios.get(url, { timeout: 30 * 1000 })  // 自动 reject with ECONNABORTED
```
- 进 catch 后保留旧 data (复用 W5 T5.4 教训)
- 不引入新常量在 composable 层 (T4 范围紧凑)

## 相关 memory

- `multi-agent-task-orchestration-baseline.md` — 主指挥协调范式
- `chat-share-celery-cleanup-2026-07-20.md` — P2-A
- `kb-and-chat-timeout-2026-07-20.md` — P2-C
- `localstorage-chat-session-ttl-2026-07-20.md` — P2-B