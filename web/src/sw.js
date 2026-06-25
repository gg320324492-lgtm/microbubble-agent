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
const SW_VERSION = 'v58-meeting-room-timer-2026-06-26'
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
