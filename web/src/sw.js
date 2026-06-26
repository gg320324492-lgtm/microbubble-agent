// 自定义 Service Worker（injectManifest 模式）
// 替换 vite-plugin-pwa 的 generateSW 模式，修复 offline.html 总是优先返回的 bug
//
// === 背景 ===
// 旧配置用 `navigateFallback: '/offline.html'`，workbox-build 会自动生成：
//   registerRoute(new NavigationRoute(createHandlerBoundToURL("/offline.html"), ...))
// `createHandlerBoundToURL` 是 SPA shell 模式：不管网络是否可用，直接把
// 该 URL 的 precache 内容返回。结果就是「所有导航请求秒返回 offline.html」，
// 即使后面再写一条 NetworkFirst 文档路由，按 workbox「先注册先匹配」规则
// 也永远走不到。
//
// === 修复 ===
// 1. 导航请求走 NetworkFirst + 5s 超时（在线 → 真实页面；慢/断 → 缓存）
// 2. `setCatchHandler` 兜底：路由处理 throw 时（真正离线 + 没缓存）才返回
//    offline.html，配合 retry 按钮 + online 事件监听器自动刷新。

// 2026-06-13 事故修复：BUMP 每次部署递增，触发 SW 字节变化让浏览器检测到新 SW
// → 立即 skipWaiting() 激活 → activate 钩子清空所有 cache（包括被污染的 documents）
// → 用户下次访问拿到的就是新资源（不受之前 octet-stream 缓存影响）
// 2026-06-13 v3 BUMP：图片路由 CacheFirst → NetworkFirst + CacheableResponsePlugin，
// 防止 FRP/服务端 5xx 响应被永久缓存 30 天
// 2026-06-13 v4 BUMP：修复 __WB_MANIFEST 里 manifest.webmanifest 旧路径导致 SW install
// 阶段 precache 失败的问题（vite-plugin-pwa 在 generateBundle 把 manifest 写进 SW，
// manifestHashPlugin 在 closeBundle 才重命名文件，SW 里还引用旧名字 → 410 Gone）
// 2026-06-14 v5 BUMP：commit a40e84c 修复 dist 漏 commit 事故后，用户浏览器仍报
// 'Cache.put() encountered a network error' — 老 SW 还在 stuck 在 install 失败状态
// （老 precache 引用不存在的 index-c2fe833d.js）。BUMP 版本强制浏览器识别为新 SW
// 重走 install 流程，激活钩子的 caches.delete 会清空老 cache。
// v28 step 85: 升级到 v37 — paperAdapter 强制保险 fallback（不依赖前面 regex 的空格）
// v28 step 101: 升级到 v38 — paperAdapter cleanContent 加 OCR phantom 页码/段首单词 inline
//   合并规则（B. cereus\n\n3\n\n(Grutsch → B. cereus 3 (Grutsch）。SW 字节未变，浏览器
//   不会主动检测更新 → 用户继续用旧 cached index-*.js → BUMP 触发升级 + activate
//   钩子清空所有 cache，让新 dist 生效
// v28 step 101 第二次 BUMP v38 → v39：去掉整篇中文守卫 if (!/[一-龥]/.test(result))。
//   原守卫会让中英混排 PDF（含中文 Abstract + 英文 Methods）整篇 result 命中中文
//   → 守卫 false → 英文段落 phantom 不合并 → 用户看不到效果
// v53: 2026-06-26 用户报告"网页进不去"白屏 → 典型 SW 污染症状（CLAUDE.md 2026-06-13
// 沉淀的同类事故）。本次 commit 只改 src/views/* + 新建 utils，未 BUMP SW，导致浏览器
// SW 字节未变 → 不触发 install → 老 cache（含 octet-stream / 旧 chunk 路径）继续生效
// → SPA 加载失败。BUMP SW_VERSION 触发浏览器重新 install → activate 钩子
// caches.keys() + Promise.all(keys.map(caches.delete)) 清空所有 cache → postMessage
// SW_UPDATED → main.js 监听 → window.location.reload() 闭环。
// v57: 2026-06-26 修复录音会议室"返回（录音继续）"router.back → router.replace(meetings/{id})。
// handleBack 在 if(isGlobalRecorderActive) 分支调用 router.back()，从聊天页 Rich Block 进入
// 的用户 history 栈前一条是 /chat，router.back() 把用户弹回聊天页（不是用户期望的"返回"）。
// 改成 router.replace(/meetings/{id}) 与 onProgressClose 行为镜像，跳到稳定的会议详情页。
// v58: 2026-06-26 v57 fix 仍然不对（用户反馈）。v57 跳到 /meetings/{id} 详情页失去了
// 实时计时器+音频波形视图，用户期望的是"和底部胶囊一样"留在录音室。改成
// router.replace('/meetings/room')，与 MainLayout.goToRecording + MeetingView/MobileMeetingView
// 的 ?resume= 拦截逻辑最终目标一致。Vue Router 4 在当前已处于 /meetings/room 时
// short-circuit → 等价于关闭弹窗后留在原页（计时器+波形+录音不间断）。
// v59: 2026-06-26 用户反馈两个新 bug (1) 听会房间"使用说明" sheet 被底部 TabBar (z=2500)
// + 录音胶囊 (z=2900) 覆盖 → MobileMeetingRoom.vue .help-overlay z-index 2000 → 5000。
// (2) 移动端 TabBar 切深色模式不变色 → 双根因修复：TabBar.vue 删 hardcoded
// inactive-color="#909399" / active-color="#FF7A5C" 属性（阻断 NutUI CSS 变量级联），
// nutui-theme.scss [data-theme="dark"] 块补 --nut-tabbar-active-color #FF9D85 +
// --nut-tabbar-inactive-color #a6a9ad 覆盖。SW BUMP 触发浏览器重新 install。
// v60: 2026-06-26 v59 部署后用户反馈"还是没变深色"。诊断发现：(a) NutUI 内部 inactive
// icon 选择器 nut-tabbar-item__icon--unactive 实际用 --nut-dark-color-gray /
// --nut-text-color 而不是 --nut-tabbar-inactive-color，所以 v59 在 nutui-theme.scss
// 加的 inactive 变量**根本没被消费**。(b) TabBar.vue :deep(.nut-tabbar-item) 用
// var(--color-text-secondary)，但该变量在 variables.css:501 设计上 light/dark 都
// 保持 #909399 不变（次要文字色需要稳定的中性灰）。所以 inactive 颜色"看不出变化"。
// (c) active 用 var(--color-primary) = dark #FF9D85 与 light #FF7A5C，亮度差仅 +15%，
// 视觉差异太小。修复：TabBar.vue 加 [data-theme="dark"] :deep(...) 覆盖，inactive
// 用 var(--color-text-regular) = #c0c4cc，active 用 var(--color-accent) = #FFC067。
// 纪律沉淀：NutUI 主题定制优先改 项目 scoped CSS + [data-theme="dark"] 覆盖，
// 不要期望 nutui-theme.scss 改 --nut-tabbar-*-color 生效。
// v61: 2026-06-26 v60 部署后用户反馈还是不变。诊断：Vue 3 scoped CSS 编译 [attr]
// 属性选择器 + :deep() 有坑——把 data-v-2c0c6d65 加到了 [data-theme="dark"] 上
// 而不是 :deep() 内的 .nut-tabbar-item，编译产物为
// [data-theme=dark][data-v-2c0c6d65] .nut-tabbar-item，
// 需要同一个元素同时拥有两个属性才匹配——但 <html> 只有 data-theme="dark"，
// <nav class="mobile-tabbar"> 只有 data-v-2c0c6d65，**永远不匹配**。
// 修复尝试 v61：用 :global([data-theme="dark"]) 显式让属性选择器脱离 Vue scope，
// 但 Vue 编译器把 :global() + :deep() + 后代选择器组合处理错——
// 编译产物变 [data-theme=dark]{color:var(--color-accent);background:#ffb3472e}
// 单独的规则（后代选择器和 :deep() 部分被丢），且这条规则会作用到 <html> 上！
// v62: 2026-06-26 终极修复——把 dark mode 规则移到 Vue SFC 的**第二个非 scoped
// <style> 块**。非 scoped 块不附加 data-v，规则全局生效直接命中 NutUI 元素。
// 教训：dark mode 跨组件（特别是 NutUI 第三方元素）覆盖优先用非 scoped <style> 块，
// 不要在 scoped 块里玩 [attr] + :deep() 或 :global() 组合——Vue 编译器有 3 层坑。
// v63: 2026-06-26 v62 部署后用户反馈 inactive icon 仍不变。诊断：v62 第一条规则
// [data-theme="dark"] .nut-tabbar-item { color: var(--color-text-regular) }
// 设的是父元素 .nut-tabbar-item 的 color，但 NutUI 编译 CSS rule 15 直接在
// 子元素 .nut-tabbar-item__icon--unactive 上设 color: var(--nut-black, #000)
// （本项目 nutui-theme.scss:35 定义 --nut-black = #2D2D2D）——子元素直接设色
// 切断 CSS 继承，所以 inactive icon 颜色在 dark 模式仍 = #2D2D2D。
// 修复：在非 scoped 块追加 [data-theme="dark"] .nut-tabbar-item__icon--unactive
// 选择器，直接命中 NutUI 实际设色的子元素，特异性 (0,2,0) vs NutUI (0,1,0) 胜出。
// 教训：编译正确 ≠ 业务生效——必须验证选择器命中的元素确实是想要染色的元素，
// CSS color 继承会被子元素直接声明覆盖。
// v64: 2026-06-26 v63 部署后用户截图反馈"底部导航栏全白的"。诊断：v62/v63 只把
// .nut-tabbar-item 颜色移到非 scoped 块，但漏了 .mobile-tabbar 容器背景。
// 容器背景 dark 模式还在 scoped <style> 块，scoped CSS 编译 [data-theme="dark"]
// .mobile-tabbar 时把 data-v 错误附加到属性选择器（同 v60 教训），编译产物
// [data-theme=dark] .mobile-tabbar[data-v-xxx] 要求同一元素同时有两属性——
// <html> 只有 data-theme，<nav> 只有 data-v，**永不匹配** → dark 容器背景
// 永远不生效，TabBar 一直是 rgba(255,255,255,0.92) 白底半透明。
// 修复：把 .mobile-tabbar 容器背景 dark 覆盖也移到非 scoped 块。
// 教训：v62/v63 教训只覆盖到 .nut-tabbar-item，漏了 .mobile-tabbar 容器。
// 任何 [data-theme="dark"] 在 scoped 块里都触发同一 Vue scoped bug，**所有 dark 模式
// scoped 规则都要迁移到非 scoped 块**。下次添加 dark 模式前先检查该组件是否在
// scoped 块写过 [data-theme="dark"] 规则，统统迁移。
// v65: 2026-06-26 v64 部署后 DevTools 6 项 console.table 全 ✓ 深色（TabBar bg
// rgba(26,29,35,0.92)、active 金橙、inactive 亮灰都对），但用户截图仍显示白色。
// 真根因：rgba(26,29,35,0.92) 半透明 + backdrop-filter blur(16px) 在深色页面背景上
// 视觉呈现"雾化灰白"——8% 透明区透出深色 + 模糊混合 + 白色图标叠加 = 看起来浅色。
// 不是 CSS bug，是视觉错觉。
// 修复：dark 模式 TabBar 背景从 rgba(...,0.92) 改成 rgb(26,29,35) 完全不透明，
// 消除 8% 透明区，TabBar 绝对实心深色不可能再被误认为白色。light 模式保留 0.92
// 半透明（浅色场景半透明有 iOS 玻璃质感，保留设计意图）。
// 教训：CSS 层面正确不等于用户视觉满意，调试 dark mode UI 必须亲自看截图，
// 不能只看 DevTools 数值。
// v66: 2026-06-26 v65 部署后 console.table 显示 TabBar bg 仍是 rgba(26,29,35,0.92)
// 半透明，根本没生效。原因：CSS 同时存在 2 条 dark 规则——
//   Rule 1: [data-theme="dark"] .mobile-tabbar[data-v-xxx] → rgba(26,29,35,0.92)
//           (scoped v64 留尾，特异性 0,3,0)
//   Rule 2: [data-theme="dark"] .mobile-tabbar → rgb(26,29,35)
//           (非 scoped v65 新加，特异性 0,2,0)
// Rule 1 特异性更高胜出 → 仍是半透明。v65 只改了非 scoped 那条，漏了原 scoped
// 那条仍是 0.92 透明。修复：把原 scoped 那条的值从 rgba(26,29,35,0.92) 改成
// rgb(26,29,35) 完全不透明，与非 scoped 规则值一致。
// 教训：dark mode 容器背景涉及**两条 CSS 规则**（scoped + 非 scoped），任何一处
// 不透明值都会被高特异性那条胜出，必须**两处同步修改**。下次添加 dark 模式 UI
// 先 grep 现有 scoped 块是否已有同名 dark 规则，全量同步。
// v67: 2026-06-26 v66 部署后 console.table 显示 .mobile-tabbar bg-color 是
// rgb(26,29,35) 深色 ✓，但 .nut-tabbar bg-color 是 rgb(255,255,255) 白色 ✗
// → TabBar 仍显示白色。根因：NutUI 内部 .nut-tabbar 子元素有自己的
// `background: var(--nut-white, #fff)` 规则直接设白色，**盖住**了父元素
// .mobile-tabbar 的深色背景。CSS background 不继承，子元素直接设 background
// 就会覆盖视觉。
// 修复：在非 scoped 块加 [data-theme="dark"] .nut-tabbar 覆盖，深色与父元素同步。
// 教训：CSS 框架子组件（NutUI/MUI/EP 等）的 dark class（.nut-theme-dark /
// .dark 等）通常和项目自己的 [data-theme="dark"] 不一致——必须为每个有
// background 的子组件单独写覆盖，不能假设父元素深色子元素就深色。
// NutUI 有 .nut-theme-dark .nut-tabbar 的 dark 模式 fallback（用 --nut-dark-background），
// 但项目用 [data-theme="dark"] 不触发 NutUI 的 dark class，所以 NutUI 的
// dark 规则完全不生效——必须手动覆盖。
// v68: 2026-06-26 桌面端主题切换按钮 + SettingsView 视觉升级。
// (1) 新增 ThemeToggleButton.vue 共享组件（36px 圆形 ☀️/🌙 emoji 按钮，
//     hover scale(1.1) + 主色背景 + 阴影），MainLayout 顶栏铃铛之后接入。
//     桌面端终于有全局主题切换入口（之前只在 ChatViewSSE 页内）。
// (2) SettingsView.vue 全面视觉升级：
//     - 顶部新增 Hero 卡片（grid-column: 1/-1 全宽）= 大头像 88px + 姓名 +
//       角色 tag + 邮箱 + "编辑资料"按钮，背景 linear-gradient 主色→强调色
//     - 4 张功能卡片统一加 .glass-card class = backdrop-filter: blur(12px) +
//       rgba(255,255,255,0.7) 半透明 + hover translateY(-2px) 浮起
//     - 新增"外观主题"卡片（grid 4）= el-switch 深色模式 + 占位主题色 radio
//     - dark mode 用 :global([data-theme="dark"]) 避开 scoped + [data-theme]
//       的 specificity 坑（继承 v60/v61 教训），独立给玻璃背景 rgba(42,45,53,0.7)
//     - 改密码卡片改名为"账号安全"（语义更准确）
// v69 P0: 2026-06-26 桌面端 dark mode 全面重构。
// (1) variables.css: 补 5 个未覆盖令牌（--color-bg-warm / --color-bg-sidebar /
//     --color-sidebar-border / --color-border / --color-primary-border）+ 更新
//     --color-text-secondary 提亮（#909399 → #a8aab0 提对比度）+ 7 个阴影变量
//     全部重定义（dark 模式 rgba(0,0,0,.3-.6) 替代 light 的 .04-.12）+ 渐变
//     库（5 个 dashboard 渐变 dark 用 rgba 透明而非亮色块）+ 14 个 EP 组件
//     完整 dark 覆盖（el-tag 背景/文字、el-button 4 状态色、el-checkbox/radio/
//     tabs/form/input 等）
// (2) MainLayout.vue: 末尾追加非 scoped dark 块覆盖侧栏/顶栏/通知/录音 banner/
//     移动端 drawer（v60-v67 教训：dark 跨组件规则必须非 scoped）
// (3) Dashboard.vue: 3 个 stat-icon 行内 style 重构为 class + 末尾追加非 scoped
//     dark 块（hero / stat-card / group-header / task-row / view-all-btn /
//     unassigned-group / 骨架屏）
// (4) DashboardPet.vue: 末尾追加非 scoped dark 块（speech-bubble 白底→深色 +
//     XP 条 / 小三角等细节）
// v69 P1a: 2026-06-26 多主题切换基建。
// (1) variables.css 末尾追加 6 套主题色板（orange/ocean/forest × light/dark），
//     用 [data-accent="X"] + [data-theme="dark"][data-accent="X"] 双轴选择器
//     覆盖 16+ 变量（primary / primary-bg / sidebar / shadow / 渐变 5 条）
// (2) useThemeStore: 新增 accent ref（orange|ocean|forest） + setAccent 方法，
//     监听 accent 变化时同步写 data-accent + localStorage
// (3) SettingsView: 主题色 picker UI 升级为 3 个 swatch 按钮（带 Check 圈 + active
//     边框 + hover translateY + focus-visible outline），CSS 变量驱动颜色
// (4) variables.css: 加 --theme-transition 让主题切换时 bg/border/color/box-shadow
//     走 280ms ease 过渡，避免生硬跳变
// v69 P1b: 2026-06-26 11 桌面视图 dark 适配。
// ChatViewSSE + AgentTracesView + TaskTrash + TaskView + MeetingView +
// MeetingDetailView + KnowledgeView + KnowledgeDetailView + ProjectView +
// MemberView 共 10 个文件末尾追加非 scoped <style> 块（v60-v67 教训：必须非
// scoped）。共 ~110 条 dark 规则覆盖 hardcoded 颜色（#fff/#333/#666/#999/
// rgba(255,255,255,...) 等），全部用 var(--color-*) 变量驱动。
// v69 P1b fix: 2026-06-26 截图发现 4 处仍白色，修复：
// (1) variables.css 加 el-dialog 完整 dark 覆盖（之前只覆盖 el-drawer，导致
//     ProjectView 3 个 dialog 创建/编辑/详情 白色）+ el-empty illustration
//     filter:invert 适配 dark（"请从左侧选择一个公式" 空状态）
// (2) ChatViewSSE chat-immersive 渐变在 scoped 块被 [data-v-xxx] specificity
//     抢赢 → 在非 scoped 块重新声明 dark 渐变；messages 加 background:transparent
// (3) KnowledgeView memory-card background: #fff → var(--color-bg-card)
// (4) VoiceprintCard.vue background: #fff → var(--color-bg-card)（组件单独
//     追加非 scoped dark 块，host.vue 内 P1b 没覆盖到）
const SW_VERSION = 'v69-p1b-fix-whites-2026-06-26'
self.__SW_VERSION__ = SW_VERSION
console.log('[SW] version:', SW_VERSION)

