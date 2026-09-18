// Renderer 入口 — 设计令牌（单一来源包）先行加载
import '@mb/design-tokens/variables.css'
// M7：宣纸暖白令牌覆盖层（必须在共享令牌之后、EP 样式之前/之后均可——EP 映射走
// [data-theme='paper'] 属性块，specificity 高于 EP 自身 :root）
import './assets/theme-paper.css'
import './assets/app.css'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'

// 主题轴 — M7 起唯一主题为 paper（宣纸暖白）；属性选择器可稳定压过 EP 的 :root 变量
document.documentElement.dataset.theme = 'paper'

// 锁定页面缩放 — 应用不提供缩放功能；拦截触控板捏合 / Ctrl+滚轮误触
// （Chromium 会按 origin 持久化缩放级别，重启不恢复，故必须从源头拦截）
window.addEventListener(
  'wheel',
  (e) => {
    if (e.ctrlKey) e.preventDefault()
  },
  { passive: false }
)

createApp(App).use(createPinia()).use(router).use(ElementPlus).mount('#app')
