import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve, join } from 'path'
import { readdirSync, lstatSync, readFileSync } from 'fs'
import { createHash } from 'crypto'
import { execSync } from 'child_process'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import NutUIResolver from '@nutui/nutui/dist/resolver'
import { VitePWA } from 'vite-plugin-pwa'

// ============================================================
// 2026-10-07 [DEPLOY-DETERM / R-5] BUILD_TIMESTAMP / BUILD_ID 派生根治 (类 20.133)
//
// 旧实现 (2026-08-03 首版, 2026-09-16 修过随机兜底后仍在用):
//   BUILD_TIMESTAMP = `git log -1 --format=%cI`      (HEAD 的提交时间)
//   BUILD_ID        = `git rev-parse --short HEAD`   (HEAD 短哈希)
// 二者随**任何** commit 变化 —— 纯 docs commit 也变 → vite define 注入 entry chunk
// → banner 字节变 → 按依赖图 ~190 个 chunk 级联 rename → 入库的 web/dist (部署契约,
// 365 tracked) 每次重建都与仓库对不上。收尾规划 R-5 / §3.5 据此根治。
//
// 新实现: 双字段都从「构建的真实源输入」派生, 与 HEAD / docs / dist 提交彻底解耦:
//   BUILD_TIMESTAMP = `git log -1 --format=%cI -- <SOURCE_INPUTS>`
//       语义 = **最后一次触碰构建源输入的提交的 committer 时间** (ISO 8601 含时区)。
//       **不是**构建时刻、**不是** HEAD 时间 —— 源输入不动 (docs / 测试 / 其他模块
//       commit / dist 入库) 它就不变; 只有 src/index.html/lockfile/vite 配置等被提交
//       才推进。console banner 里它是"源码最后修改时间"。
//   BUILD_ID = sha256(源输入文件清单 [相对路径 + '\0' + 字节内容]) 前 12 hex
//       语义 = 构建源内容指纹。内容变 (含未提交的工作区改动) 才变;
//       提交 dist / docs / 其他目录 → 内容不变 → 不变。
//
// 反循环论证 (为什么显式允许清单、而不是把 git tree 喂进哈希):
//   web/dist 自身入库且在 web/ 树内 —— 任何把含 dist 的树喂进哈希的方案
//   (git rev-parse HEAD^{tree} / ls-tree web / 对 web/ 目录求哈希) 都会:
//   提交 dist → 树变 → ID 变 → banner 变 → chunk 级联 rename → 下次提交又变,
//   永不收敛。因此派生输入 = 显式**允许清单** SOURCE_INPUTS (不含 dist),
//   从磁盘读字节, dist 物理上不可能进入哈希输入。
//
// 为什么用「工作区内容哈希」而不是「HEAD tree hash」:
//   若按 HEAD 派生, 提交前构建 = 拿旧 HEAD 的 ID 给新源码产物 → 提交后重建又对不上,
//   等于把 R-5 缩小到"每个源码提交"而不是根治。工作区内容哈希忠实反映真实输入:
//   同内容 = 同 ID (含未提交改动), ID 部分对任意时刻的构建都成立。
//   ⚠️ 但 BUILD_TIMESTAMP 取 path-log (历史), **原子 src+dist 提交会让 timestamp 滞后
//   一个源提交** (构建时 path-log = 旧源提交; 在新提交上重建 path-log = 新提交自己)
//   → 该提交上重建 ≠ 入库 dist (banner 时间差 → 级联 rename)。因此入库顺序纪律:
//   **源输入改动先提交, 再 `npm run build`, 再提 dist** —— e50631024 实战: config
//   提交前在克隆里构建, timestamp 滞后 20 分钟, 195 文件重建修正。
//   dist-only / docs 提交不推进 path-log → 在 dist 提交上重建恒等于入库 dist (R-5 主验收)。
//
// fail-loud (类 20.133「异常 fallback 必须 fail-loud 或确定」), 按 build/dev 分模式:
//   - git 不可用 (无 .git / 非 git 检出 / PATH 缺 git / 容器内 git 不可用):
//     `vite build` → 直接 throw; dev → 固定哨兵 'no-git-dev' (确定值; playwright.yml
//     视觉回归的 visual-vite 容器 git 不可用, 曾被无差别 throw 误杀 —— 2026-10-07 修);
//   - `vite build` 且 git log 对源输入返回空 (浅克隆未含源路径历史) → throw,
//     绝不产出浅克隆时间戳的 dist;
//   - dev / CI dev-server (playwright.yml 的 `npx vite` 是 actions/checkout 默认
//     depth=1 浅克隆, tip 常为 dist-only/docs-only 提交, 不在 SOURCE_INPUTS 里) →
//     确定性降级为 tip 提交时间 (dev 产物不入库), 仅 warn —— 属「fail-loud 或确定」
//     的「确定」分支, 同时保证 CI dev server 不被打断;
//   理由: CI 实测从不跑 vite build (视觉/无障碍走 dev server, lint-css 只 lint),
//   dist 只在维护者本机构建 (恒有完整 .git) → 构建 fail-loud 现实成本为零;
//   未来 CI 若要跑 build, 按本条由 CI **显式固定输入** (而非随机兜底), 届时再加。
//
// 明确不做 (类 20.133 红线): 不读 Date.now / new Date / process.env / process.pid /
// Math.random; 不加静默兜底值; 不用裸 `vite build` (npm run build 是唯一合法命令)。
// ============================================================