import { precacheAndRoute, cleanupOutdatedCaches } from 'workbox-precaching'
import { registerRoute, setCatchHandler } from 'workbox-routing'
import { NetworkFirst, StaleWhileRevalidate, CacheFirst } from 'workbox-strategies'
import { ExpirationPlugin } from 'workbox-expiration'
import { CacheableResponsePlugin } from 'workbox-cacheable-response'

// === 生命周期 ===
// skipWaiting + clients.claim 让新版 SW 安装后立即接管所有已开的标签页，
// 用户刷新一次后看到的就是新逻辑（autoUpdate 体验）
self.skipWaiting()

// v28 step 33: 响应 main.js 的 GET_VERSION 消息，返回当前 SW 版本号
// main.js 用此检查 SW 是否在黑名单（服务器部署滞后场景）
self.addEventListener('message', (event) => {
  if (event.data?.type === 'GET_VERSION') {
    event.ports[0]?.postMessage({ type: 'SW_VERSION_RESPONSE', version: SW_VERSION })
  }
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      // 清空所有 cache（不只是 workbox 默认的，所有客户端 cache）
      // 解决：之前 server 返回 octet-stream 时期被 SW NetworkFirst 缓存到 documents
      // cache 的污染响应 —— 老 SW 不会清，老 activate 不会跑
      const keys = await caches.keys()
      await Promise.all(
        keys.map(async (cacheName) => {
          console.log('[SW] deleting cache:', cacheName)
          return caches.delete(cacheName)
        })
      )
      await self.clients.claim()
      // 通知所有客户端 SW 已升级，让它们 reload
      const clients = await self.clients.matchAll({ type: 'window' })
      clients.forEach((client) => {
        client.postMessage({ type: 'SW_UPDATED', version: SW_VERSION })
      })
    })()
  )
})

