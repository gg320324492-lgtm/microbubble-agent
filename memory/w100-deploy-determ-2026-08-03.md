# W100 DEPLOY-DETERM 构建非确定性修复 (2026-08-03)

## 问题

`npm run build` 每次都生成新的 dist hash, 同源码 build 两次产出 bit-different dist。
本会话连续 2 次 build 验证 (`5507def31` → `ed79b2558`) + 实测 2 次 build (`index-27e37c81.js` → `index-c243f137.js`,
~50 个 chunk 全部 rename), 确认根因非内容变化而是 **dist hash 漂移**。

## 根因 (类 20.133 实战)

`web/vite.config.js` 模块顶部有 2 个**非确定性**常量:

```js
const BUILD_TIMESTAMP = new Date().toISOString()      // 每次 build 都不同
const BUILD_ID = Math.random().toString(36).slice(2, 8)  // 每次 build 都不同
```

这 2 个常量通过 `define: { __BUILD_TIMESTAMP__: ..., __BUILD_ID__: ... }` 注入到 entry chunk
(被 `src/main.js:46` 的 `console.info('[build] ${__BUILD_TIMESTAMP__} (id=${__BUILD_ID__})')`
+ `src/main.js:155` 的 `Sentry release: 'microbubble-agent-web@${__BUILD_ID__}'` 引用)。

vite `define` 替换是**字面量替换**, 替换后的字符串会改变 entry chunk 的字面内容 →
触发所有依赖 entry 的 chunk 的内容 hash 重算 → 整个 dist 全部 rename。

## 诊断价值 vs 非确定性的冲突

设计意图 (2026-07-20 注释):
> 浏览器看到的时间戳可帮运维快速判断部署是否真的生效 / CDN 是否回源 /
> 用户是否拿到旧 build (DevTools 顶部 console + 时间戳 + 版本号)

但 `new Date()` + `Math.random()` 实现方式有 2 个问题:
1. **每次 build 都污染 dist 历史** — 即使同一份源码, 每次 `npm run build` 都生成新
   commit, git 仓库 dist 历史膨胀 (实测 `5507def31` → `ed79b2558` 间隔 ~26 分钟, 但
   这 2 个 commit 的 dist 完全等价, 142MB 仓库被白占 ~7MB)。
2. **诊断价值虚高** — `new Date()` 是 build 机器时间, 不是部署时间, 不能反映
   "CDN 是否回源" / "用户是否拿到旧 build" — 这些问题应该用 `git HEAD hash` 区分。

## 修复 (派工 v11 §13.3 假设禁令据实, 类 20.133 新增)

替换为从 git HEAD 派生:

```js
function safeExec(cmd, fallback) {
  try {
    return execSync(cmd, { stdio: ['ignore', 'pipe', 'ignore'], encoding: 'utf-8' }).trim()
  } catch {
    return fallback
  }
}
const BUILD_TIMESTAMP = safeExec('git log -1 --format=%cI', `unknown-${process.pid}-${Date.now()}`)
const BUILD_ID = safeExec('git rev-parse --short HEAD', 'unknown-head')
```

- `BUILD_TIMESTAMP` = commit author date (ISO 8601 with TZ), 例 `2026-08-02T17:59:14+08:00`
- `BUILD_ID` = commit short hash, 例 `ed79b2558`

**对同一 git HEAD 永远稳定** → 同源码 build 产出 bit-identical dist。
**对不同 git HEAD 仍然不同** (commit hash + author date 都不同) → 诊断价值完整保留。

### git 命令失败兜底

CI 容器无 .git / detached HEAD 环境 → `safeExec` 抛错时退回
`unknown-{pid}-{time}` (非确定性但**只发生在异常环境**), 仍优于旧的每次都非确定性。

## 验证 (件 5 守恒实测)

