<!--
  FileRequestSubmitView.vue — v2 PR7 文件请求公开提交页 (无需登录)

  路由: /r/:token
  设计: 极简独立页, 不走 Element Plus 侧栏, 纯 CSS (纯净网盘 / OneDrive 文件请求 UX)
-->
<template>
  <div class="file-request-submit-public">
    <div class="submit-card">
      <h1 class="submit-title">📂 {{ requestInfo?.title || '文件请求' }}</h1>

      <div v-if="loading" class="submit-state">
        加载中...
      </div>

      <div v-else-if="!requestInfo" class="submit-state error">
        <h2>文件请求不存在</h2>
        <p>该链接可能已失效，请联系发起人重新生成。</p>
      </div>

      <div v-else-if="!requestInfo.active" class="submit-state error">
        <h2>文件请求已关闭</h2>
        <p v-if="requestInfo.expired">链接已于 {{ formatTime(requestInfo.expires_at) }} 过期。</p>
        <p v-else>发起人已关闭此文件请求，无法再提交文件。</p>
      </div>

      <div v-else class="submit-form">
        <div v-if="requestInfo.description" class="submit-desc">
          <p>{{ requestInfo.description }}</p>
        </div>

        <div class="submit-meta">
          <span v-if="requestInfo.allowed_extensions && requestInfo.allowed_extensions.length">
            仅限类型: {{ requestInfo.allowed_extensions.map(ext => '.' + ext).join(', ') }}
          </span>
          <span v-if="requestInfo.max_file_size_mb">≤ {{ requestInfo.max_file_size_mb }} MB</span>
          <span v-if="requestInfo.expires_at">截止: {{ formatTime(requestInfo.expires_at) }}</span>
        </div>

        <form @submit.prevent="onSubmit" enctype="multipart/form-data">
          <div v-if="requestInfo.require_uploader_name" class="form-row">
            <label>你的姓名 <span class="required">*</span></label>
            <input
              v-model="uploaderName"
              type="text"
              required
              maxlength="100"
              placeholder="如: 张三"
            />
          </div>

          <div class="form-row">
            <label>选择文件 <span class="required">*</span></label>
            <input
              ref="fileInput"
              type="file"
              required
              :accept="acceptTypes"
              @change="onFileChange"
            />
            <small v-if="file" class="file-info">
              {{ file.name }} · {{ formatSize(file.size) }}
            </small>
          </div>

          <button type="submit" :disabled="submitting || !canSubmit" class="submit-btn">
            {{ submitting ? '上传中...' : '提交文件' }}
          </button>

          <div v-if="errorMessage" class="submit-error">
            {{ errorMessage }}
          </div>
        </form>
      </div>

      <div v-if="submitted" class="submit-success">
        <h2>✅ 提交成功</h2>
        <p>感谢您提交文件「{{ submittedFileName }}」</p>
        <button @click="onSubmitAnother" class="submit-btn">再提交一份</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useFileRequests } from '@/composables/useFileRequests'

const route = useRoute()
const token = route.params.token

const { fetchPublicInfo, submitPublic } = useFileRequests()

const requestInfo = ref(null)
const loading = ref(true)
const uploaderName = ref('')
const file = ref(null)
const fileInput = ref(null)
const submitting = ref(false)
const errorMessage = ref('')
const submitted = ref(false)
const submittedFileName = ref('')

const acceptTypes = computed(() => {
  if (!requestInfo.value?.allowed_extensions?.length) return '*/*'
  return requestInfo.value.allowed_extensions.map(ext => '.' + ext).join(',')
})

const canSubmit = computed(() => {
  if (!requestInfo.value) return false
  if (requestInfo.value.require_uploader_name && !uploaderName.value.trim()) return false
  if (!file.value) return false
  return true
})

function formatTime(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleString('zh-CN', { hour12: false })
  } catch { return iso }
}

