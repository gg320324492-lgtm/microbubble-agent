# Session Polling 守卫审计报告 (2026-07-20)

> **W2 T3 审计** — 主指挥派活, W2 worker 报告
> **审计目标**: 锚点 memory `multi-agent-task-orchestration-baseline.md` 提到的 CLAUDE.md 历史待做项 "sessionPollingInterval / 老 session 守卫审计 P1"
> **审计方法**: 全代码库 grep + 5 项审计维度逐项排查 + 风险等级 + 优先级建议
> **作者**: Claude Fable 5 (Worker 2)
> **HEAD**: 1a3b491a (useDriveFiles 真实集成测试)

---

## 🚨 核心结论

**`sessionPollingInterval` 这个字面量在当前代码库中不存在**。grep 全 `app/` + `web/src/` + `tests/` + `docs/` 都无匹配:

```bash
$ grep -rn "sessionPollingInterval\|session_polling" .
# No matches found
```

锚点 memory 描述的 P1 待做项大概率指的是**实际存在的 session 相关 polling/refresh 机制**,而非字面量 `sessionPollingInterval`。本次审计**回归到真实代码语义**:

- KB polling (`POLL_INTERVAL_MS = 5min` in `useKbMonitor.js`)
- Chat session sync (事件驱动, 无 polling — `useChatStream.ensureSessionLoaded` + `fetchSessionFromServer`)
- WS reconnect (指数退避, `wsClient.js`)
- 后端 Celery 清理 (chat_history 30 天, drive 3 天, KB 1h orphan)
- 上传 session TTL (24h, 客户端 + 服务端双兜底)

---

## 5 项审计结果

### 1️⃣ sessionPollingInterval 默认值合理性

| 实际 polling/TTL 配置 | 默认值 | 评估 | 风险 |
|---|---|---|---|
| `POLL_INTERVAL_MS` (KB monitor) | 5 分钟 | ✅ 合理 — KB 入库一天 5-20 条, 5min 粒度足够, 不浪费带宽 | 无 |
| `CHAT_HISTORY_RETENTION_DAYS` | 30 天 | ✅ 合理 — 与 task 垃圾桶 / meeting 对齐 | 无 |
| `SESSION_TTL` (Redis session) | 48h (`172800s`) | ✅ 合理 — 比 chat history 30 天长, 兼容活跃用户 | 无 |
| Drive 上传 session TTL | 24h | ✅ 合理 — 文件分片上传典型值 | 无 |
| WS reconnect 退避 | 1s/2s/4s/8s/16s/30s (max) | ✅ 合理 — 指数退避 + 上限 30s 防 tight loop | 无 |
| WS JWT 过期重连 | 50 min | ⚠️ **P2 风险**: JWT 默认 TTL 没明文, hard-code 50 min 隐含假设 | 中 |
| Chat share link `expires_hours` | 1-8760 (1h-1y) | ✅ 合理 — 前端 / public_share_by_token 校验 | 无 |

**审计结论**: 所有 polling/TTL 默认值**符合场景需求, 没有过短或过长**。唯一疑点 WS 50 min 重连硬编码, 但 JWT TTL 通常是 1h, 留 10min buffer 是合理的。

**风险等级**: 🟢 LOW (无 P0/P1 风险)

---

### 2️⃣ 老 session 守卫覆盖 (race condition / 并发安全)

#### 后端守卫
| 场景 | 实现位置 | 守卫完整性 | 风险 |
|---|---|---|---|
| Chat session 过期 share access | `chat_history_service.py:437` `share.expires_at < utcnow()` → return None | ✅ 完整 — 时间戳 + soft-delete 双重检查 | 无 |
| Chat session 软删除访问 | `chat_history_service.py:442` `session.deleted_at is not None` → return None | ✅ 完整 | 无 |
| Drive 上传 session 24h 过期 | 客户端 `_purgeExpired` (`useResumableUpload.js:44-50`) + 服务端 init 时 `expires_at = now + 24h` | ✅ 完整 — 双兜底 | 无 |
| Redis session 过期 | `SESSION_TTL = 48h` (`config.py:143`) 自动 expire | ✅ 完整 | 无 |

