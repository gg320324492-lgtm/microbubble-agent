<!--
  ShareLinkDialog.vue — 课题组网盘 v2 Folder Share Link Dialog (W72 第 2 批 B-1)

  功能 (W72 第 2 批 B-1 差量):
  - 过期时间: 1天/7天/30天 (1-365 天)
  - 密码保护: 4-8 位数字 (可选, 默认开启)
  - 下载次数限制: 1/3/5/10/不限 (可选, 默认不限)
  - 创建 → 复制 URL → 复制密码 → 撤销 完整流

  与现有 ShareDialog.vue 区别:
  - ShareDialog.vue: 单文件 share-link (Knowledge.share_token, PR2.7)
  - ShareLinkDialog.vue: folder 共享链接 (DriveFolderShare, PR7 增强)

  dark mode: 末尾非 scoped 块 (v60-v67 教训, v77 P2.6 6 主题)

  Props:
  - modelValue: 显隐 (v-model:show)
  - folder: {id, name}

  Events:
  - @update:modelValue 关闭
  - @created (share) 创建成功后
  - @revoked (share_id) 撤销后
-->
<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    class="drive-dialog share-link-dialog"
    title="🔗 创建 Folder 共享链接"
    width="540px"
    top="12vh"
    :close-on-press-escape="!submitting"
    :show-close="!submitting"
  >
    <!-- 表单态 -->
    <div v-if="!result" class="share-link-form">
      <p class="share-link-intro">
        将创建 "<strong>{{ folder?.name }}</strong>" 的公开访问链接,
        收到链接 + 提取码 + 在次数限额内 的人可访问 folder 下的文件.
      </p>

      <!-- 过期时间 -->
      <div class="share-link-field">
        <label class="share-link-field-label">过期时间</label>
        <el-radio-group v-model="expiresDays" class="share-link-radio-group">
          <el-radio :value="1">1 天</el-radio>
          <el-radio :value="7">7 天</el-radio>
          <el-radio :value="30">30 天</el-radio>
        </el-radio-group>
      </div>

      <!-- 密码保护 -->
      <div class="share-link-field">
        <label class="share-link-field-label">提取码保护</label>
        <el-switch
          v-model="usePassword"
          active-text="启用 4-8 位数字提取码"
          inactive-text="无密码公开分享"
        />
      </div>

      <div v-if="usePassword" class="share-link-field share-link-sub-field">
        <label class="share-link-field-label">提取码</label>
        <el-input
          v-model="password"
          placeholder="4-8 位数字"
          maxlength="8"
          show-password
          clearable
          class="share-link-password-input"
        >
          <template #append>
            <el-button @click="autoGeneratePassword">
              <el-icon><Refresh /></el-icon>
              随机
            </el-button>
          </template>
        </el-input>
      </div>

      <!-- 下载次数限制 (W72-B-1 差量) -->
      <div class="share-link-field">
        <label class="share-link-field-label">下载次数限制</label>
        <el-radio-group v-model="maxDownloadsOption" class="share-link-radio-group">
          <el-radio :value="null">不限</el-radio>
          <el-radio :value="1">1 次</el-radio>
          <el-radio :value="3">3 次</el-radio>
          <el-radio :value="5">5 次</el-radio>
          <el-radio :value="10">10 次</el-radio>
        </el-radio-group>
        <p class="share-link-hint">
          达到上限后链接自动失效; 仅 folder 浏览不计入下载
        </p>
      </div>
    </div>

    <!-- 结果态 -->
    <div v-else class="share-link-result">
      <el-result icon="success" title="分享链接已创建">
        <template #sub-title>
          <p class="share-link-result-detail">
            链接有效期至 <strong>{{ formatExpires(result.expires_at) }}</strong>
            <span v-if="result.has_password"> · 提取码保护</span>
            <span v-if="result.max_downloads">
              · 限 {{ result.max_downloads }} 次下载 (已用 {{ result.download_count }})
            </span>
          </p>
        </template>
      </el-result>

      <div class="share-link-url-row">
        <el-input v-model="shareUrl" readonly class="share-link-url-input">
          <template #prepend>🔗 URL</template>
        </el-input>
        <el-button type="primary" @click="copyUrl" class="share-link-copy-btn">
          <el-icon><DocumentCopy /></el-icon>
          {{ copied ? '已复制' : '复制' }}
        </el-button>
      </div>

      <div v-if="result.has_password" class="share-link-url-row">
        <el-input v-model="password" readonly class="share-link-password-display">
          <template #prepend>🔑 提取码</template>
        </el-input>
        <el-button @click="copyPassword" class="share-link-copy-btn">
          <el-icon><DocumentCopy /></el-icon>
          {{ passwordCopied ? '已复制' : '复制' }}
        </el-button>
      </div>

      <div class="share-link-actions">
        <el-button type="danger" plain @click="revokeShare">
          <el-icon><CircleClose /></el-icon>
          立即撤销
        </el-button>
        <el-button type="primary" @click="reset">
          <el-icon><Plus /></el-icon>
          再创建一个
        </el-button>
      </div>
    </div>

    <!-- 表单态 footer -->
    <template v-if="!result" #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="createShare">
        生成链接
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { DocumentCopy, Refresh, CircleClose, Plus } from '@element-plus/icons-vue'
import '@/views/drive/drive-view.css'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  folder: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue', 'created', 'revoked'])

