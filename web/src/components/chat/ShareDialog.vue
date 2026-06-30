<!--
  ShareDialog.vue — #043 Phase 6 分享会话对话框

  - 选择权限（read）+ 有效期（1h/1d/7d/30d/永久）
  - 调 chatHistoryStore.createShareLink 生成 share_url
  - 复制 URL（navigator.clipboard.writeText + 降级方案）
-->
<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="onModelUpdate"
    title="分享会话"
    :width="isMobile ? '90vw' : '480px'"
    top="8vh"
    destroy-on-close
    @open="onOpen"
  >
    <div v-if="session" class="share-dialog">
      <div class="session-preview">
        <div class="session-title">{{ session.title || '新对话' }}</div>
        <div class="session-meta">
          {{ session.messageCount || 0 }} 条消息 · 创建于 {{ formatDate(session.createdAt || session.created_at) }}
        </div>
      </div>

      <el-form :model="form" label-width="80px">
        <el-form-item label="权限">
          <el-radio-group v-model="form.permission">
            <el-radio value="read">仅查看（只读）</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="有效期">
          <el-select v-model="form.expiresHours" placeholder="永不过期" clearable style="width: 100%">
            <el-option label="1 小时" :value="1" />
            <el-option label="1 天" :value="24" />
            <el-option label="7 天" :value="168" />
            <el-option label="30 天" :value="720" />
          </el-select>
        </el-form-item>
      </el-form>

      <div v-if="shareUrl" class="share-result">
        <el-alert type="success" :closable="false" show-icon>
          <template #title>分享链接已生成</template>
          <template #default>任何拿到此链接的人都能查看会话内容（只读）</template>
        </el-alert>
        <div class="share-url-row">
          <el-input
            :model-value="shareUrl"
            readonly
            name="share-url-display"
          >
            <template #append>
              <el-button @click="copyUrl" :icon="CopyDocument">复制</el-button>
            </template>
          </el-input>
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="onModelUpdate(false)">关闭</el-button>
      <el-button v-if="!shareUrl" type="primary" :loading="generating" @click="onGenerate">
        生成分享链接
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { CopyDocument } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useChatHistoryStore } from '@/stores/chatHistory'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  session: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue'])

const chatHistoryStore = useChatHistoryStore()

const isMobile = computed(() => window.innerWidth <= 768)
const generating = ref(false)
const shareUrl = ref(null)

const form = reactive({
  permission: 'read',
  expiresHours: null,
})

function onModelUpdate(v) {
  if (!v) {
    // 关闭时清状态
    shareUrl.value = null
    form.permission = 'read'
    form.expiresHours = null
  }
  emit('update:modelValue', v)
}

function onOpen() {
  shareUrl.value = null
  form.permission = 'read'
  form.expiresHours = null
}

async function onGenerate() {
  if (!props.session?.id) return
  generating.value = true
  try {
    const opts = { permission: form.permission }
    if (form.expiresHours) opts.expiresHours = form.expiresHours
    const result = await chatHistoryStore.createShareLink(props.session.id, opts)
    if (result?.share_url) {
      // share_url 是相对路径 /api/v1/chat/shares/<token>，补 origin 便于直接打开
      const origin = window.location.origin
      shareUrl.value = result.share_url.startsWith('http')
        ? result.share_url
        : `${origin}${result.share_url}`
    } else {
      ElMessage.error('生成分享链接失败')
    }
  } finally {
    generating.value = false
  }
}

async function copyUrl() {
  if (!shareUrl.value) return
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(shareUrl.value)
      ElMessage.success('已复制到剪贴板')
    } else {
      // 降级：execCommand('copy')
      const textarea = document.createElement('textarea')
      textarea.value = shareUrl.value
      textarea.style.position = 'fixed'
      textarea.style.opacity = '0'
      document.body.appendChild(textarea)
      textarea.select()
      const ok = document.execCommand('copy')
      document.body.removeChild(textarea)
      if (ok) ElMessage.success('已复制到剪贴板')
      else ElMessage.error('复制失败，请手动选择 URL 复制')
    }
  } catch (e) {
    ElMessage.error('复制失败：' + (e?.message || '未知错误'))
  }
}

function formatDate(iso) {
  if (!iso) return '未知时间'
  try {
    return new Date(iso).toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
  } catch { return '未知时间' }
}
</script>

<style scoped>
.share-dialog { padding: 4px 0; }
.session-preview {
  padding: 12px; margin-bottom: 16px;
  background: var(--color-bg-warm, #f8f9fa);
  border-radius: 8px;
}
.session-title { font-size: 14px; font-weight: 500; color: var(--color-text-primary); }
.session-meta { font-size: 12px; color: var(--color-text-secondary); margin-top: 4px; }
.share-result { margin-top: 12px; }
.share-url-row { margin-top: 8px; }
</style>

<!-- v77 P2.6 / v69 P1b: dark 覆盖（v60-v67 教训：必须非 scoped） -->
<style>
[data-theme="dark"] .session-preview { background: var(--color-bg-warm); }
[data-theme="dark"] .session-title { color: var(--color-text-primary); }
[data-theme="dark"] .session-meta { color: var(--color-text-secondary); }
</style>
