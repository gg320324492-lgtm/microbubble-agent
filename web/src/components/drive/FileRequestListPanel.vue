<!--
  FileRequestListPanel.vue — 文件请求 inline Panel (2026-07-02)

  设计:
  - 从 FileRequestListView 抽取 body 内容 (toolbar + list + Create Dialog + Preview Dialog)
  - 不含 page-container / page-header (由 DesktopDriveView 上下文提供, breadcrumb 显示当前视图)
  - 当 DesktopDriveView 的 specialView === 'requests' 时 inline 渲染
  - URL 直跳 /drive/requests 仍走 FileRequestListView 全屏版 (保留 mobile + URL 兼容性)

  Props: 无 (self-contained, 通过 useFileRequests composable 取数)

  Dialog 必须在 Panel 模板根 div 内 (与列表同上下文, 共享 showCreate/showPreview ref)

  Dark mode: 用 var(--color-*) token + 非 scoped dark 块 (v60-v67 教训)
-->
<template>
  <div class="file-request-list-panel">
    <!-- 工具栏 -->
    <div class="request-toolbar">
      <el-switch v-model="includeInactive" @change="onIncludeInactiveChange" />
      <span class="request-toolbar-label">包含已关闭/过期</span>
      <el-button link @click="onRefresh">刷新</el-button>
      <div class="request-toolbar-spacer" />
      <el-button type="primary" size="small" @click="showCreate = true">
        <el-icon><Plus /></el-icon>
        新建文件请求
      </el-button>
    </div>

    <!-- 列表/加载/空态 -->
    <div v-if="loading && requests.length === 0" class="request-loading">加载中...</div>

    <div v-else-if="!hasRequests" class="request-empty">
      <el-empty description="还没有文件请求。点击右上角'新建文件请求'开始收集文件。" />
    </div>

    <ul v-else class="request-list">
      <li v-for="req in requests" :key="req.id" class="request-item">
        <div class="request-main">
          <div class="request-title">
            <strong>{{ req.title }}</strong>
            <el-tag v-if="!req.active" size="small" type="info">已关闭</el-tag>
            <el-tag v-else-if="req.expired" size="small" type="warning">已过期</el-tag>
            <el-tag v-else size="small" type="success">活跃</el-tag>
          </div>
          <div v-if="req.description" class="request-desc">{{ req.description }}</div>
          <div class="request-meta">
            <span>已收到 <strong>{{ req.submission_count }}</strong> 份</span>
            <span v-if="req.expires_at">· 过期: {{ formatTime(req.expires_at) }}</span>
            <span v-if="req.allowed_extensions && req.allowed_extensions.length">· 仅限 {{ req.allowed_extensions.join(', ') }}</span>
            <span v-if="req.max_file_size_mb">· ≤ {{ req.max_file_size_mb }}MB</span>
            <span v-if="req.require_uploader_name">· 必填姓名</span>
          </div>
        </div>
        <div class="request-actions">
          <el-button link type="primary" @click="onCopyUrl(req)">复制链接</el-button>
          <el-button link type="primary" @click="onPreview(req)">预览</el-button>
          <el-button v-if="req.active" link type="danger" @click="onDeactivate(req)">关闭</el-button>
        </div>
      </li>
    </ul>

    <!-- Create Dialog (与列表同上下文, 不能拆出) -->
    <el-dialog v-model="showCreate" class="drive-dialog" title="新建文件请求" width="540px" :close-on-click-modal="false">
      <el-form :model="createForm" label-width="100px" ref="formRef">
        <el-form-item label="标题" required>
          <el-input v-model="createForm.title" placeholder="如: 2026 秋季作业" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="createForm.description" type="textarea" :rows="3" maxlength="2000" show-word-limit />
        </el-form-item>
        <el-form-item label="有效期">
          <el-select v-model="createForm.expires_in_days" placeholder="永久" clearable>
            <el-option label="1 天" :value="1" />
            <el-option label="7 天" :value="7" />
            <el-option label="30 天" :value="30" />
            <el-option label="90 天" :value="90" />
            <el-option label="365 天" :value="365" />
          </el-select>
        </el-form-item>
        <el-form-item label="允许类型">
          <el-input v-model="createForm.extensionsText" placeholder="如: pdf,docx,xlsx (留空=不限)" />
        </el-form-item>
        <el-form-item label="最大大小">
          <el-input-number v-model="createForm.max_file_size_mb" :min="1" :max="500" placeholder="MB (留空=不限)" :step="1" controls-position="right" style="width: 160px" />
        </el-form-item>
        <el-form-item label="必填姓名">
          <el-switch v-model="createForm.require_uploader_name" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="onCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- Preview Dialog -->
    <el-dialog v-model="showPreview" class="drive-dialog" title="公开链接" width="560px">
      <p>用户打开此链接即可匿名提交文件：</p>
      <el-input v-model="previewUrl" readonly>
        <template #append>
          <el-button @click="onCopyPreview">复制</el-button>
        </template>
      </el-input>
      <p class="preview-hint">也可以让用户扫描下方二维码（TODO）</p>
    </el-dialog>
  </div>
