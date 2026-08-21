import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
// router 必须在 pinia 之后（router.beforeEach 里要 useAuthStore）
app.use(router)

app.mount('#app')
