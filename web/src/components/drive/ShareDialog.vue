<!--
  ShareDialog.vue — 课题组网盘 v2 PR1 ShareDialog 组件

  功能:
  - 顶部: 选择过期时间 (1天/7天/30天/永久)
  - 中部: el-switch 启用提取码 + el-input 4-8 位密码 + 自动生成按钮
  - 底部: 生成按钮 + 复制 URL 链接 + 显示完整分享 URL
  - dark mode: 末尾非 scoped 块 (v60-v67 教训)

  Props:
  - modelValue: 显隐 (v-model:show)
  - file: {id, file_name, file_type, file_size}

  Events:
  - @update:modelValue 关闭
  - @shared (token, url, password) 创建分享后
-->
<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    title="🔗 生成分享链接"
    width="500px"
    top="15vh"
    :close-on-press-escape="!generating"
    :show-close="!generating"
  >
    <div v-if="!result" class="share-form">
      <p class="share-intro">
        生成分享链接后, 任何收到链接的人都可以
        <span v-if="usePassword">需输入提取码</span>
        <span v-else>直接</span>
        下载 "{{ file?.file_name }}" (限时效内).
      </p>

      <div class="share-field">
        <label class="share-field-label">过期时间</label>
        <el-radio-group v-model="expiresHours" class="share-radio-group">
          <el-radio :value="24">1 天</el-radio>
          <el-radio :value="168">7 天</el-radio>
          <el-radio :value="720">30 天</el-radio>
          <el-radio :value="-1">永久</el-radio>
        </el-radio-group>
      </div>

      <div class="share-field">
        <label class="share-field-label">提取码保护</label>
        <el-switch
          v-model="usePassword"
          active-text="启用 4 位数字提取码"
          inactive-text="无密码公开分享"
        />
      </div>

      <div v-if="usePassword" class="share-field">
        <label class="share-field-label">提取码</label>
        <el-input
          v-model="password"
          placeholder="4-8 位数字"
          maxlength="8"
          show-password
          clearable
          class="share-password-input"
        >
          <template #append>
            <el-button @click="autoGeneratePassword">
              <el-icon><Refresh /></el-icon>
              随机
            </el-button>
          </template>
        </el-input>
        <p class="share-hint">已记住的提取码 = 4-8 位数字, 留空即无密码</p>
      </div>
    </div>

    <div v-else class="share-result">
      <el-result icon="success" title="分享链接已创建">
        <template #sub-title>
          <p class="share-result-detail">
            <span v-if="result.passwordRequired">含提取码保护</span>
            <span v-else>无密码 - 任何收到链接的人可直接下载</span>
          </p>
        </template>
      </el-result>

      <div class="share-url-box">
        <el-input
          v-model="result.shareUrl"
          readonly
          class="share-url-input"
        >
          <template #append>
            <el-button type="primary" @click="copyUrl">
              <el-icon><DocumentCopy /></el-icon>
              {{ copied ? '已复制' : '复制' }}
            </el-button>
          </template>
        </el-input>
      </div>

      <div v-if="result.passwordRequired" class="share-password-display">
        <p class="share-password-label">提取码 (请单独告知)</p>
        <div class="share-password-value-row">
          <code class="share-password-value">{{ result.password }}</code>
          <el-button text @click="copyPassword">
            <el-icon><DocumentCopy /></el-icon>
            {{ passwordCopied ? '已复制' : '复制' }}
          </el-button>
        </div>
      </div>

      <div v-if="result.expiresAt" class="share-expires">
        到期时间: {{ formatExpires(result.expiresAt) }}
      </div>
      <div v-else class="share-expires">
        到期时间: 永久
      </div>
    </div>

    <template #footer>
      <template v-if="!result">
        <el-button @click="$emit('update:modelValue', false)">取消</el-button>
        <el-button type="primary" :loading="generating" @click="generate">
          生成链接
        </el-button>
      </template>
      <template v-else>
        <el-button @click="resetForAnother">再生成一次</el-button>
        <el-button type="primary" @click="$emit('update:modelValue', false)">完成</el-button>
      </template>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { DocumentCopy, Refresh } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  file: { type: Object, default: null }
})

const emit = defineEmits(['update:modelValue', 'shared'])

const EXPIRE_PRESETS = [
  { value: 24, label: '1 天' },
  { value: 168, label: '7 天' },
  { value: 720, label: '30 天' },
  { value: -1, label: '永久' }
]

const SHARE_BASE_URL = computed(() => {
  // v2 PR1: 公开 URL = {origin}/drive/share/{token}
  // origin 用 window.location.origin, 因为后端 share_url 给的是相对路径 /drive/share/...
  if (typeof window !== 'undefined' && result.value?.token) {
    return `${window.location.origin}${result.value.shareUrl}?password=${encodeURIComponent(password.value || '')}`
  }
  return ''
})

const expiresHours = ref(168)  // 默认 7 天
const usePassword = ref(true)
const password = ref('1234')
const generating = ref(false)
const result = ref(null)
const copied = ref(false)
const passwordCopied = ref(false)