const WEB_ROOT = __dirname

// 构建源输入允许清单 (相对 web/)。判据 = 该文件的字节能改变 `npm run build` 产物:
//   - src/ index.html public/            vite 打包图 + 静态拷贝
//   - vite.config.js                     构建配置本体 (define/patch/postcss/manualChunks)
//   - package.json / package-lock.json   依赖锁定版本 (npm ci 安装的 node_modules 代理)
//   - scripts/postbuild-fix-manifest.js  npm run build 命令链的后半段
// 明确**不**入清单 (别加):
//   - dist/                    自身入库, 入清单即哈希循环 (见上方反循环论证)
//   - src/**/__tests__/, *.test.* / *.spec.* — vitest 用, 不进 build 产物
//   - .stylelintrc.json / .hintrc.json / playwright*.config.js / vitest.config.js /
//     tests/ / tools/ / design-showcase/ / Dockerfile / nginx.conf
//                              lint / 测试 / 部署面, 不参与 build
const SOURCE_INPUTS = [
  'index.html',
  'package.json',
  'package-lock.json',
  'public',
  'scripts/postbuild-fix-manifest.js',
  'src',
  'vite.config.js',
]

// git 调用: 任何失败 → throw (fail-loud)。禁止在这里加兜底值。
function gitOrDie(cmd) {
  try {
    return execSync(cmd, {
      stdio: ['ignore', 'pipe', 'ignore'],
      encoding: 'utf-8',
      cwd: WEB_ROOT,
    }).trim()
  } catch (err) {
    throw new Error(
      `[vite] 构建标识派生失败: \`${cmd}\` 执行失败 (${String(err.message).split('\n')[0]})。\n` +
      '[vite] 按类 20.133 (W100 构建确定性纪律) fail-loud: 无 .git / 非 git 检出 / ' +
      'PATH 缺 git / 浅克隆缺源路径历史时, 构建必须显式失败, ' +
      '禁止静默退回随机或进程态标识产出 dist。' +
      '修复: 在完整 git 仓库内运行 npm run build。'
    )
  }
}

// 源输入里不参与构建产物的路径 (即使它在允许清单目录下):
//   __tests__ / *.test.* / *.spec.*  vitest 用例
//   .DS_Store / Thumbs.db / desktop.ini  编辑器/系统垃圾 (误入会让 ID 随机器漂移)
function isNonBuildInput(relPath) {
  const segs = relPath.split('/')
  if (segs.includes('__tests__')) return true
  if (/\.(test|spec)\.[cm]?[jt]sx?$/.test(relPath)) return true
  if (segs.some((s) => s === '.DS_Store' || s === 'Thumbs.db' || s === 'desktop.ini')) return true
  return false
}