function formatSize(bytes) {
  if (!bytes) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function onFileChange(e) {
  const f = e.target.files[0]
  if (!f) return
  // 客户端检查扩展名 (服务端也查, 双重防御)
  if (requestInfo.value?.allowed_extensions?.length) {
    const ext = (f.name.split('.').pop() || '').toLowerCase()
    if (!requestInfo.value.allowed_extensions.includes(ext)) {
      errorMessage.value = `不允许的文件类型 .${ext}`
      file.value = null
      if (fileInput.value) fileInput.value.value = ''
      return
    }
  }
  // 客户端检查大小
  if (requestInfo.value?.max_file_size_mb) {
    const maxBytes = requestInfo.value.max_file_size_mb * 1024 * 1024
    if (f.size > maxBytes) {
      errorMessage.value = `文件 ${formatSize(f.size)} 超过 ${requestInfo.value.max_file_size_mb}MB 限制`
      file.value = null
      if (fileInput.value) fileInput.value.value = ''
      return
    }
  }
  file.value = f
  errorMessage.value = ''
}

async function onSubmit() {
  if (!canSubmit.value) return
  submitting.value = true
  errorMessage.value = ''
  try {
    const formData = new FormData()
    if (requestInfo.value.require_uploader_name) {
      formData.append('uploader_name', uploaderName.value.trim())
    }
    formData.append('file', file.value)
    await submitPublic(token, formData)
    submittedFileName.value = file.value.name
    submitted.value = true
    // 重置
    file.value = null
    if (fileInput.value) fileInput.value.value = ''
  } catch (e) {
    errorMessage.value = e?.response?.data?.detail || e?.message || '提交失败'
  } finally {
    submitting.value = false
  }
}

function onSubmitAnother() {
  submitted.value = false
  uploaderName.value = ''
}

onMounted(async () => {
  try {
    requestInfo.value = await fetchPublicInfo(token)
  } catch (e) {
    requestInfo.value = null
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.file-request-submit-public {
  min-height: 100vh;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf3 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
}

.submit-card {
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08);
  padding: 40px;
  max-width: 540px;
  width: 100%;
}

.submit-title {
  font-size: 24px;
  font-weight: 600;
  margin: 0 0 24px 0;
  color: #1a1a1a;
}

.submit-state {
  text-align: center;
  padding: 40px 20px;
  color: #666;
}
.submit-state.error h2 {
  color: #d9534f;
  font-size: 18px;
  margin-bottom: 8px;
}

.submit-desc {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 16px;
  font-size: 14px;
  color: #333;
  line-height: 1.5;
}

.submit-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  color: #888;
  margin-bottom: 20px;
}

.form-row {
  margin-bottom: 20px;
}
.form-row label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: #333;
  margin-bottom: 6px;
}
.required {
  color: #d9534f;
}
.form-row input[type="text"] {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 14px;
  box-sizing: border-box;
  font-family: inherit;
}
.form-row input[type="text"]:focus {
  outline: none;
  border-color: #4a90e2;
}
.form-row input[type="file"] {
  font-size: 14px;
  font-family: inherit;
}
.file-info {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: #888;
}

.submit-btn {
  display: block;
  width: 100%;
  padding: 12px;
  background: #FF7A5C;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
  font-family: inherit;
}
.submit-btn:hover:not(:disabled) {
  background: #ff5e3a;
}
.submit-btn:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.submit-error {
  margin-top: 12px;
  padding: 10px 14px;
  background: #fef0ef;
  border: 1px solid #fbc7c4;
  border-radius: 6px;
  color: #d9534f;
  font-size: 13px;
}

.submit-success {
  text-align: center;
  padding: 20px;
}
.submit-success h2 {
  color: #5cb85c;
  font-size: 22px;
  margin-bottom: 12px;
}
.submit-success p {
  color: #333;
  font-size: 14px;
  margin-bottom: 24px;
}
</style>