watch(usePassword, (val) => {
  if (val && !password.value) {
    autoGeneratePassword()
  }
})

watch(() => props.modelValue, (open) => {
  if (open) {
    // 打开时重置
    result.value = null
    expiresHours.value = 168
    usePassword.value = true
    password.value = '1234'
    copied.value = false
    passwordCopied.value = false
  }
})

function autoGeneratePassword() {
  // 4 位数字密码
  password.value = String(Math.floor(1000 + Math.random() * 9000))
}

async function copyToClipboard(text) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text)
    } else {
      // Fallback for non-secure contexts
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      try { document.execCommand('copy') } catch (_) {}
      document.body.removeChild(ta)
    }
    return true
  } catch {
    return false
  }
}

async function copyUrl() {
  const ok = await copyToClipboard(SHARE_BASE_URL.value)
  if (ok) {
    copied.value = true
    ElMessage.success('链接已复制到剪贴板')
    setTimeout(() => (copied.value = false), 2000)
  } else {
    ElMessage.error('复制失败, 请手动选择文本复制')
  }
}

async function copyPassword() {
  const ok = await copyToClipboard(password.value)
  if (ok) {
    passwordCopied.value = true
    ElMessage.success('提取码已复制到剪贴板')
    setTimeout(() => (passwordCopied.value = false), 2000)
  }
}

function formatExpires(isoString) {
  if (!isoString) return '永久'
  try {
    return new Date(isoString).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return isoString
  }
}

async function generate() {
  if (!props.file?.id) {
    ElMessage.error('请先选择文件')
    return
  }
  if (usePassword.value && password.value) {
    if (!/^\d{4,8}$/.test(password.value)) {
      ElMessage.warning('提取码必须是 4-8 位数字')
      return
    }
  }
  generating.value = true
  try {
    const resp = await fetch('/api/v1/drive/files/' + props.file.id + '/share-link', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + (localStorage.getItem('access_token') || '')
      },
      body: JSON.stringify({
        expires_hours: expiresHours.value,
        password: usePassword.value && password.value ? password.value : null
      })
    })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}))
      throw new Error(err.detail || err.error?.message || 'HTTP ' + resp.status)
    }
    const data = await resp.json()
    result.value = {
      token: data.token,
      shareUrl: data.share_url,
      expiresAt: data.expires_at,
      passwordRequired: data.password_required,
      password: password.value  // 保留明文给复制按钮
    }
    emit('shared', {
      token: data.token,
      url: data.share_url,
      passwordRequired: data.password_required,
      expiresAt: data.expires_at
    })
  } catch (e) {
    ElMessage.error(e.message || '生成失败')
  } finally {
    generating.value = false
  }
}

function resetForAnother() {
  result.value = null
  copied.value = false
  passwordCopied.value = false
}
</script>

<style scoped>
.share-intro {
  font-size: 13px;
  color: var(--color-text-secondary, #606266);
  margin: 0 0 16px;
  padding: 12px;
  background: var(--color-bg-page, #fafbfc);
  border-radius: 4px;
  line-height: 1.6;
}

.share-field {
  margin-bottom: 18px;
}

.share-field-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary, #303133);
  margin-bottom: 8px;
}

.share-radio-group {
  width: 100%;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.share-radio-group :deep(.el-radio) {
  margin-right: 8px;
}

.share-password-input :deep(.el-input-group__append) {
  background: var(--color-bg-page, #fafbfc);
}

.share-hint {
  font-size: 11px;
  color: var(--color-text-placeholder, #909399);
  margin: 4px 0 0;
}

.share-result-detail {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin: 0;
}

.share-url-box {
  margin-top: 16px;
}

.share-url-input :deep(.el-input__inner) {
  font-family: 'SF Mono', Monaco, Consolas, monospace;
  font-size: 12px;
  background: var(--color-bg-page, #fafbfc);
}

.share-password-display {
  margin-top: 16px;
  padding: 12px;
  background: var(--color-warning-bg, #fdf6ec);
  border-radius: 4px;
  border: 1px solid var(--color-warning-border, #faecd8);
}

.share-password-label {
  font-size: 12px;
  color: var(--color-text-secondary, #606266);
  margin: 0 0 8px;
  font-weight: 600;
}

.share-password-value-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.share-password-value {
  font-family: 'SF Mono', Monaco, Consolas, monospace;
  font-size: 18px;
  font-weight: 700;
  color: var(--color-warning, #e6a23c);
  background: var(--el-color-white, #ffffff);
  padding: 6px 12px;
  border-radius: 4px;
  border: 1px dashed var(--color-warning, #e6a23c);
  letter-spacing: 2px;
}

.share-expires {
  margin-top: 12px;
  font-size: 12px;
  color: var(--color-text-placeholder, #909399);
  text-align: center;
}
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块
  本组件 PR3.7 统一审计 dark 模式时再加 dark 块
-->