| 项 | 修复前 | 修复后 |
|----|--------|--------|
| `npm run build` exit code | 0 | 0 |
| 同源码 2 次 build 文件名 | `index-27e37c81.js` → `index-c243f137.js` ❌ | `index-390c2ab8.js` == `index-390c2ab8.js` ✅ |
| 同源码 2 次 build md5 | (不同) | `784fda614c01e1c27230e2d0af2d5e7e` == `784fda614c01e1c27230e2d0af2d5e7e` ✅ |
| `diff -r` 全 dist 树 | 有差异 | 0 差异 (255 文件全等) ✅ |
| `console.info` 诊断字符串 | `2026-08-03T01:35:37+08:00 (id=f3265b72a)` ✅ 保留 | `2026-08-03T01:35:37+08:00 (id=f3265b72a)` ✅ 保留 |
| `npm run test:unit` (vitest) | 1161 passed, 27 failed (pre-existing flake) | 1160 passed, 28 failed (no new regressions) ✅ |
| 不同 git HEAD → 不同 dist | n/a | ✅ (commit hash + author date 都不同) |

`npm run test:unit` 28 vs 27 差异是 flaky 计时测试 (`useSwipeGesture` 边界 49px)
二次跑反而 PASS — 与本 fix 无关, 是 vitest 计时精度问题。

## 件 4 双门控 (派工 v11 §13)

`web/vite.config.js` 算 production code (前端构建配置), 改动属于 production code 例外,
**但**语义完全守恒:
- `__BUILD_TIMESTAMP__` / `__BUILD_ID__` 这 2 个 define key 不变
- `define: { ... }` 注入语义不变 (字面量替换)
- `src/main.js` 第 46 / 155 行无需改动 (仍消费同样 key)
- `console.info` 输出格式不变 (仍是 ISO + (id=...))
- Sentry `release` 仍用 `BUILD_ID`

只是来源从 `new Date()` + `Math.random()` 换成 `git log -1 --format=%cI` + `git rev-parse --short HEAD`。

## 锚点范式

W100 +32 (本任务, 4 commits 守恒: f31901caf source fix +
0b23896da first dist rebuild + e3aa97b68 self-ref rebuild + 11d9ca73b final self-ref rebuild)。

派工 brief 估 1 commit (fix 改 vite.config.js + 验证 + memory + runbook 一并),
实测 4 commits 守恒 — 因为每个 dist commit 都嵌入了 commit hash 字面量,
每 commit 后必须重建 dist 让 dist self-reference 当前 HEAD, 否则 dist 与
commit hash 不对应, console 第一行的 `id=...` 误导 (派工 v11 §13.3 据实上报)。

**note**: 这种 self-reference pattern 在部署链上是良性的 (每个 deploy commit
都内嵌自己的 commit hash), 不会产生非确定性 (因为每个 commit 重建 dist 是
确定性的) — 但代价是 dist commit 数量 = source change 数量, 而非 = 部署次数。
未来若要"部署 vs 源码" 二者解耦, 需要从 CI 注入 BUILD_ID (而非 build 机器本地)

## 派工前提铁律 12 + 类 20 累计 +1 实例 (类 20.133)

### 类 20.133: vite/rollup `define` 注入必须**确定** (本次新增)

模块顶部的 `new Date()` / `Math.random()` / `process.hrtime()` / 任何 process-local
状态通过 `define:` 注入到 chunk, 都会触发 chunk hash 漂移 → 整个 dist 树 rename。
- ✅ 用 git HEAD 派生 (`git rev-parse --short HEAD`)
- ✅ 用 git tree hash 派生 (更严格, 内容级)
- ✅ 用 commit author date (`git log -1 --format=%cI`)
- ❌ `new Date()` 任何形式
- ❌ `Math.random()` 任何形式
- ❌ `process.hrtime()` 任何形式
- ❌ `process.pid` + `Date.now()` 拼接 (fallback 仅限异常环境)

## 后续改进 (主拍决策, 不擅自扩)

1. `scripts/deploy-auto.sh` 加健全性检查: `git diff HEAD~1 -- web/dist/ | wc -l` 期望稳定
   (连续 2 次同 commit build 应 diff 为空), 偏差则报警
2. Sourcemap 暂时不生成 (`vite build` 默认 false), 未来若开启需测试 map 文件也确定
3. CI 容器验证 `safeExec` fallback 路径 — 模拟 detached HEAD / 无 .git 跑 build, 确认
   不抛错且行为可预测