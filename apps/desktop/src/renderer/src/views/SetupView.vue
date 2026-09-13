<script setup lang="ts">
// 首启注册 — 库内零用户时到达；第一个账号即本机管理员（骨架设计 §1.1）
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import logoUrl from '../assets/logo.png'

const router = useRouter()
const auth = useAuthStore()

const form = ref({ username: '', displayName: '', password: '', confirm: '' })
const error = ref('')
const loading = ref(false)

async function onSubmit(): Promise<void> {
  error.value = ''
  if (!form.value.username || !form.value.password) {
    error.value = '请输入用户名和密码'
    return
  }
  if (form.value.password.length < 8) {
    error.value = '密码至少 8 位'
    return
  }
  if (form.value.password !== form.value.confirm) {
    error.value = '两次输入的密码不一致'
    return
  }
  loading.value = true
  try {
    await auth.registerAdmin(form.value.username, form.value.displayName, form.value.password)
    void router.push({ name: 'assistant' })
  } catch (e) {
    error.value = e instanceof Error ? e.message : '创建失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="auth-root">
    <section class="auth-shell" aria-labelledby="setup-title">
      <aside class="auth-identity" data-testid="login-identity" aria-label="小气科研工作台 产品说明">
        <div class="auth-brand"><img class="auth-brand-logo" :src="logoUrl" alt="微纳米气泡课题组" /><span>MicroBubble Lab</span></div>
        <p class="auth-kicker">SCIENTIFIC WORKBENCH</p>
        <h1>把课题组的数据，装进一台本地工作台。</h1>
        <p>实验、知识、会议与 AI 助手汇集在同一套本地科研工作台；数据存本机，断网可用。</p>
        <p class="auth-status"><span class="auth-status-dot" aria-hidden="true"></span>本地数据库已就绪 <b aria-hidden="true">•</b> 离线优先</p>
      </aside>
      <form class="auth-form" @submit.prevent="onSubmit">
        <p class="auth-eyebrow">首次使用</p>
        <h2 id="setup-title">创建管理员账号</h2>
        <p class="auth-lede">第一个账号将成为本机管理员，之后可由管理员在设置中创建其他账号。</p>
        <label for="setup-username">用户名</label>
        <input id="setup-username" v-model="form.username" type="text" autocomplete="username" :disabled="loading" placeholder="例如：wangtianzhi" />
        <label for="setup-display">显示名称（可选）</label>
        <input id="setup-display" v-model="form.displayName" type="text" autocomplete="name" :disabled="loading" placeholder="例如：王天志" />
        <label for="setup-password">密码（至少 8 位）</label>
        <input id="setup-password" v-model="form.password" type="password" autocomplete="new-password" :disabled="loading" placeholder="设置你的密码" />
        <label for="setup-confirm">确认密码</label>
        <input id="setup-confirm" v-model="form.confirm" type="password" autocomplete="new-password" :disabled="loading" placeholder="再输入一次密码" />
        <button type="submit" :disabled="loading">{{ loading ? '创建中…' : '创建并进入工作台' }}</button>
        <p v-if="error" class="auth-error" role="alert">{{ error }}</p>
        <p class="auth-note"><span aria-hidden="true">▣</span>账号和数据仅保存在本机数据库，不上传云端。</p>
      </form>
    </section>
  </main>
</template>

<style src="./auth.css" scoped />
