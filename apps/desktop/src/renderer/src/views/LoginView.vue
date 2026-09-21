<script setup lang="ts">
// 登录页 — M2-3a+ 统一登录：以**父级账号**联网登录（本地建号已退役）；视觉沿用归档规格的双栏/a11y 结构
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'
import logoUrl from '../assets/logo.png'
import WindowControls from '../components/WindowControls.vue'

const router = useRouter()
const auth = useAuthStore()

const form = ref({ username: '', password: '' })
const error = ref('')
const loading = ref(false)

async function onSubmit(): Promise<void> {
  error.value = ''
  if (!form.value.username || !form.value.password) {
    error.value = '请输入课题组账号与密码'
    return
  }
  loading.value = true
  try {
    // M2-3a+ 统一登录：走父级账号（取代本地建号 + 手动绑定）
    const r = await auth.cloudLogin(form.value.username, form.value.password, server.value || undefined)
    if (r.firstClaim && r.summary) ElMessage.success(r.summary)
    void router.push({ name: 'assistant' })
  } catch (e) {
    error.value = e instanceof Error ? e.message : '登录失败'
  } finally {
    loading.value = false
  }
}
const api = window.api // 模板作用域内不可直接访问 window，桥接引用
/** 服务器地址（高级折叠，默认课题组 API 主机；自建/局域网部署可改） */
const server = ref('https://agent.mnb-lab.cn')
/** 本地不再提供注册：无账号时引导去网页端注册 */
function openRegister(): void {
  void api.app.openExternal('https://mnb-lab.cn')
}
</script>

<template>
  <main class="auth-root">
  <div class="auth-windowbar" @dblclick="api.window.toggleMaximize()">
    <WindowControls variant="page" />
  </div>
    <section class="auth-shell" aria-labelledby="login-title">
      <aside class="auth-identity" data-testid="login-identity" aria-label="小气科研工作台 产品说明">
        <div class="auth-brand"><img class="auth-brand-logo" :src="logoUrl" alt="微纳米气泡课题组" /><span>MicroBubble Lab</span></div>
        <p class="auth-kicker">SCIENTIFIC WORKBENCH</p>
        <h1>把课题组的数据，装进一台本地工作台。</h1>
        <p>实验、知识、会议与 AI 助手汇集在同一套本地科研工作台；数据存本机，断网可用。</p>
        <p class="auth-status"><span class="auth-status-dot" aria-hidden="true"></span>本地数据库已就绪 <b aria-hidden="true">•</b> 离线优先</p>
      </aside>
      <form class="auth-form" @submit.prevent="onSubmit">
        <p class="auth-eyebrow">欢迎回来</p>
        <h2 id="login-title">进入科研工作台</h2>
        <p class="auth-lede">账号保存在本机，断网也可登录使用。</p>
        <label for="login-username">用户名</label>
        <input id="login-username" v-model="form.username" type="text" autocomplete="username" :disabled="loading" placeholder="例如：wangtianzhi" />
        <label for="login-password">密码</label>
        <input id="login-password" v-model="form.password" type="password" autocomplete="current-password" :disabled="loading" placeholder="输入你的密码" />
        <p class="register-hint">
          还没有课题组账号？
          <a href="#" data-testid="login-register-hint" @click.prevent="openRegister">到 mnb-lab.cn 注册</a>
        </p>
        <details class="server-adv">
          <summary>高级选项</summary>
          <input id="login-server" v-model="server" type="text" :disabled="loading" placeholder="服务器地址（默认课题组 API 主机）" />
        </details>
        <button type="submit" :disabled="loading">{{ loading ? '登录中…' : '安全登录' }}</button>
        <p v-if="error" class="auth-error" role="alert">{{ error }}</p>
        <p class="auth-note"><span aria-hidden="true">▣</span>账号和数据仅保存在本机数据库。</p>
      </form>
    </section>
  </main>
</template>

<style src="./auth.css" scoped />