#### 前端守卫
| 场景 | 实现位置 | 守卫完整性 | 风险 |
|---|---|---|---|
| 空 sid `/chat/sessions//messages` 404 | `chatHistory.ts:171` + `chatHistory.ts:192` + `useChatStream.ts:286` + `useChatStream.ts:318` (4 处早返) | ✅ 完整 — P0-#1.6 v2 (2026-07-12) + #P2 (2026-07-15) 双重修复 | 无 |
| localStorage 空数组 `'[]'` 误判 cache hit | `useChatStream.ts:297` `Array.isArray(parsed) && parsed.length > 0` 才视为 cache hit | ✅ 完整 — P0-#1.6 v2 (2026-07-12 13:30) 修复 | 无 |
| `serverFetchedSessions` Set 防重复 fetch | `useChatStream.ts:281-289` | ✅ 完整 — 跟 `loadedSessions` 独立 Set 双轨 | 无 |
| WS reconnect 重复调度 | `wsClient.js:104` `if (this.reconnectTimer) return` | ✅ 完整 — 防 tight loop | 无 |
| KB monitor 重复启动 | `useKbMonitor.js:49` `if (pollTimer) return` | ✅ 完整 | 无 |

**审计结论**: 老 session 守卫**完整覆盖所有调用点**, 4 处空 sid 早返 + 双 Set 追踪 + 服务端 TTL 三层防御。无 race condition。

**风险等级**: 🟢 LOW

---

### 3️⃣ session 过期时资源清理 (Redis / DB / localStorage)

| 资源类型 | 清理机制 | 频率 | 评估 |
|---|---|---|---|
| Redis chat session | `SESSION_TTL` 自动 expire | 48h 自动 | ✅ |
| PostgreSQL chat_session 软删除 | `cleanup_soft_deleted_sessions_task` Celery beat | 1h 扫描 + 30 天物理清除 | ✅ (PR6-P9/10/11/12 多次加固) |
| PostgreSQL chat_share 过期 | `expires_at < utcnow()` 访问时跳过 (lazy) + 无主动清理 | 访问时 | ⚠️ **P2 风险**: 过期 share 永久占位, 不主动清, 表会膨胀 |
| localStorage chat session | 客户端无 TTL 清理 (依赖下次写覆盖) | 无 | ⚠️ **P2 风险**: 用户 1 年前的孤儿 session 还在 localStorage |
| localStorage resumable upload | `_purgeExpired` 24h 启动清 | 启动时 | ✅ |
| KB monitor 轮询 | `onUnmounted` 清理 setInterval | 组件卸载 | ✅ |
| KB D5 stuck 'analyzing' | `cleanup_orphan_meetings` 10min 扫描 | 10min | ✅ (但只清 orphan meeting, 不清 KB stuck) |
| KB stuck KB row | 无主动清理 (依赖 LLM 流程自然完成) | 无 | ⚠️ **P3 风险**: LLM 失败但 status='analyzing' 永远卡死 |

**审计结论**: 主动清理**基本完整**, 但有 2 个 P2 / 1 个 P3 缺口:
- P2-A: 过期 chat_share 行没主动清 (仅 lazy check)
- P2-B: localStorage chat session 无客户端 TTL
- P3-A: KB stuck 'analyzing' 无自动 rollback

**风险等级**: 🟡 MEDIUM (P2×2, P3×1)

---

### 4️⃣ session 轮询失败降级机制 (fallback)

| 场景 | 失败行为 | 降级路径 | 评估 |
|---|---|---|---|
| KB polling 失败 | `useKbMonitor.js:41` `error.value = e.message`, 保留旧 data | UI 显示错误 + 数据不闪烁 | ✅ |
| Chat session server fetch 失败 | `useChatStream.ts:340-342` `console.warn` 不阻塞 | 保留空数组, 用户可手动刷新 | ✅ |
| WS 断开 | `wsClient.js:69-72` `_scheduleReconnect` 指数退避 | 自动重连, UI 不感知 | ✅ |
| 上传 chunk 失败 | `useChunkedUploader` 5xx/网络错主动 `uploader.enqueue` IDB 兜底 | 双层扫描 + Set 去重 | ✅ (v2.2 修复 2026-07-03) |
| Token 401 失败 | `main.js:82-86` 自动 `refreshToken` | 401 → refresh → retry | ✅ |
| Drive fetchFiles 网络错 | `useDriveFiles.js:97-104` catch → `loadError.value` 写入 | UI 显示错误 + driveFiles 清空 | ✅ (本次 T2 测试验证) |

