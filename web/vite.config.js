import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import NutUIResolver from '@nutui/nutui/dist/resolver'
import { VitePWA } from 'vite-plugin-pwa'

// 2026-07-20 cache-bust 时间窗: 全局 __BUILD_TIMESTAMP__ 常量
// 注入时机: build 启动时 (process.hrtime / Date.now), 在 main.js 入口 console.log 出来
// 浏览器看到的时间戳可帮运维快速判断:
//   1. 部署是否真的生效 (用户报 cache miss → 对比 dist hash + 时间戳)
//   2. CDN/边缘节点是否回源 (同 URL 不同时间戳 = 边缘 cache)
//   3. 用户是否拿到旧 build (DevTools 顶部 console + 时间戳 + 版本号)
// 设计: 用 ISO 字符串 (人可读) 而非 epoch ms, 同时附 build_id (随机 6 字符, 多容器并行 build 区分)
// ⚠️ 与 main.js 的 console.log 必须同步, 否则用户看不到时间戳 = 功能无效
const BUILD_TIMESTAMP = new Date().toISOString()
const BUILD_ID = Math.random().toString(36).slice(2, 8)

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
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/ws': {
        target: 'ws://localhost:8000',
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
  }
})