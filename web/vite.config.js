import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import NutUIResolver from '@nutui/nutui/dist/resolver'
import { VitePWA } from 'vite-plugin-pwa'

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
    // - manifest: 应用元信息（添加到桌面用）
    // - workbox: 资源预缓存 + API 缓存 + 离线 fallback
    VitePWA({
      registerType: 'autoUpdate',
      injectRegister: 'auto', // 自动注入 service worker 注册
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
      workbox: {
        // 预缓存所有构建产物（最大 3MB）
        globPatterns: ['**/*.{js,css,html,svg,png,ico,woff,woff2}'],
        navigateFallback: '/offline.html',
        navigateFallbackDenylist: [/^\/api\//, /^\/ws\//],
        runtimeCaching: [
          {
            // 静态资源（已通过 globPatterns 预缓存）
            urlPattern: ({ request }) => request.destination === 'document' || request.destination === 'script' || request.destination === 'style',
            handler: 'StaleWhileRevalidate',
            options: { cacheName: 'static-resources' },
          },
          {
            // API GET 请求（5 分钟缓存）
            urlPattern: /^\/api\/v1\/.*$/,
            handler: 'NetworkFirst',
            method: 'GET',
            options: {
              cacheName: 'api-cache',
              networkTimeoutSeconds: 5,
              expiration: { maxEntries: 100, maxAgeSeconds: 300 },
            },
          },
          {
            // 图片资源（30 天缓存）
            urlPattern: /\.(?:png|jpg|jpeg|svg|gif|webp)$/,
            handler: 'CacheFirst',
            options: {
              cacheName: 'images',
              expiration: { maxEntries: 50, maxAgeSeconds: 60 * 60 * 24 * 30 },
            },
          },
        ],
      },
      devOptions: {
        // 开发模式禁用 service worker（避免缓存干扰调试）
        enabled: false,
      },
    }),
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
          if (id.includes('node_modules/echarts/') || id.includes('node_modules/vue-echarts/')) return 'echarts'
        },
      },
    },
  }
})