function collectSourceFiles(absDir, relBase, out) {
  // readdirSync(...).sort(): 默认 UTF-16 码元序, 与 locale 无关 → 跨机器顺序稳定
  for (const name of readdirSync(absDir).sort()) {
    const abs = join(absDir, name)
    const rel = relBase ? `${relBase}/${name}` : name
    if (isNonBuildInput(rel)) continue
    const st = lstatSync(abs)
    if (st.isDirectory()) collectSourceFiles(abs, rel, out)
    else if (st.isFile()) out.push({ rel, abs })  // 符号链接跳过 (Windows/本仓库无)
  }
}

// 内容指纹: sha256(排序后的 [rel + '\0' + bytes + '\0'] 流) 前 12 hex。
// 只读 SOURCE_INPUTS, 不碰 dist → 与 dist 提交次数、与 HEAD 全部解耦。
function deriveSourceTreeHash() {
  const files = []
  for (const input of SOURCE_INPUTS) {
    const abs = join(WEB_ROOT, input)
    let st
    try {
      st = lstatSync(abs)
    } catch {
      throw new Error(`[vite] 构建源输入缺失: web/${input} — 源输入清单与仓库不符, fail-loud (类 20.133)`)
    }
    if (st.isDirectory()) collectSourceFiles(abs, input, files)
    else if (st.isFile()) files.push({ rel: input, abs })
  }
  // 最终按相对路径全序排序 (码元比较, 不用 localeCompare —— locale 依赖排序不稳定)
  files.sort((a, b) => (a.rel < b.rel ? -1 : a.rel > b.rel ? 1 : 0))
  if (files.length === 0) {
    throw new Error('[vite] 构建源输入清单收集到 0 个文件 — fail-loud (类 20.133)')
  }
  const hash = createHash('sha256')
  for (const { rel, abs } of files) {
    hash.update(rel, 'utf8')
    hash.update('\0')
    hash.update(readFileSync(abs))
    hash.update('\0')
  }
  return hash.digest('hex').slice(0, 12)
}

// 构建模式判定: `vite build` 的 argv 含 'build'; dev/serve/preview/vitest 不含。
const IS_VITE_BUILD = process.argv.includes('build')

// --- git 可用性预检 (分模式) ---
//   build: 不可用 → throw fail-loud (验收铁律: 无 .git 跑 build 必须报错退出,
//          绝不产出兜底标识 dist);
//   dev:   不可用 → 固定哨兵 'no-git-dev' (确定值, 非随机/进程态, 属类 20.133
//          「fail-loud 或确定」的「确定」分支)。场景: playwright.yml 视觉回归 job 的
//          `docker run visual-vite` 挂载了 checkout (-v $PWD:/app) 但容器内 git 不可用
//          (pinned 镜像无 git / dubious ownership), 2026-10-07 曾被无差别 fail-loud
//          误杀。dev 产物不入库, 哨兵不会进入 dist; BUILD_ID 是内容哈希, 无 git 也照算。
let _gitTop = null
try {
  _gitTop = execSync('git rev-parse --show-toplevel', {
    stdio: ['ignore', 'pipe', 'ignore'],
    encoding: 'utf-8',
    cwd: WEB_ROOT,
  }).trim()
} catch (err) {
  _gitTop = null
  if (IS_VITE_BUILD) {
    throw new Error(
      `[vite] 构建标识派生失败: \`git rev-parse --show-toplevel\` 执行失败 (${String(err.message).split('\n')[0]})。\n` +
      '[vite] 按类 20.133 (W100 构建确定性纪律) fail-loud: 无 .git / 非 git 检出 / ' +
      'PATH 缺 git 时, 构建必须显式失败, 禁止静默退回随机或进程态标识产出 dist。' +
      '修复: 在完整 git 仓库内运行 npm run build。'
    )
  }
}

