---
name: w71-route-71st-batch-a2-prompt-v7
description: "W71 batch A-2 派工纪要 v7 (锚点范式第 193 守恒) — v6 → v7 升级链路: 段 5 6→9 项必填 (+浏览器状态轨迹 +PWA & SW 副作用 +runtime 心跳 3 项) + 段 7 5→10 类派工前提错误 (+W68 H-1 setInterval +H-2/H-3 nginx 410 +H-4 checkSwBlacklist +H-5 heartbeat 5 类) + 段 3 新增前端任务 5 hot-fix 链路 + 段 4 新增 grep + console 噪声策略 + 段 6 三段串联 (alembic + dist rebuild + nginx reload). W71st batch 实战 5 hot-fix (commits 49ebe9b33/3207aea62/72eaae07f/ff9b6b3e2/960f8abe1/85619c012) 暴露 v6 对前端/浏览器层派工前提 0 覆盖, v7 必含. 派工纪要本身纯 docs, 0 production code 改动铁律维持. 派工前提 5/5 守恒. 1 commit defer."
metadata:
  node_type: memory
  type: project
  originSessionId: W71st-batch-A-2
  modified: 2026-07-24T00:00:00.000Z
---

# W71st batch A-2: 派工纪要 v7 (W71 实战反馈: H-1/H-2/H-3/H-4/H-5 五次 hot-fix 新纪律, 锚点范式第 193 守恒, 2026-07-24/27)

> 派工纪要 v7 是 v6 的纯增量升级 (派工 v7 第 4 条铁律: 不动 v1-v6 历史约束). 仅升级段 3/4/5/6/7, 段 1/段 2/段 8 全文不变.

## 1. v6 → v7 升级链路 (6 段联动)

- **段 3** (前置验证/门禁): 在 v6 "其他任务" 前新增 "前端任务 5 hot-fix 链路检查" + "PWA / SW 状态检查" 两类实战检查. 派工 prompt 若涉及前端, 必显式写明"先确认 5 hot-fix 是否全在基线"
- **段 4** (完成定义/PS 5.1): 在 v6 "未完成项写 BLOCKED" 前新增 "web 改动必 grep 验证" + "runtime 心跳 / console 噪声策略" 两类实战约束
- **段 5** (反馈循环): v6 6 项必填 → **v7 9 项必填**, 新增 3 项实战信号: 浏览器状态轨迹 (主指挥 console 仍刷啥) / PWA & SW 副作用 (PWA 禁用四步做了几个) / runtime 心跳 (timer 句柄存哪里 console 删没删)
- **段 6** (合并顺序表): 在 v6 表格前新增 "实战 5 hot-fix 必含三段串联" 段 (alembic + dist rebuild + nginx reload)
- **段 7** (派工前提错误): v6 5 大类 → **v7 10 大类**, 新增 5 类前端/浏览器派工前提 (W68 H-1~H-5 沉淀): 浏览器老 SW cache 强制清 / PWA 永久禁用四步 / checkSwBlacklist self-loop 删除 / setInterval timer 句柄 / heartbeat 静默策略
- **段 1/段 2/段 8** (兼容矩阵 + 自检清单 + 升级路径): 段 1/段 2 完全沿用 v6 原文 (派工纪要 v7 第 7 条铁律)

## 2. 派工纪要 v7 8 条新铁律 (派工纪要 v7 §5)

1. **段 5 反馈必填 9 项** (v6 升级) — agent 完工回传必须含段 5 v7 9 项, 否则视为"完工未达标"
2. **段 6 合并顺序表必含三段串联** (v6 升级) — alembic 串单链 + web dist rebuild + nginx reload, 三段必含
3. **v7 默认应用从 W71 batch 开始** — W71 及以后必须用 v7, W73 调研任务必须用 v7
4. **段 7 派工前提错误必含 10 大类** — v6 5 类 + v7 5 类, 任何派工必含
5. **PWA 永久禁用必走四步** (v7 新增) — vite-plugin-pwa disable + main.js 顶部 unregister + nginx 3 server block 410 + postbuild 兼容 sw.js 缺失
6. **checkSwBlacklist 这类 self-loop check 必整段删** (v7 新增) — 函数定义 + 调用方 + 常量一起 if(false) 包裹或彻底删除
7. **setInterval / setTimeout 必存 timer 句柄 + onUnmounted 清理** (v7 新增) — timer 存 ref + 组件 unmount 时 clearInterval, 避免 Dashboard 时钟 / 通知 polling 泄漏
8. **heartbeat / setTimeout 警告按主指挥策略执行** (v7 新增) — 保留 timer 重置逻辑 (避免 W68 H-5 heartbeat 循环 bug), console 警告按"完全静默 / 降为 info / 保留 warn"调整