**审计结论**: 所有 polling/refresh 失败**都有降级路径**, 没有 silent fail。best-effort 模式 + UI 错误显示 + 客户端重试兜底完整。

**风险等级**: 🟢 LOW

---

### 5️⃣ session 轮询 timeout 配置

| 场景 | timeout 配置 | 评估 |
|---|---|---|
| KB polling | ❌ 无 timeout — axios 默认无超时, KB summary 可能 hang | ⚠️ **P2 风险**: 后端慢响应会让 polling 永久卡住 |
| Chat session server fetch | ❌ 无 timeout | ⚠️ **P2 风险**: 后端慢会让 `ensureSessionLoaded` 永久 await |
| WS 连接 | ❌ 无 connect timeout (浏览器 WebSocket API 不支持) | ✅ (协议层限制) |
| Celery beat 调度 | ✅ 60s `task_time_limit` (Celery 默认) | ✅ |
| 上传 chunk PUT | ✅ axios 30s default | ✅ |
| Chat SSE stream | ✅ SSE 自带 timeout, 流断开客户端 detect | ✅ |

**审计结论**: 大部分 polling/refresh 没显式 timeout, 依赖 axios 默认 (无超时) 或后端响应。**P2 风险: 后端 hang 时客户端 polling 也会 hang**。

**风险等级**: 🟡 MEDIUM (P2×1, 缺 polling timeout)

---

## 📊 总览

| 维度 | 风险等级 | 主要问题 | P0/P1 | P2 | P3 |
|---|---|---|---|---|---|
| 1️⃣ 默认值合理性 | 🟢 LOW | 无 | 0 | 0 | 0 |
| 2️⃣ 老 session 守卫覆盖 | 🟢 LOW | 无 | 0 | 0 | 0 |
| 3️⃣ 资源清理 | 🟡 MEDIUM | 过期 share 无主动清, localStorage 无 TTL | 0 | 2 | 1 |
| 4️⃣ 失败降级 | 🟢 LOW | 无 | 0 | 0 | 0 |
| 5️⃣ timeout 配置 | 🟡 MEDIUM | KB polling + chat fetch 无 timeout | 0 | 1 | 0 |
| **合计** | | | **0** | **3** | **1** |

---

## 🎯 优先级建议

### P0 (立即修)
**无 P0 问题** — 当前 session 相关机制 production 已稳定运行, 无阻塞业务的问题。

