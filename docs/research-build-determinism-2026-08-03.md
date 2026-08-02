# Vite 构建非确定性调查（2026-08-03）

## 1. 调查范围与结论

本调查追踪历史修复提交 `f31901caf`（`[DEPLOY-DETERM W100 +32] fix(web/build): vite 构建非确定性修复 + 调查根因 (类 20.133)`），目标是区分：

1. Vite 7.x / Rollup 默认是否自行注入时间、PID 或随机数；
2. 项目配置是否把非确定性值注入了产物；
3. 三次 rebuild 为什么仍产生三个 dist commit；
4. 后续构建是否有可执行的永久确定性门禁。

**结论**：Vite 7.3.6 默认不会把构建时间注入应用 chunk，也没有证据表明 Rollup 的 `[hash]` 计算读取 build time、PID 或随机数。此次漂移的直接根因是项目 `web/vite.config.js` 的 `define` 常量：旧实现使用 `new Date().toISOString()` 和 `Math.random()`，其字面量被替换进 entry chunk，随后 Rollup 对内容及依赖关系重新计算 hash，导致整个 dist 树连锁 rename。历史三次 rebuild 的额外变化来自“每次构建都把当前提交 hash 自引用进产物”的闭环，而不是 Vite 默认非确定性。

## 2. 起步与仓库物证

| 项目 | 实测结果 |
|---|---|
| worktree | `E:/agent-research-build-determinism` |
| 分支 | `chore/research-build-determinism` |
| 起点 | `8e54d538d`，与 `origin/main` 0 ahead / 0 behind |
| 起步状态 | `git fetch origin` 完成，工作树 clean |
| 修复提交 | `f31901caf` |
| 关联 rebuild | `0b23896da`、`e3aa97b68`、`11d9ca73b` |
| Vite | `7.3.6`（`web/package-lock.json`） |
| Rollup lockfile | `4.62.3`（Vite package metadata 声明兼容 `^4.43.0`） |
| 5 件套范围 | 本任务仅 docs/memory/CLAUDE.md；不改 app、web/src、alembic |

## 3. 18 项调查反馈

### 反馈 1：历史修复究竟改了什么
`f31901caf` 只修改 `web/vite.config.js` 与新增历史 memory。旧的两个模块级常量是：

```js
const BUILD_TIMESTAMP = new Date().toISOString()
const BUILD_ID = Math.random().toString(36).slice(2, 8)
```

修复后主路径改为 `git log -1 --format=%cI` 与 `git rev-parse --short HEAD`。

### 反馈 2：旧值是否真的进入最终产物
是。`define` 中的 `__BUILD_TIMESTAMP__` 和 `__BUILD_ID__` 会进行字面量替换；`src/main.js` 消费它们输出 build console 行，并将 build ID 用作 Sentry release。因此改变常量就改变 entry chunk 字节。

### 反馈 3：Vite 7.x 默认是否含时间戳
没有发现。对 Vite 7.3.6 发布包源码审计，时间函数出现在 debug 计时、dotenv tip、依赖优化临时目录等工具路径，不是生产 bundle 内容或默认 chunk hash 输入。

### 反馈 4：Vite 的开发/依赖缓存是否会用时间
会，但这是另一层语义。Vite 依赖优化临时目录后缀使用 PID、时间和随机数，目的是避免并发缓存冲突；它不等于应用 `dist` chunk hash，也不应被误判为生产构建非确定性。

### 反馈 5：Rollup `[hash]` 是否含 build 时间
没有证据支持。Rollup 4.43.0 源码先渲染 chunk，再通过 `transformChunksAndGenerateContentHashes` 基于渲染内容、依赖 placeholder 和插件 `augmentChunkHash` 生成 hash；时间不是默认输入。

### 反馈 6：chunk hash 的实际依赖
`[hash]` 反映 chunk 内容及其依赖关系。入口字节改变会改变入口 hash；引用入口或被入口依赖的 chunk 可能因最终引用替换而连锁重算。因此一处非固定 define 足以造成大量文件 rename。

### 反馈 7：hashCharacters 的作用
项目设置 `hashCharacters: 'hex'` 只改变 hash 字符编码/可读形式，以满足 webhint 的十六进制正则；它不制造也不消除时间随机性。

### 反馈 8：Vite 默认文件名模板
Vite 7.3.6 源码为 worker 等输出使用 `[name]-[hash]` 模式；Vite/Rollup 的默认 hash placeholder 本身是内容导向的。自定义 `manualChunks` 会影响拓扑，但在输入固定时不应引入时间值。

### 反馈 9：是否发现 process ID 注入 chunk
默认 Vite/Rollup 没有。项目旧配置没有直接把 PID 注入正常路径；修复提交新增的异常 fallback 是 `unknown-${process.pid}-${Date.now()}`，这只在 git 命令失败时发生，属于确定性风险留口，不能作为严格 reproducible build 方案。

### 反馈 10：是否发现随机 ID 注入 chunk
默认 Vite/Rollup 没有。项目旧配置明确使用 `Math.random()` 生成 `BUILD_ID`，这是本事故的直接随机源；修复后的正常 git 路径不再随机。

### 反馈 11：是否发现时间戳注入 chunk
默认 Vite/Rollup 没有。项目旧配置明确使用 `new Date()` 生成 `BUILD_TIMESTAMP`；修复后的正常路径从 commit author date 读取固定值。

### 反馈 12：`process.env` 是否天然破坏确定性
不是所有 `process.env` 都破坏确定性，但未经固定的环境值一旦进入 `define`、banner、footer、插件 hash hook 或源码生成，就会改变产物。当前配置的 `VITE_API_PROXY_TARGET` 仅用于 dev server proxy，不属于 build chunk 注入；仍应禁止把任意环境值无审计地注入产物。