// --- BUILD_TIMESTAMP: 最后一次触碰源输入的提交时间 (语义见顶部注释) ---
let BUILD_TIMESTAMP
if (!_gitTop) {
  // dev 且无可用 git: 固定哨兵, 确定性 (见上方分模式说明)
  console.warn(
    "[vite] 无可用 git (容器 dev?), BUILD_TIMESTAMP 固定哨兵 'no-git-dev' " +
    '(确定值, 仅 dev 可见, 不会进入入库 dist); BUILD_ID 仍为源输入内容哈希'
  )
  BUILD_TIMESTAMP = 'no-git-dev'
} else {
  BUILD_TIMESTAMP = gitOrDie(`git log -1 --format=%cI -- ${SOURCE_INPUTS.join(' ')}`)
  if (!BUILD_TIMESTAMP) {
    // 源输入路径在可见历史里无提交 —— 典型场景: actions/checkout 默认 depth=1 浅克隆,
    // tip 是 dist-only / docs-only / workflow-only 提交 (这些都不在 SOURCE_INPUTS 里)。
    if (IS_VITE_BUILD) {
      // 构建模式 fail-loud: 入库 dist 的 TIMESTAMP 必须是真实的源输入提交时间,
      // 浅克隆拿不到就绝不产出 (CI 实测从不跑 vite build → 现实零成本)。
      throw new Error(
        '[vite] git log 对源输入路径返回空 (浅克隆未含源输入历史 / 路径从未提交?) — ' +
        '按类 20.133 fail-loud, 不产出兜底标识 dist。修复: 用完整克隆 (git fetch --unshallow) 运行 npm run build。'
      )
    }
    // dev / CI dev-server (playwright.yml 的 `npx vite`, 浅克隆 depth=1): 确定性降级。
    // dev 产物不入库, banner 值仅本机可见; 用 tip 提交时间 (浅克隆内可用, 同 checkout 恒定)
    // —— 确定性值, 不是随机/进程态, 满足类 20.133「fail-loud 或确定」的「确定」分支。
    const _tipDate = gitOrDie('git log -1 --format=%cI')
    if (!_tipDate) {
      throw new Error('[vite] 仓库无任何提交历史, BUILD_TIMESTAMP 无法派生 — fail-loud (类 20.133)')
    }
    console.warn(
      `[vite] 源输入 git log 为空 (浅克隆 depth=1 且 tip 未触碰源输入?), ` +
      `BUILD_TIMESTAMP 确定性降级为 tip 提交时间 ${_tipDate} (仅 dev 可见, 不会进入入库 dist)`
    )
    BUILD_TIMESTAMP = _tipDate
  }
}

// --- BUILD_ID: 源输入内容指纹 (语义见顶部注释) ---
const BUILD_ID = deriveSourceTreeHash()

console.log(`[vite] BUILD_ID=${BUILD_ID} BUILD_TIMESTAMP=${BUILD_TIMESTAMP} (source-derived, 反循环: dist 不入哈希)`)

// webhint cache-busting 修复：vite-plugin-pwa 输出的 manifest.webmanifest
// 不参与 Vite rollup hash 流程，文件名固定 → webhint cache-busting 永远报警告。
// 修复路径：**完全在 postbuild Node 脚本里处理** (`scripts/postbuild-fix-manifest.js`)。
// Vite plugin (`manifestHashPlugin`) 2026-07-10 已删除，原因：
//   1. setImmediate + 100ms×20 重试是脆弱时序竞态 — vite-plugin-pwa 内部用
//      workbox-build 异步生成 sw.js，写盘时机跟 Vite plugin 钩子不同步，
//      极个别 build 会出现 sw.js 已被 patch 但又被覆写回旧 URL 的情况。
//   2. `npm run build` 末尾的 && 链 `vite build && node scripts/postbuild-fix-manifest.js`
//      postbuild 跑在 vite 进程退出**之后**，是独立 Node 进程，对 sw.js 的改写
//      不可能被 Vite plugin 钩子再覆写，更可靠。
// 任何走 `vite build`（绕开 postbuild）的 build 都会被 `scripts/deploy-auto.sh`
// 的健全性检查拦下，提示重跑 `npm run build`。

// Vue 3.5 'bum' null 解构 bug patch（已确认 3.5.34 / 3.5.38 都没修）
// renderer.ts unmountComponent 函数签名：
//   const unmountComponent = (instance, parentSuspense, doRemove) => {
//     if (__DEV__ && instance.type.__hmrId) { unregisterHMR(instance) }
//     const { bum, scope, job, subTree, um, m, a } = instance  // ← instance === null 时爆！
// 触发链路：EP 内部 el-table 子组件递归 unmount → 某子 vnode.component 已是 null →
//   vnode.type.remove(...) → unmountComponent(null) → 'Cannot destructure bum of null'
// 修复：在 esm-bundler.js 顶部注入一行 if (!instance) return; 守卫
// 只影响 build 产物（dev mode 不修，因为 dev 调试需要看原始报错定位应用层 bug）
const VUE_BUM_NULL_PATCH = '/* patch:vue-3.5-bum-null */ if (!instance) return;'