// 监听客户端消息：SW_UPDATED → reload
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting()
  }
})

// === 预缓存 ===
// __WB_MANIFEST 由 vite-plugin-pwa 在构建时根据 globPatterns 注入
// （包含 JS/CSS/SVG/PNG/ICO/字体 + offline.html）
precacheAndRoute(self.__WB_MANIFEST)
cleanupOutdatedCaches()

// === 路由 1：HTML 文档（含顶层导航）===
// NetworkFirst + 5s 超时：
//   - 在线快：拿到新版 HTML 并刷缓存
//   - 在线慢（>5s）：回退到 documents 缓存中的旧 HTML（仍可用）
//   - 离线 + 有缓存：旧 HTML
//   - 离线 + 无缓存：抛错 → setCatchHandler 兜底 offline.html
registerRoute(
  ({ request }) => request.mode === 'navigate' || request.destination === 'document',
  new NetworkFirst({
    cacheName: 'documents',
    networkTimeoutSeconds: 5,
    plugins: [
      new ExpirationPlugin({ maxEntries: 20, maxAgeSeconds: 60 * 60 * 24 }),
    ],
  })
)

// === 路由 2：脚本 + 样式 ===
// 已在 precache 中，runtime SWR 让在线时静默更新缓存
registerRoute(
  ({ request }) => request.destination === 'script' || request.destination === 'style',
  new StaleWhileRevalidate({ cacheName: 'static-resources' })
)

