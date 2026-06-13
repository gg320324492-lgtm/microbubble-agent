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

import { precacheAndRoute, cleanupOutdatedCaches } from 'workbox-precaching'
import { registerRoute, setCatchHandler } from 'workbox-routing'
import { NetworkFirst, StaleWhileRevalidate, CacheFirst } from 'workbox-strategies'
import { ExpirationPlugin } from 'workbox-expiration'

// === 生命周期 ===
// skipWaiting + clients.claim 让新版 SW 安装后立即接管所有已开的标签页，
// 用户刷新一次后看到的就是新逻辑（autoUpdate 体验）
self.skipWaiting()
self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim())
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

// === 路由 3：API GET（5 分钟缓存）===
// 阿里云 FRP 隧道偶发慢，5s 内无响应回退到 5 分钟内的旧响应
registerRoute(
  ({ url }) => url.pathname.startsWith('/api/v1/'),
  new NetworkFirst({
    cacheName: 'api-cache',
    networkTimeoutSeconds: 5,
    plugins: [
      new ExpirationPlugin({ maxEntries: 100, maxAgeSeconds: 300 }),
    ],
  }),
  'GET'
)

// === 路由 4：图片（30 天缓存）===
// MinIO 通过 FRP 隧道的头像/封面图，CacheFirst 节省带宽
registerRoute(
  ({ request, url }) =>
    request.destination === 'image' ||
    /\.(?:png|jpg|jpeg|svg|gif|webp)$/.test(url.pathname),
  new CacheFirst({
    cacheName: 'images',
    plugins: [
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