// EP useOrderedChildren.removeChild null guard patch（2026-06-18 实战教训）
// 触发链：el-tab-pane / el-table-column 等注册到父 el-tabs / el-table 的 pane，
//   父组件先 unmount → parentNode 被 detach → childNode.parentNode 变 null
//   → nodesMap.get(null) 返回 undefined → childNodes.indexOf(childNode) 爆
//   → 'Cannot read properties of undefined (reading indexOf)' at unregisterPane
// 修复：在 removeChild 拿到 childNodes 后立刻 return，不要 splice
// 触发页（高频）：AgentTracesView（19 el-table）/ TaskTrash（18）/ MeetingDetailView（el-tabs lazy）
//   / KnowledgeView（4 tab lazy）/ SpeakerMappingPanel（8）/ VoiceprintEnrollDialog（el-tabs lazy）
// 只影响 build 产物（dev mode 不修），与 VUE_BUM_NULL_PATCH 同款策略
const EP_UNREGISTER_PANE_NULL_PATCH = '/* patch:ep-unregister-pane-null */ if (!childNodes) return;'
function vueBumNullPatchPlugin() {
  return {
    name: 'vue-bum-null-patch',
    // enforce:'pre' 让 transform 在其他插件前跑（确保 patch 在 esbuild 处理前生效）
    enforce: 'pre',
    transform(code, id) {
      // 只 patch @vue/runtime-core 的 esm-bundler 入口（build 时 Vite 会加载这个）
      if (!/node_modules\/@vue\/runtime-core\/dist\/runtime-core\.esm-bundler\.js$/.test(id)) {
        return null
      }
      // 防御性：检查是否已 patch（避免重复）
      if (code.includes('/* patch:vue-3.5-bum-null */')) {
        return null
      }
      // 定位 unmountComponent 函数体
      // esm-bundler.js 是 minified-ish（变量短但结构保留），用正则匹配
      const pattern = /(const\s+unmountComponent\s*=\s*\([^)]*\)\s*=>\s*\{)/
      const match = code.match(pattern)
      if (!match) {
        // 文件结构变了，patch 失败（升级 Vue 后要重新适配）
        console.warn('[vue-bum-null-patch] unmountComponent pattern not found, skipped')
        return null
      }
      // 在函数体开头插入 null guard
      const patched = code.replace(pattern, `$1\n    ${VUE_BUM_NULL_PATCH}`)
      console.log('[vue-bum-null-patch] applied to', id)
      return {
        code: patched,
        map: null,
      }
    },
  }
}

// EP useOrderedChildren.removeChild null guard（防 el-tabs/el-table 父组件先 unmount 后
// 子 pane 调 unregisterPane 拿不到 nodesMap entry 而 indexOf undefined 崩溃）。
// patch 目标：node_modules/element-plus/es/hooks/use-ordered-children/index.mjs
// pattern 唯一性：`nodesMap.get(parentNode)` 后紧跟 `childNodes.indexOf(childNode)`，
// 该组合在 EP 其他文件无重复出现（只有 useOrderedChildren 用 WeakMap(parentNode)）
function epUnregisterPaneNullPatchPlugin() {
  return {
    name: 'ep-unregister-pane-null-patch',
    enforce: 'pre',
    transform(code, id) {
      // 只 patch useOrderedChildren 的源码模块
      if (!/node_modules\/element-plus\/es\/hooks\/use-ordered-children\/index\.mjs$/.test(id)) {
        return null
      }
      // 防御性：检查是否已 patch
      if (code.includes('/* patch:ep-unregister-pane-null */')) {
        return null
      }
      // 定位 removeChild 函数体内 nodesMap.get(parentNode) → childNodes.indexOf(childNode) 链路
      // 源码原样（保留 tab 缩进）：
      //   const childNodes = nodesMap.get(parentNode);
      //   const index = childNodes.indexOf(childNode);
      const pattern = /(const childNodes = nodesMap\.get\(parentNode\);\s*\n\s*const index = childNodes\.indexOf)/
      const match = code.match(pattern)
      if (!match) {
        // EP 升级后源码结构变了，patch 失效（升级后要重新适配）
        console.warn('[ep-unregister-pane-null-patch] pattern not found, skipped (EP version may have changed)')
        return null
      }
      // 在 childNodes.indexOf 之前插入 null guard
      // 格式：拿不到 childNodes 说明 parentNode 没在 nodesMap 注册过（父组件已 unmount），
      // 直接 return 不再做 splice（WeakMap 用 null 作 key 会丢，仅 delete children.value 已足够清理）
      const patched = code.replace(
        pattern,
        `const childNodes = nodesMap.get(parentNode);\n\t\t\t${EP_UNREGISTER_PANE_NULL_PATCH}\n\t\t\tconst index = childNodes.indexOf`
      )
      console.log('[ep-unregister-pane-null-patch] applied to', id)
      return {
        code: patched,
        map: null,
      }
    },
  }
}

