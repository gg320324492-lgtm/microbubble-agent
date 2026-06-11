import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

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
      resolvers: [ElementPlusResolver({ importStyle: 'css' })],
      dts: false,  // 不生成类型声明文件
    }),
  ],
  css: {
    postcss: {
      plugins: [stripMozAppearance, stripScrollbarWidth, stripEpProgressKeyframes]
    }
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
  }
})
