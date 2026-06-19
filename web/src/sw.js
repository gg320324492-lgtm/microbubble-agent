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
const SW_VERSION = 'v11-no-figure-leak-2026-06-19'
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