// zrender wheel/touchstart/touchmove listener 缺 {passive:false} 导致 preventDefault 被拒
// （"Unable to preventDefault inside passive event listener invocation" 警告刷屏）。
// 根因：zrender 5.6.1 / 6.x 的 HandlerProxy.js:236 mountSingleDOMEventListener 调用
// addEventListener(..., opt) 时 opt=undefined，modern Chromium 把 wheel/touchstart
// 默认当 passive:true 处理。当 ECharts RoamController 处理滚轮 zoom 调
// eventTool.stop(e.event) → e.preventDefault() 时被浏览器拒绝 + 打印警告。
// 修复：在 build 阶段 transform HandlerProxy.js，给 wheel/mousewheel/touchstart/
// touchmove 这 4 个 nativeEventName 显式传 {passive:false}，浏览器从此允许
// preventDefault()。功能完全不变（zoom 仍工作，只是 prevDefault 不再被拒）。
// 已对比 echarts 5.6.0 / 6.1.0 tarball，zrender HandlerProxy.js 完全一致，6.x 也没修。
// 因此升级 echarts 主版本无法解决，必须在 build 产物层 patch。
// 与 vueBumNullPatchPlugin / epUnregisterPaneNullPatchPlugin 同款"上游已知 bug 但未修"策略。
// 升级 zrender 后若上游修了（pattern miss），console.warn '[zrender-passive-wheel-patch]
// pattern not found, skipped (zrender version may have changed)'，届时删除本 plugin。
function zrenderPassiveWheelPatchPlugin() {
  return {
    name: 'zrender-passive-wheel-patch',
    enforce: 'pre',
    transform(code, id) {
      // 只 patch zrender 的 HandlerProxy.js（lib/ 或 es/ 都兼容；当前 5.6.1 用 lib/）
      if (!/node_modules\/zrender\/(lib|es)\/dom\/HandlerProxy\.js$/.test(id)) {
        return null
      }
      // 防重复 patch
      if (code.includes('/* patch:zrender-passive-wheel */')) {
        return null
      }
      // 定位 addEventListener 调用 + 函数声明
      // zrender 5.6.1 / 6.x 源码结构：
      //   function mountSingleDOMEventListener(scope, nativeEventName, listener, opt) {
      //     scope.mounted[nativeEventName] = listener;
      //     scope.listenerOpts[nativeEventName] = opt;
      //     addEventListener(scope.domTarget, nativeEventName, listener, opt);
      //   }
      const callPattern = /addEventListener\(scope\.domTarget,\s*nativeEventName,\s*listener,\s*opt\);/
      const callMatch = code.match(callPattern)
      if (!callMatch) {
        console.warn('[zrender-passive-wheel-patch] pattern not found, skipped (zrender version may have changed)')
        return null
      }
      // 注入：把 addEventListener 第 4 个参数 opt 替换为 _patchedOpt，并在前面声明。
      // _patchedOpt 在 nativeEventName 是 wheel/mousewheel/touchstart/touchmove 时
      // 合并 {passive:false}（保留 opt 已有字段如 capture:true）
      const patched = code.replace(
        callPattern,
        `var _patchedOpt = (nativeEventName === 'wheel' || nativeEventName === 'mousewheel' || nativeEventName === 'touchstart' || nativeEventName === 'touchmove') ? Object.assign({ passive: false }, opt || {}) : opt; /* patch:zrender-passive-wheel */ addEventListener(scope.domTarget, nativeEventName, listener, _patchedOpt);`
      )
      console.log('[zrender-passive-wheel-patch] applied to', id)
      return {
        code: patched,
        map: null,
      }
    },
  }
}