// === 状态 ===
const expiresDays = ref(7)              // 默认 7 天
const usePassword = ref(true)           // 默认启用密码
const password = ref('1234')            // 默认密码 (前端占位, 创建后服务端哈希)
const maxDownloadsOption = ref(null)    // 默认不限 (W72-B-1 差量)
const submitting = ref(false)
const result = ref(null)                // 创建成功的 share 对象
const copied = ref(false)
const passwordCopied = ref(false)

const shareUrl = computed(() => {
  if (typeof window !== 'undefined' && result.value?.share_token) {
    return `${window.location.origin}/drive/share/${result.value.share_token}`
  }
  return ''
})

watch(usePassword, (val) => {
  if (val && !password.value) {
    autoGeneratePassword()
  }
})

watch(() => props.modelValue, (open) => {
  if (open) {
    // 打开时重置
    result.value = null
    expiresDays.value = 7
    usePassword.value = true
    password.value = '1234'
    maxDownloadsOption.value = null
    submitting.value = false
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
  const ok = await copyToClipboard(shareUrl.value)
  if (ok) {
    copied.value = true
    ElMessage.success('链接已复制到剪贴板')
    setTimeout(() => (copied.value = false), 2000)
  } else {
    ElMessage.error('复制失败, 请手动选择')
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

async function createShare() {
  if (!props.folder?.id) {
    ElMessage.error('请先选择 folder')
    return
  }
  if (usePassword.value && !/^\d{4,8}$/.test(password.value)) {
    ElMessage.warning('提取码必须是 4-8 位数字')
    return
  }
  submitting.value = true
  try {
    const body = {
      permission: 'read',
      expires_days: expiresDays.value,
      password: usePassword.value ? password.value : null,
      max_downloads: maxDownloadsOption.value,
    }
    const resp = await fetch(
      `/api/v1/drive/folders/${props.folder.id}/share`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(body),
      }
    )
    if (!resp.ok) {
      const errText = await resp.text().catch(() => '')
      throw new Error(errText || `HTTP ${resp.status}`)
    }
    const data = await resp.json()
    result.value = data
    emit('created', data)
    ElMessage.success('分享链接已创建')
  } catch (e) {
    ElMessage.error(`创建失败: ${e.message}`)
  } finally {
    submitting.value = false
  }
}

async function revokeShare() {
  if (!result.value?.id) return
  try {
    const resp = await fetch(
      `/api/v1/drive/folders/share/${result.value.id}`,
      { method: 'DELETE', credentials: 'include' }
    )
    if (!resp.ok) {
      const errText = await resp.text().catch(() => '')
      throw new Error(errText || `HTTP ${resp.status}`)
    }
    ElMessage.success('链接已撤销')
    emit('revoked', result.value.id)
    result.value = null
  } catch (e) {
    ElMessage.error(`撤销失败: ${e.message}`)
  }
}

function reset() {
  result.value = null
  expiresDays.value = 7
  usePassword.value = true
  password.value = '1234'
  maxDownloadsOption.value = null
  copied.value = false
  passwordCopied.value = false
}
</script>

<style scoped>
.share-link-intro {
  margin: 0 0 16px;
  color: var(--color-text-regular, #606266);
  font-size: 13px;
  line-height: 1.6;
}
.share-link-field {
  margin-bottom: 16px;
}
.share-link-sub-field {
  padding-left: 12px;
  border-left: 2px solid var(--color-primary-light, #fde2e2);
}
.share-link-field-label {
  display: block;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary, #303133);
}
.share-link-radio-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.share-link-radio-group :deep(.el-radio) {
  margin-right: 0;
}
.share-link-hint {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--color-text-secondary, #909399);
}
.share-link-password-input :deep(.el-input-group__append) {
  background: transparent;
}
.share-link-result-detail {
  margin: 0;
  color: var(--color-text-regular, #606266);
  font-size: 13px;
}
.share-link-url-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.share-link-url-input,
.share-link-password-display {
  flex: 1;
}
.share-link-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--color-border-light, #ebeef5);
}
</style>

<!--
  v77 P2.6 6 主题 dark mode 非 scoped 块 (CLAUDE.md 永久锚点)
  必须非 scoped 才能跨 dark/ocean/theme 切换生效
-->
<style>
.share-link-dialog.el-dialog {
  border-radius: 12px;
  backdrop-filter: blur(16px);
  background: var(--color-bg-card, #fff);
}
html.dark .share-link-dialog.el-dialog,
html[data-theme='dark'] .share-link-dialog.el-dialog {
  background: rgba(30, 30, 30, 0.95);
}
html.ocean .share-link-dialog.el-dialog {
  background: rgba(232, 244, 250, 0.95);
}
</style>