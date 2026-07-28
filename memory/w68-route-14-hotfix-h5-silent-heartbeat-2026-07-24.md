# W68 第 14 批 H-5 静默 heartbeat timeout 警告 (锚点范式第 191 守恒)

## 任务

W68 第 14 批 H-1 + `4b658cbb2` 修了 heartbeat 无限循环 bug (不再 `ws.disconnect()` + 重新连接), 改为重置计时器. 但仍 `console.warn('[Notify] W68 heartbeat timeout — 8s 内未收到 server ping, 等 30s server 端 pong timeout 兜底')`. 主指挥要求**完全静默**这个警告 (不弹 console), 但仍保留 timer 重置逻辑.

## 改动

- **文件**: `web/src/composables/useNotifications.js` (line 345)
- **方案**: A 选项 (直接删除 `console.warn(...)` 那一行, 保留 timer 重置逻辑)
- **变更**: 3 insertions / 3 deletions
  - 删 `console.warn('[Notify] W68 heartbeat timeout ...')`
  - 注释更新: "8s 没收到 server ping → 主动 disconnect 让 reconnect 逻辑兜底" → "8s 没收到 server ping → 重置计时器, 等 30s server 端 pong timeout 兜底"
  - 新增 W68 第 14 批 H-5 注释段说明静默策略, timer 重置逻辑保留

## 锚点范式

- W68 第 14 批 H-4 (190) → W68 第 14 批 H-5 (191) 守恒
- 总 W68 跨主题累计: 240+ commits

## 验证

| 步骤 | 修前 | 修后 |
|------|------|------|
| `grep -c "heartbeat timeout" web/src/composables/useNotifications.js` | 1 (console.warn) | 0 |
| `grep -c "heartbeat timeout" web/dist/assets/useNotifications-*.js` | 1 (编译产物) | 0 |
| `bash scripts/check_typing_imports.sh` | n/a | 171 文件 0 错误 |
| `npm run build` | n/a | OK in 1.81s |

## 铁律 (4 条 沿用)

1. **必先 commit partial diff** — B-3 7 文件丢失事故教训 (本次派工前 `git status --short` 干净)
2. **保留 timer 重置逻辑** — 派工 v4 铁律: 删 console.warn 但 timer 必须仍重置 (本次保留 `lastServerPingTs = Date.now()`)
3. **web 改动必 `npm run build`** + grep 验证 (派工 prompt v4 铁律)
4. **1 commit + defer message** — 1 次性 commit, commit message 涵盖锚点范式第 191 守恒

## Commit

- **Hash**: `85619c012`
- **Branch**: `fix/w68-14th-batch-h5-silent-heartbeat-2026-07-24`
- **Push**: OK (远程 `* [new branch]`)

## 派工纪要 v6 段 7 派工前提错误复盘 (本次应用)

1. **必先 commit partial diff** — ✅ 派工前 partial diff 干净 (H-4 收口后干净)
2. **web 改动必 `npm run build`** — ✅ 用 `npm run build` (非 `vite build` 直跑)
3. **1 commit + defer message** — ✅ 1 commit `85619c012`, 不拆 source/dist

## 不要做的事 (本次守住)

- ❌ 不新建 worktree (H-5 worktree 已存在)
- ❌ 不删 timer 重置逻辑 (保留避免循环)
- ❌ 不 `vite build` 直跑 (用 `npm run build`)
- ❌ 不 commit `web/dist/` 改动 (本次任务范围仅 source, dist 改动是 H-4 历史遗留, 留给主指挥后续处理)