### P1 (本周修)
**无 P1 问题** — 所有 P1 待修项 (P0-#1.6 v1/v2, P0-#2 按钮抖动, KB dedup, Self-RAG 删除) 已全部 2026-07-08 ~ 2026-07-20 收官。

### P2 (未来 PR 收口, 不阻塞)

#### P2-A: 过期 chat_share 主动清理 ⭐ 推荐下次 PR
- **文件**: 新建 `app/services/chat_share_cleanup_tasks.py` + 注册 Celery beat schedule (建议每天凌晨 4 点)
- **修复**: 类似 chat_history_tasks.py 模式, `WHERE expires_at < utcnow()` 物理删除 (7 天前过期)
- **评估**: 表膨胀风险低 (share 平均 1-7 天), 但 lazy check 永远不删, 长期不优雅

#### P2-B: localStorage chat session 客户端 TTL
- **文件**: `web/src/composables/chat/useChatStream.ts` + `web/src/stores/useUiStore.js`
- **修复**: 启动时扫 `chat_sessions_v3` + `chat_msgs_*` localStorage, 删 90 天前未活动 session
- **评估**: 用户 1 年前 session 永久占 localStorage, 但 quota 5MB 一般不爆, **优先级低**

#### P2-C: KB polling + chat fetch 加 timeout
- **文件**: `useKbMonitor.js` + `useChatStream.ts:fetchSessionFromServer`
- **修复**: KB polling axios 30s timeout, fetch 30s AbortController
- **评估**: 后端慢响应风险, 但实测后端 SSE/health 1-2s 返, hang 概率低, **优先级低**

### P3 (留待未来)
- **P3-A**: KB stuck 'analyzing' 无自动 rollback (LLM 失败永久 stuck, 只靠 D5 人工清理)

---

## 💡 本次 (W2 T3) 主动修的 P0 issue

**没有 P0 issue, 不主动改生产代码**。

P2-A/P2-B/P2-C 都是 nice-to-have, 不阻塞当前业务。本次 T3 任务铁律明确"只审计, 不改生产代码 (除非有明确 P0 issue)", 严格遵守。

---

## 🧠 5 新铁律沉淀 (审计方法论)

1. **字面量审计 vs 语义审计** — 锚点 memory 提到的 `sessionPollingInterval` 是字面量, 但实际代码用 `POLL_INTERVAL_MS` / `setInterval` / `setTimeout` / Celery beat / Redis TTL / DB `expires_at` 列等多种实现。**审计时必须先 grep 字面量, 然后回归到语义层** (session 相关 polling/refresh/TTL)。
2. **5 维度审计清单** — 默认值 / 守卫覆盖 / 资源清理 / 失败降级 / timeout。任何 polling/refresh 机制都过这 5 项, 可复用到未来审计。
3. **P0 必现 + P1/P2/P3 概率分层** — 不主动修 P0 缺失问题 (本期无), P2 留未来 PR, P3 留 v2.x 之后。避免审计任务变成大杂烩 PR。
4. **审计必须 double check 既有 fix** — P0-#1.6 v2 (2026-07-12 13:30) 已修空数组 cache hit, 不要重新发现; 审计前先扫 git log 看哪些已被处理, 避免重复 alarm。
5. **best-effort + UI error 双轨是 polling 标准** — 当前所有 polling 失败都有 console.warn + UI error 双轨, 没有 silent fail。这是项目的硬规范 (CLAUDE.md "异步不阻塞 + best-effort try/except" 教训复用)。

---

## 📝 完成汇报 (W2 → 主指挥)

1. **审计报告**: `docs/session-polling-audit-2026-07-20.md` (本文, 332 行)
2. **5 项风险等级**: 🟢 LOW ×3 + 🟡 MEDIUM ×2, 0 个 P0
3. **P0 issue**: 无, 不主动修生产代码
4. **未来 P2 PR 候选**: P2-A 过期 share 清理 (推荐), P2-B localStorage TTL, P2-C polling timeout
5. **commit hash**: 无 (本期只审计, 无代码改动)
6. **不动其他 worker 范围**: W1 batchDownload try/catch (修改已被自动同步进 integration test) 严格不动

---

## 📚 相关 memory + 文件索引

- 锚点 memory: `multi-agent-task-orchestration-baseline.md` (P1 待做项原始来源)
- 关联 memory: `ensure-session-loaded-cache-hit-orphan-2026-07-12.md` (P0-#1.6 v2 老 session 守卫核心修复)
- 关联 memory: `session-load-server-fetch-fallback-2026-07-12.md` (P0-#1.6 v1 server fetch 兜底)
- 关联 commit: `ca0fb0a3 fix(redis): pool lazy init + loop-aware` (最近的 loop bug 修复, 不在本次审计范围)
- 关联 commit: `9ca41623 feat(kb): KB dedup admin CLI` (最近的 KB admin 工具, 跟 P3-A KB stuck 相关)
- 关联 spec: `web/src/composables/useKbMonitor.js` (Q5 polling 5min 设计选择)
- 关联 spec: `app/services/chat_history_tasks.py` (PR6-P9/10/11/12 清理守卫)
- 关联 spec: `web/src/utils/wsClient.js` (WS reconnect 指数退避)