### 反馈 13：`NODE_ENV` 与 Vite mode 是否等价
不等价。Vite `vite build` 默认使用 production mode，但 mode 是 Vite 配置/`.env` 选择维度，`process.env.NODE_ENV` 是 Node 环境变量。PostCSS 等依赖会读取 `process.env.NODE_ENV`，因此 build script 必须显式声明它，不能凭默认 mode 推断。

### 反馈 14：现有 build script 是否显式声明 NODE_ENV
当前 `web/package.json` 的 `build` 是 `vite build && node scripts/postbuild-fix-manifest.js`，没有显式 `NODE_ENV=production`。本调查只做文档与纪律沉淀，不擅自修改 script；这是后续兼容 Windows/Unix 的构建脚本加固留口。

### 反馈 15：三次 rebuild 为什么各自产生 114 文件变化
`0b23896da`、`e3aa97b68`、`11d9ca73b` 都重命名约 114 个 dist 文件。修复后每次 commit 自身又改变了 `git rev-parse --short HEAD` 的值；为了让 dist 内嵌 ID 与当前 commit 对齐，只能再 rebuild，于是形成 source commit → dist commit → 新 hash → 下一次 dist commit 的 self-reference 链。

### 反馈 16：self-reference 是否等于非确定性
不等于。对一个固定 git HEAD，修复后的正常路径是确定的；但每新增一个 dist commit，HEAD 变了，输入也合法地变了。它是提交拓扑/发布策略成本，而不是同一 source 的随机漂移。

### 反馈 17：是否有直接的修复后证据
历史 memory 记录修复后两次同 HEAD build 的 `diff -r` 为 0，255 个文件一致，`index-390c2ab8.js` 文件名和 MD5 一致；修复前 `index-27e37c81.js` → `index-c243f137.js` 且约 50 个 chunk rename。该证据支持“配置输入导致漂移”的根因判断。

### 反馈 18：可执行的永久门禁是什么
固定 Node/Vite/Rollup 与 lockfile，使用 `npm ci`；显式声明 `NODE_ENV=production`；禁止时间、随机、PID 和未固定环境值进入产物；同一 source 连续 build 后用 `diff -r` 或文件 hash 清单比较；不同 commit 要确认差异来自预期 source/version 输入；无 `.git` 时必须由 CI 提供固定 build metadata 或 fail-loud，不能静默 PID+时间 fallback。

## 4. 现状 grep 结果

- `web/vite.config.js` 当前正常路径从 git HEAD 派生 build metadata；文件中的 `Date.now()` 只出现在异常 fallback，`Math.random()` 只出现在注释中的旧实现说明。
- `web/vite.config.js` 的 `process.env.VITE_API_PROXY_TARGET` 只配置 dev server `/api` 与 `/ws` proxy，没有进入 `define`。
- `web/scripts/` 没有发现 `Date.now()`、`new Date()`、`Math.random()`、`randomUUID`、PID 或 NODE_ENV 注入模式。
- Vite 7.3.6 源码中命中的时间/随机值属于 debug、dotenv 提示和依赖优化临时目录；Rollup 4.43.0 命中的时间/随机值属于 watch/CLI 辅助路径，不是默认 hash 算法。

## 5. 5 件套守恒

1. **alembic**：本任务不改 migration；沿用当前 main 单 head 基线。
2. **pytest**：本任务不改 Python production/test runtime；不伪造与文档调查无关的测试数字。
3. **PWA/build**：不重建 dist，沿用 `f31901caf` 修复后的 255 文件 `diff -r = 0` 证据；本任务不触碰 `web/src` 或 `web/dist`。
4. **0 production code**：仅修改 `CLAUDE.md`、`docs/`、`memory/`；无 `app/`、`web/src/`、`alembic/versions/` 改动。
5. **锚点**：本提交按派工要求使用 `[W100 +48]`；不删除历史 remote ref，不修改或重建 `f31901caf` 的物证链。

## 6. 永久规则落点

本次将规则写入 `CLAUDE.md` 的“W100 构建确定性永久纪律”段，核心要求是：同一 source 必须同 hash；禁止 process/time/random 注入；显式 NODE_ENV；锁定依赖；异常 fallback fail-loud 或使用 CI 固定值。后续任何 build determinism 事故应引用类 20.133，而不是把 Vite 默认 hash 机制误报为时间驱动。

## 7. 后续留口（不在本任务擅自扩展）

1. 为跨平台显式 `NODE_ENV=production` 增加仓库认可的脚本实现（例如 cross-env 或 Node wrapper），另起变更验证。
2. 将无 `.git` fallback 从 PID+时间改为 CI 注入或 fail-loud。
3. 在 CI 增加两次同 source build 的产物清单比较，并将 Node/npm/lockfile/Vite/Rollup 版本列入日志。
4. 如启用 sourcemap、压缩器或新的 Rollup plugin，必须重新验证 map、banner、footer 和 `augmentChunkHash` 的确定性。

## 8. 关键物证

- `f31901caf`：配置修复与根因说明。
- `0b23896da`：修复后的首次 dist rebuild。
- `e3aa97b68`：self-referencing build ID rebuild。
- `11d9ca73b`：最终 self-referencing rebuild。
- `memory/w100-deploy-determ-2026-08-03.md`：历史修复的完整执行记录。
- `web/vite.config.js`：当前 build metadata 与 define 配置。
- `web/package.json` / `web/package-lock.json`：build script 与依赖锁定物证。