</template>

<script setup>
// v2.0 (2026-07-09) Drive 美化: 引入 drive-view.css 让 .drive-dialog 玻璃态生效
import '@/views/drive/drive-view.css'
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useFileRequests } from '@/composables/useFileRequests'

const {
  requests,
  loading,
  error,
  hasRequests,
  fetchMy,
  createRequest,
  deactivate,
} = useFileRequests()

const includeInactive = ref(false)
const showCreate = ref(false)
const showPreview = ref(false)
const previewUrl = ref('')
const creating = ref(false)
const formRef = ref(null)

const createForm = ref({
  title: '',
  description: '',
  expires_in_days: null,
  extensionsText: '',
  max_file_size_mb: null,
  require_uploader_name: true,
})

function parseExtensions(text) {
  if (!text) return null
  const list = text.split(/[,，\s]+/).map(s => s.trim().replace(/^\./, '').toLowerCase()).filter(Boolean)
  return list.length ? list : null
}

function formatTime(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleString('zh-CN', { hour12: false })
  } catch { return iso }
}

function onIncludeInactiveChange() {
  fetchMy(includeInactive.value)
}

async function onRefresh() {
  await fetchMy(includeInactive.value)
}

async function onCreate() {
  if (!createForm.value.title.trim()) {
    ElMessage.warning('请填写标题')
    return
  }
  creating.value = true
  try {
    const payload = {
      title: createForm.value.title.trim(),
      description: createForm.value.description || null,
      expires_in_days: createForm.value.expires_in_days || null,
      allowed_extensions: parseExtensions(createForm.value.extensionsText),
      max_file_size_mb: createForm.value.max_file_size_mb || null,
      require_uploader_name: createForm.value.require_uploader_name,
    }
    const created = await createRequest(payload)
    showCreate.value = false
    ElMessage.success(`创建成功！Token: ${created.token.slice(0, 12)}...`)
    createForm.value = {
      title: '',
      description: '',
      expires_in_days: null,
      extensionsText: '',
      max_file_size_mb: null,
      require_uploader_name: true,
    }
  } catch (e) {
    ElMessage.error(e.message || '创建失败')
  } finally {
    creating.value = false
  }
}

function getPublicUrl(token) {
  const origin = window.location.origin
  return `${origin}/r/${token}`
}

async function onCopyUrl(req) {
  const url = getPublicUrl(req.token)
  try {
    await navigator.clipboard.writeText(url)
    ElMessage.success(`已复制: ${url}`)
  } catch {
    ElMessage.warning('复制失败，请手动复制')
  }
}

function onPreview(req) {
  previewUrl.value = getPublicUrl(req.token)
  showPreview.value = true
}

async function onCopyPreview() {
  try {
    await navigator.clipboard.writeText(previewUrl.value)
    ElMessage.success('已复制')
  } catch {
    ElMessage.warning('复制失败')
  }
}

async function onDeactivate(req) {
  try {
    await ElMessageBox.confirm(
      `确定关闭文件请求「${req.title}」？关闭后用户无法继续提交。`,
      '关闭文件请求',
      { confirmButtonText: '关闭', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  const ok = await deactivate(req.id)
  if (ok) ElMessage.success('已关闭')
  else ElMessage.error('关闭失败')
}

onMounted(() => {
  fetchMy(false)
})
</script>

<style scoped>
.file-request-list-panel {
  /* Panel 内由 DesktopDriveView 主区提供 padding, 此处不重复 */
}
.request-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  padding: 8px 12px;
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
}
.request-toolbar-spacer { flex: 1; }
.request-toolbar-label {
  font-size: 13px;
  color: var(--color-text-secondary);
}
.request-loading, .request-empty {
  padding: 40px;
  text-align: center;
  color: var(--color-text-secondary);
}
.request-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.request-item {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 16px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}
.request-main { flex: 1; min-width: 0; }
.request-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  margin-bottom: 4px;
}
.request-desc {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-bottom: 6px;
}
.request-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  color: var(--color-text-secondary);
}
.request-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}
.preview-hint {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 12px;
}
</style>

<!-- v60-v67 教训: dark mode 跨组件覆盖必须非 scoped 块 -->
<style>
[data-theme="dark"] .file-request-list-panel .request-item {
  background: var(--color-bg-card);
  border-color: var(--color-border);
}
[data-theme="dark"] .file-request-list-panel .request-toolbar {
  background: var(--color-bg-card);
}
</style>