// PostCSS 插件：剥离 -moz-appearance（webhint: 应使用标准 appearance，已有 CSS 覆盖补全）
const stripMozAppearance = {
  postcssPlugin: 'strip-moz-appearance',
  Declaration(decl) {
    if (decl.prop === '-moz-appearance') {
      decl.remove()
    }
  }
}
// PostCSS 插件：剥离 scrollbar-width（webhint: Safari 不支持，已有 -webkit-scrollbar 回退）
const stripScrollbarWidth = {
  postcssPlugin: 'strip-scrollbar-width',
  Declaration(decl) {
    if (decl.prop === 'scrollbar-width') {
      decl.remove()
    }
  }
}
// PostCSS 插件：剥离 Element Plus 进度条 keyframes（已用 mb-* 前缀 GPU 版替代）
const stripEpProgressKeyframes = {
  postcssPlugin: 'strip-ep-progress-keyframes',
  AtRule(atRule) {
    if (atRule.name === 'keyframes' &&
        /^(progress|striped-flow|indeterminate)$/.test(atRule.params)) {
      atRule.remove()
    }
  }
}

export default defineConfig({
  plugins: [
    vue(),
    Components({
      // 桌面端 Element Plus（el- 前缀）+ 移动端 NutUI 4（nut- 前缀）
      // 类名前缀不冲突，按需导入各自独立 chunk
      resolvers: [
        ElementPlusResolver({ importStyle: 'css' }),
        // NutUI 4 用预编译 CSS（避免 SCSS 变量作用域问题）
        // 主题色通过 nutui-theme.scss 顶部全局 CSS 变量覆盖（nut- 组件 CSS 用 var()）
        NutUIResolver({ importStyle: 'css' }),
      ],
      dts: false,  // 不生成类型声明文件
    }),

    // PR #9: PWA 配置
    // - registerType: 'autoUpdate' 自动更新（新版本部署后下次访问自动应用）
    // - strategies: 'injectManifest' 自定义 SW（src/sw.js），修复 generateSW 模式
    //   下 navigateFallback 把 offline.html 当 SPA shell 永远返回的 bug
    // - injectRegister: null → 不自动注入 /registerSW.js，改在 main.js 用
    //   useRegisterSW Vue composable 注册，避免 webhint 报 registerSW.js 缺 cache-busting
    // - manifest: 应用元信息（添加到桌面用），文件名带 hash 由上面 manifestHashPlugin 处理
    VitePWA({
      disable: true,  // W68 第 14 批 H-3: 强制禁用 PWA (主指挥浏览器老 SW 仍 active 致持续刷新)
      registerType: 'autoUpdate',
      injectRegister: null,
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.js',
      manifest: {
        name: '微纳米气泡课题组智能助手',
        short_name: '小气助手',
        description: '任务/会议/知识一体化智能 Agent',
        theme_color: '#FF7A5C',
        background_color: '#F5F7FA',
        display: 'standalone',
        orientation: 'portrait',
        scope: '/',
        start_url: '/',
        icons: [
          { src: '/pwa-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/pwa-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/pwa-512-maskable.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      injectManifest: {
        // 预缓存：JS/CSS/SVG/PNG/字体 + offline.html（真离线兜底）
        // 不预缓存 index.html：HTML 总走 NetworkFirst 拿最新
        // v28 step 80: 不预缓存 .webmanifest（manifest 文件不需要离线缓存 + 服务器 410 拦截会触发 bad-precaching-response）
        globPatterns: ['**/*.{js,css,svg,png,ico,woff,woff2}', 'offline.html'],
        globIgnores: ['**/*.webmanifest'],
      },
      devOptions: {
        // 开发模式禁用 service worker（避免缓存干扰调试）
        enabled: false,
      },
    }),

    // webhint cache-busting 修复：manifest.webmanifest → manifest.{hash}.webmanifest
    // 2026-07-10: 删 manifestHashPlugin，统一在 scripts/postbuild-fix-manifest.js 处理。
    // 见上方 import 块的注释（setImmediate 竞态根因 + postbuild 更可靠）

    // Vue 3.5 'bum' null 解构 bug patch — 见上面 vueBumNullPatchPlugin 注释
    vueBumNullPatchPlugin(),
    // EP useOrderedChildren.removeChild null guard — 见 epUnregisterPaneNullPatchPlugin 注释
    epUnregisterPaneNullPatchPlugin(),
    // zrender wheel/touchstart listener 加 {passive:false} — 见上面 zrenderPassiveWheelPatchPlugin 注释
    zrenderPassiveWheelPatchPlugin(),
  ],
  css: {
    postcss: {
      plugins: [stripMozAppearance, stripScrollbarWidth, stripEpProgressKeyframes]
    },
    // PR #2: NutUI 4 组件 SCSS 需要 $dark-background 等变量
    // NutUIResolver 忽略 importStyle 直接用 .scss 源，
    // 必须用 additionalData 在每个 SCSS 文件顶部注入 NutUI 默认变量
    preprocessorOptions: {
      scss: {
        additionalData: `@import "@nutui/nutui/dist/styles/variables.scss";\n`,
      },
    },
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  // 2026-07-20 cache-bust: 全局常量注入 (与 main.js console.log 同步)
  // 浏览器 DevTools 顶部 console 看 [build] 行 → 知道是哪个 build
  // 运维诊断: 用户报"页面没更新" → 让他截图 console 第一行, 对比服务器部署时间
  define: {
    __BUILD_TIMESTAMP__: JSON.stringify(BUILD_TIMESTAMP),
    __BUILD_ID__: JSON.stringify(BUILD_ID),
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        // W93: CI 可覆盖 (app-test 在 8001, 本地 dev 在 8000)
        target: process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000',
        changeOrigin: true
      },
      '/ws': {
        target: (process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000').replace('http', 'ws'),
        ws: true
      }
    }
  },
  // webhint cache-busting 兼容：把 chunk/asset 哈希从默认 base64 改成 16 进制
  // 默认 hash: 'Bd9Mi5i6' (base64url, A-Za-z0-9_-) 被 webhint 内置 [0-9a-f]+ 正则拒绝
  // hashCharacters: 'hex' 后产出 'bd9a3e21' 这种全小写 16 进制，webhint 通过
  //
  // PR #2: 独立 chunk 切分（桌面/移动物理隔离）
  // - element-plus-desktop: 桌面组件库，所有 el-* 组件共享此 chunk
  // - nutui-mobile: 移动组件库，所有 nut-* 组件共享此 chunk（桌面首屏不下载）
  // - echarts: 大型图表库独立 chunk（按需懒加载）
  build: {
    rollupOptions: {
      output: {
        hashCharacters: 'hex',
        // PR #2: 独立 chunk 切分（桌面/移动物理隔离）
        // Vite 8 / rolldown 要求 manualChunks 为函数而非对象
        manualChunks(id) {
          if (id.includes('node_modules/element-plus/')) return 'element-plus-desktop'
          if (id.includes('node_modules/@nutui/nutui/')) return 'nutui-mobile'
          if (id.includes('node_modules/echarts/')) return 'echarts'
          // v28 step 101 fix: paperAdapter.js 152KB 大文件，Vite 默认 treeshake
          //   把整个文件消除（named import 无 side effect）。强制独立 chunk 避免被消除
          if (id.includes('src/utils/paperAdapter') || id.includes('src/utils/chemFormat')) {
            return 'paper-adapter'
          }
        },
      },
    },
  },
  build: {
    cssMinify: false,  // W-N 2026-08-14 保留 :hover 规则（esbuild minify 会错误优化掉）
    cacheDir: '',  // 禁用 build 缓存，强制每次重编译
  }
})