// === 路由 3：API GET（5 分钟缓存 + 仅 2xx）===
// 阿里云 FRP 隧道偶发慢，5s 内无响应回退到 5 分钟内的旧响应
// 2026-06-13 教训：必须 CacheableResponsePlugin 限制只缓存 0/200，避免 5xx 被永久缓存
registerRoute(
  ({ url }) => url.pathname.startsWith('/api/v1/'),
  new NetworkFirst({
    cacheName: 'api-cache',
    networkTimeoutSeconds: 5,
    plugins: [
      new CacheableResponsePlugin({ statuses: [0, 200] }),
      new ExpirationPlugin({ maxEntries: 100, maxAgeSeconds: 300 }),
    ],
  }),
  'GET'
)

// === 路由 4：图片（NetworkFirst + 仅缓存 2xx）===
// MinIO 通过 FRP 隧道的头像/封面图。
// 2026-06-13 教训：之前用 CacheFirst，FRP 断时浏览器把 502 响应**当成功缓存**到 images cache
// 30 天有效期 → frp 修好后浏览器永远返回 cache 里的 502，用户看不到头像。
// workbox 默认不会区分 200/4xx/5xx，全部缓存。
// 修复：① 改 NetworkFirst（先网络后 cache，5s 超时）② 加 CacheableResponsePlugin 只缓存
// statuses: [0, 200] 的响应（0 = opaque/cross-origin no-cors，200 = 真实成功）
registerRoute(
  ({ request, url }) =>
    request.destination === 'image' ||
    /\.(?:png|jpg|jpeg|svg|gif|webp)$/.test(url.pathname),
  new NetworkFirst({
    cacheName: 'images',
    networkTimeoutSeconds: 5,
    plugins: [
      // 关键：只缓存 0 (opaque) 和 200，避免 5xx 被永久缓存
      new CacheableResponsePlugin({ statuses: [0, 200] }),
      new ExpirationPlugin({ maxEntries: 50, maxAgeSeconds: 60 * 60 * 24 * 30 }),
    ],
  })
)

// === 离线兜底（关键修复点）===
// 仅当上面所有路由都 throw 时触发 → 真正的「无网络 + 无缓存」场景
// 才返回 offline.html。普通导航不会经过这里 → 在线时绝不会误显示 offline.html
setCatchHandler(async ({ request }) => {
  if (request.destination === 'document' || request.mode === 'navigate') {
    const cached = await caches.match('/offline.html')
    return cached || Response.error()
  }
  return Response.error()
})
