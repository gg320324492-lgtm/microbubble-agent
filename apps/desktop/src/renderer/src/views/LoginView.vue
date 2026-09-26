<script setup lang="ts">
// 登录页 — M2-3a+ 统一登录：以**父级账号**联网登录（本地建号已退役）；视觉沿用归档规格的双栏/a11y 结构
import { onMounted, ref } from 'vue'
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
    const r = await auth.cloudLogin(form.value.username, form.value.password, server.value || undefined, remember.value)
    if (r.firstClaim && r.summary) ElMessage.success(r.summary)
    void router.push({ name: 'assistant' })
  } catch (e) {
    error.value = e instanceof Error ? e.message : '登录失败'
  } finally {
    loading.value = false
  }
}
const api = window.api // 模板作用域内不可直接访问 window，桥接引用
// 服务器地址：默认内置（agent.mnb-lab.cn）。
// 普通用户界面**不再暴露**该配置；运维需要覆盖时走代码层能力（auth.cloudLogin 仍接受 baseUrl，
// 亦可通过设置项覆盖），无需在登录窗暴露。
const server = ref('')

/** DL-2：记住账号与密码（凭据经系统 DPAPI 加密保存在本机） */
const remember = ref(false)

/** 挂载时尝试预填已记住的账号密码 */
async function prefillRemembered(): Promise<void> {
  try {
    const r = (await api.auth.rememberGet()) as { username?: string; password?: string } | null
    if (r?.username) {
      form.value.username = r.username
      form.value.password = r.password ?? ''
      remember.value = true
    }
  } catch {
    /* 未记住 / 解密失败 → 保持空表单 */
  }
}

onMounted(() => {
  void prefillRemembered()
})
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
        <p>实验、知识、会议与 AI 助手汇集在同一套科研工作台；登录一次即可用，断网也能继续工作。</p>
        <p class="auth-status"><span class="auth-status-dot" aria-hidden="true"></span>本地数据库已就绪 <b aria-hidden="true">•</b> 离线优先</p>
      </aside>
      <form class="auth-form" @submit.prevent="onSubmit">
        <p class="auth-eyebrow">欢迎回来</p>
        <h2 id="login-title">进入科研工作台</h2>
        <label for="login-username">用户名</label>
        <input id="login-username" v-model="form.username" type="text" autocomplete="username" :disabled="loading" placeholder="课题组账号（与网页端相同）" />
        <label for="login-password">密码</label>
        <input id="login-password" v-model="form.password" type="password" autocomplete="current-password" :disabled="loading" placeholder="输入你的密码" />
        <label class="remember-row">
          <input v-model="remember" type="checkbox" data-testid="login-remember" :disabled="loading" />
          <span>记住账号与密码</span>
        </label>
        <p class="register-hint" data-testid="login-register-hint">没有账号？请联系管理员开通</p>

        <button type="submit" :disabled="loading">{{ loading ? '登录中…' : '安全登录' }}</button>
        <p v-if="error" class="auth-error" role="alert">{{ error }}</p>
      </form>
    </section>
  </main>
</template>

<style src="./auth.css" scoped />
