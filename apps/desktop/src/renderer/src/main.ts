// Renderer 入口 — 设计令牌（单一来源包）先行加载
import '@mb/design-tokens/variables.css'
import './assets/app.css'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'

createApp(App).use(createPinia()).use(router).use(ElementPlus).mount('#app')
