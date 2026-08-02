# Build determinism investigation memory (2026-08-03)

## Scope

RESEARCH-BUILD-DETERMINISM 调查历史 `f31901caf` 与三次 dist rebuild，补齐类 20.133 永久规则。本任务只修改 `CLAUDE.md`、`docs/`、`memory/`，不改 production runtime、`web/src`、`web/dist` 或 migration。

## 起步物证

- Worktree: `E:/agent-research-build-determinism`
- Branch: `chore/research-build-determinism`
- 起点 `8e54d538d`，`origin/main` 同步，工作树 clean。
- 历史修复：`f31901caf`。
- Rebuild 链：`0b23896da` → `e3aa97b68` → `11d9ca73b`。
- 锁定依赖：Vite `7.3.6`，lockfile Rollup `4.62.3`；Vite 7.3.6 package metadata 兼容 Rollup `^4.43.0`。

## 核心结论

1. Vite 7.3.6 默认没有向 application chunk 注入 build timestamp、PID 或 random ID。
2. Rollup `[hash]` 基于渲染内容、依赖 placeholder 与插件 hash hook 计算；默认没有时间输入。
3. 真正根因是项目 `web/vite.config.js` 的旧实现：`new Date().toISOString()` 与 `Math.random()` 通过 `define` 字面量替换进入 entry chunk，触发依赖图 hash 连锁漂移。
4. 三次 rebuild 的 114 文件变化主要是 self-reference：修复后的 `BUILD_ID` 读取当前 HEAD，每次 dist commit 使 HEAD 改变，下一次 build 为同步内嵌 ID 而改变产物。这不是同一 HEAD 的随机漂移。
5. 当前修复正常 git 路径对同一 HEAD 可确定；但 `safeExec` 无 git fallback 仍为 `unknown-${process.pid}-${Date.now()}`，严格 reproducible build 应改为 CI 固定注入或 fail-loud。
6. 当前 `web/package.json` `build` 尚未显式声明 `NODE_ENV=production`；本任务只沉淀纪律，不擅自修改脚本。Vite mode 与 `process.env.NODE_ENV` 不应混为一谈。

## 18 项反馈摘要

- 历史修复只改 `web/vite.config.js`，define keys 未变，main.js 消费侧未变。
- Vite 源码命中的时间/随机值属于 debug、dotenv tips、依赖优化 temp cache，不是 dist hash 默认输入。
- Rollup 源码的 hash 流程是 render → content/dependency hash → final hash；`hashCharacters: 'hex'` 仅改变编码。
- `process.env` 不是天然不确定；只有未固定且进入产物/插件 hash 的 env 才会破坏复现。当前 `VITE_API_PROXY_TARGET` 只用于 dev proxy。
- 三次 rebuild 各改约 114 个 dist 文件，是 commit ID 自引用链；修复后历史记录的同 HEAD 两次 build 为 255 文件 `diff -r = 0`。
- 永久门禁：`npm ci` + lockfile + 固定 Node/Vite/Rollup；显式 `NODE_ENV=production`；禁止 Date/random/PID/未固定 env 注入；同 source 两次 build 比较清单；无 git 时 CI 固定 metadata 或 fail-loud。

## 本次落地

- `CLAUDE.md` 新增“W100 构建确定性永久纪律（类 20.133）”。
- 新 runbook：`docs/research-build-determinism-2026-08-03.md`，含完整 18 项反馈、源码审计、5 件套、物证和后续留口。
- 本 memory 文件用于索引与跨会话引用。

## 验证与边界

- 本任务未执行 dist rebuild，避免引入 self-reference 新链。
- 本任务未修改 `app/`、`web/src/`、`web/dist/`、`alembic/versions/`。
- 未删除任何 remote ref；`f31901caf`、三个 rebuild commit 与原 memory 物证保留。
- 后续需另起任务处理跨平台显式 NODE_ENV 脚本、无 git fallback 和 CI 双构建 hash gate。

## 关联

- `memory/w100-deploy-determ-2026-08-03.md`
- `docs/research-build-determinism-2026-08-03.md`
- `web/vite.config.js`
- `web/package.json`
- `web/package-lock.json`

## Commit 计划

按派工要求：`[W100 +48] docs(investigation): build non-determinism 调查 + 永久铁律沉淀`。
