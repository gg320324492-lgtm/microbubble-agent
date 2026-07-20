---
name: localstorage-chat-session-ttl-2026-07-20
description: localStorage chat session 客户端 90 天 TTL + lazy migration + 4 新铁律
metadata: 
  node_type: memory
  type: project
  originSessionId: 0f277dd1-0a27-4a11-b320-da966057abae
  modified: 2026-07-20T12:55:22.148Z
---

# LocalStorage Chat Session 90 天 TTL (2026-07-20)

## TL;DR

🎯 **localStorage chat session 客户端 90 天 TTL 防御** — P2 候选清单最后一项收尾, P2-A/B/C 三件套 100% 完成。

**Why**: W2 T3 审计报告 P2 候选 B — localStorage chat session 客户端无 TTL 清理, 可能无限累积, 占用 storage + 影响 list 性能。

**How to apply**: 见下方 lazy migration 实现 + 4 新铁律 + 大事故恢复 (rm -rf web/dist) 教训。

## 核心实现 (W1 P2-B)

### chatSessions.ts (loadFromStorage + saveToStorage)
```ts
// 写入时自动加 expiresAt = now + 90 天
function saveToStorage(sessions: any[], currentId: string | null) {
  const payload = {
    sessions,
    currentId,
    expiresAt: Date.now() + 90 * 24 * 60 * 60 * 1000  // 90 天后过期
  }
  localStorage.setItem(key, JSON.stringify(payload))
}

// 读取时检查 TTL + 清掉过期 key (3 key 全清)
function loadFromStorage() {
  const raw = localStorage.getItem(newKey) || localStorage.getItem(STORAGE_KEY_BASE)
  if (!raw) return { sessions: [], currentId: null }
  const parsed = JSON.parse(raw)
  // 关键: legacy 无 expiresAt 视为过期 (lazy migration 触发)
  if (!parsed.expiresAt || parsed.expiresAt < Date.now()) {
    localStorage.removeItem(newKey)
    localStorage.removeItem(STORAGE_KEY_BASE)
    localStorage.removeItem(userKey(CURRENT_KEY_BASE, userId))
    return { sessions: [], currentId: null }
  }
  return { sessions: parsed.sessions, currentId: parsed.currentId }
}
```

### scope 选择
**只给 sessions list 加 TTL** (顶层 `expiresAt` 字段),**不给 per-session messages 加** (`chat_msgs_<id>`):
- per-session messages 由 server 持久化兜底 (已 sync)
- 误清 messages 是用户看到空对话, 不是只丢元数据
- **收益小、风险大**

## 4 新铁律

### 铁律 1: localStorage TTL 必须 lazy migration + 过期清 key
- legacy 无 expiresAt 视为过期
- 避免"旧数据永不清理"导致 list 累积
- 用户首次刷新页面 → 视为过期 → 清 key → UI 空状态 → 立即 mergeServerList 从 server 拉 → 用户体验几乎无感知

### 铁律 2: 过期 cleanup 必须真删 localStorage key
- 不能仅内存清, 否则下次冷启动又扫一次
- `removeItem` 必须成对 (sessions + current + legacy)

### 铁律 3: 契约漂移测试必须主动更新
- 加新功能让原断言失败时, 修测试而不是绕测试
- 同 `config-value-contract-regression-2026-07-20.md` 教训

### 铁律 4: web/dist 是 force-tracked 资产 — 严禁 rm -rf web/dist
- `rm -rf web/dist` 触发 214 文件 D 状态 (已 tracked)
- 必须 `git checkout -- web/dist` 恢复
- 跟 CLAUDE.md 7/11 PWA manifest 410 铁律对齐 (force-add 是历史事故)

## 端到端验证 (W1 报告)

- chatSessions 单文件: 20/20 PASS (13 旧 + 7 新)
- Stores 跨文件: 35/35 PASS
- Chat composables: 9/9 PASS
- vite build sanity: 0 错误

## 7 新 vitest case (覆盖完整 TTL 契约)

1. `写入时自动加 expiresAt = now + 90 天`
2. `未过期 (expiresAt > now) → 正常加载`
3. **核心: 已过期 → 清 key + 返空**
4. `legacy 数据无 expiresAt → 视为过期 (向后兼容)`
5. `非 namespace legacy key 过期 → 也清掉`
6. `P0-#1.6 兼容: legacy 空数组占位 → 视为过期`
7. `过期 cleanup 后 createSession 立即写新 expiresAt`

## 更新 1 个过期契约测试

`falls back to legacy non-namespaced key`:
- 原断言: `sessions.length === 1` (无 TTL 概念)
- 新断言: `sessions.length === 0` (P2-B 修复后, legacy 视为过期)
- 注释明确写 "W2 T3 P2-B 修复后契约已变"

## 大事故恢复教训

W1 worker 误执行 `rm -rf web/dist` (本地测试用) → git status 显示 214 文件 D 状态 (因为 dist 是 force-tracked 历史资产) → 立即 `git checkout -- web/dist` 恢复。

**未来铁律**: 任何本地测试用 `rm -rf web/dist` 必须先 `git ls-files web/dist | head` 验证是否是 tracked, 决定用什么方式清理。

## 部署影响

- 用户首次刷新页面 → loadFromStorage 看到 legacy 无 expiresAt → 视为过期 → 清 key + 返空 → UI 显示空状态 + 立即 mergeServerList 从 server 拉
- 用户活跃期间 → 新写入自动带 expiresAt, 90 天后自动清

## P2 候选清单 3/3 全部完成

| 候选 | commit | 状态 |
|---|---|---|
| P2-A 过期 chat_share Celery 清理 | `a37ef09b` | ✅ |
| P2-B localStorage chat session 90 天 TTL | `1a0ecbed` | ✅ |
| P2-C KB polling + chat fetch 30s timeout | `f3e637cf` | ✅ |

## 相关 memory

- `multi-agent-task-orchestration-baseline.md` — 主指挥协调范式
- `chat-share-celery-cleanup-2026-07-20.md` — P2-A
- `kb-and-chat-timeout-2026-07-20.md` — P2-C
- `w2-t3-session-polling-audit-2026-07-20.md` (待建) — 审计报告 P2 候选 B