## 3. W68 第 14 批 H-1~H-5 五次 hot-fix 实战沉淀 (派工纪要 v7 §4 + §7)

| hot-fix | commit | 锚点 | 根因 | v7 升级方式 |
|---|---|---|---|---|
| **H-1** | `49ebe9b33` + `3207aea62` | 187 | Dashboard setInterval timer 未存句柄 / 401 拦截器删 token 触发循环 / 通知 polling 无 30s 限流 | 段 3 + 段 4 + 段 7 新增类 4 |
| **H-2** | `72eaae07f` | 188 | nginx `/sw.js` 仅 `add_header Cache-Control no-store` 不 `return 410` / vite-plugin-pwa 未 disable | 段 3 + 段 7 新增类 1-2 |
| **H-3** | `ff9b6b3e2` | 189 | main.js 缺顶部同步 unregister + 清 Cache Storage | 段 7 新增类 1 (浏览器老 SW cache 强制清) |
| **H-4** | `960f8abe1` | 190 | checkSwBlacklist fetch + r.text() 持续调用, 函数定义未 if(false) 包裹 | 段 7 新增类 3 (checkSwBlacklist self-loop 删除) |
| **H-5** | `85619c012` | 191 | console.warn heartbeat 噪声, 主指挥要求静默但保留 timer 重置 | 段 4 + 段 5 + 段 7 新增类 5 (heartbeat 静默策略) |

## 4. 派工前提错误复盘 (派工纪要 v7 段 7, 24h 内必填)

- **必先 commit partial diff** (派工 v6 第 1 条铁律): ✅ 派工前 `git status --short` 干净 (0 changes)
- **不动 v1-v6 历史约束** (派工 v6 第 4 条铁律): ✅ 段 1/段 2 全文沿用 v6, 仅升级段 3/4/5/6/7
- **段 5 必含 W71 实战新发现** (派工 v6 第 4 条铁律): ✅ 段 5 9 项必填含 3 项 v7 实战信号
- **0 production code 改动铁律** (派工 v6 永久): ✅ 本任务纯 docs/memory, 0 production code 改动
- **1 commit + defer message**: ✅ 1 commit `docs(w71st-batch-a2): ...`

## 5. 沉淀位置

- **派工纪要 v7 文档**: `docs/w71-dispatch-candidates-v7-2026-07-24.md` (~445 行, 含 v6→v7 diff 详表 + 段级 diff + 8 条新铁律 + 完整兼容矩阵)
- **派工纪要 v7 memory**: 本文件 (~80 行, 锚点范式第 193 守恒)
- **派工纪要 v6 文档** (历史参考): `docs/w68-dispatch-candidates-v6-2026-07-24.md` (~365 行)
- **W68 H-1~H-5 五次 hot-fix memory**:
  - `memory/w68-route-14-hotfix-b1-2026-07-24.md` (B-1 续实施 文件秒传 锚点 185)
  - H-1: dashboard setInterval timer leak (commit `49ebe9b33` 锚点 187) — 暂无单独 memory file
  - H-2: nginx 410 + vite-plugin-pwa disable (commit `72eaae07f` 锚点 188)
  - H-3: main.js 顶部 unregister + Cache Storage (commit `ff9b6b3e2` 锚点 189)
  - H-4: checkSwBlacklist self-loop 删除 (commit `960f8abe1` 锚点 190)
  - H-5: heartbeat console.warn 静默 (commit `85619c012` 锚点 191)

## 6. 不要做的事 (本次守住)

- ❌ 不动 production code (web/src Vue / app/ FastAPI / alembic/versions) — 本任务纯 docs/memory
- ❌ 不删 v6 任何段原文 (派工纪要 v7 第 4 条铁律)
- ❌ 不在 main 工作 — 本任务在 worktree `E:/microbubble-agent/.worktrees/agent-w71st-a2-prompt-v7`
- ❌ 不拆 source/dist (本任务无 dist 改动)
- ❌ 不删 timer 重置逻辑 (H-5 教训, 派工纪要 v7 第 8 条铁律)
- ❌ 不 `vite build` 直跑 (无 web 改动, 即使有也禁止)

## 7. 锚点范式

锚点范式单调上升: W7 12 → ... → W68 第 14 批 191 (H-5) → **W71st batch A-2 v7 沉淀后预测 193** (2 守恒, 本任务 A-2 仅 1 锚点 + 派工 v6 沉淀的实际锚点跃迁)

**Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>**
