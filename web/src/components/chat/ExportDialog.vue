<!--
  ExportDialog.vue — #043 Phase 6 导出会话对话框

  - 选择格式（Markdown / JSON）
  - 调 chatHistoryStore.exportToFile 拿 Blob
  - URL.createObjectURL + 动态 <a download> 触发浏览器下载
-->
<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="onModelUpdate"
    title="导出会话"
    :width="isMobile ? '90vw' : '480px'"
    top="8vh"
    destroy-on-close
  >
    <div v-if="session" class="export-dialog">
      <div class="session-preview">
        <div class="session-title">{{ session.title || '新对话' }}</div>
        <div class="session-meta">{{ session.messageCount || 0 }} 条消息</div>
      </div>

      <el-form :model="form" label-width="80px">
        <el-form-item label="格式">
          <el-radio-group v-model="form.format">
            <el-radio value="md">Markdown (.md)</el-radio>
            <el-radio value="json">JSON (.json)</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item>
          <div class="format-hint">
            <div v-if="form.format === 'md'">
              <el-icon><Document /></el-icon>
              Markdown 格式：标题 + 时间戳 + 用户/助手消息分块，适合人类阅读
            </div>
            <div v-else>
              <el-icon><DataAnalysis /></el-icon>
              JSON 格式：完整结构化数据（含 rich_blocks / tool_trace / metadata），适合程序处理
            </div>
          </div>
        </el-form-item>
      </el-form>
    </div>

    <template #footer>
      <el-button @click="onModelUpdate(false)">取消</el-button>
      <el-button type="primary" :loading="exporting" @click="onExport">下载</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { Document, DataAnalysis } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useChatHistoryStore } from '@/stores/chatHistory'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  session: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue'])

const chatHistoryStore = useChatHistoryStore()

const isMobile = computed(() => window.innerWidth <= 768)
const exporting = ref(false)

const form = reactive({
  format: 'md',
})

function onModelUpdate(v) {
  if (!v) form.format = 'md'
  emit('update:modelValue', v)
}

function sanitizeFilename(name) {
  return (name || 'chat')
    .replace(/[\\/:*?"<>|]/g, '_')
    .slice(0, 50)
    .trim() || 'chat'
}

async function onExport() {
  if (!props.session?.id) return
  exporting.value = true
  try {
    const blob = await chatHistoryStore.exportToFile(props.session.id, { format: form.format })
    if (!blob) {
      ElMessage.error('导出失败')
      return
    }
    // 触发浏览器下载
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${sanitizeFilename(props.session.title)}.${form.format}`
    a.style.display = 'none'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    // 延迟 revoke 避免浏览器取消下载
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    ElMessage.success('已下载')
    emit('update:modelValue', false)
  } catch (e) {
    ElMessage.error('导出失败：' + (e?.message || '未知错误'))
  } finally {
    exporting.value = false
  }
}
</script>

<style scoped>
.export-dialog { padding: 4px 0; }
.session-preview {
  padding: 12px; margin-bottom: 16px;
  background: var(--color-bg-warm, #f8f9fa);
  border-radius: 8px;
}
.session-title { font-size: 14px; font-weight: 500; color: var(--color-text-primary); }
.session-meta { font-size: 12px; color: var(--color-text-secondary); margin-top: 4px; }
.format-hint {
  font-size: 12px; color: var(--color-text-secondary);
  display: flex; align-items: center; gap: 6px;
  padding: 8px 12px;
  background: var(--color-primary-bg, #f0f7ff);
  border-radius: 6px;
  margin-top: 4px;
}
</style>

<!-- v77 P2.6 / v69 P1b: dark 覆盖（v60-v67 教训：必须非 scoped） -->
<style>
[data-theme="dark"] .session-preview { background: var(--color-bg-warm); }
[data-theme="dark"] .session-title { color: var(--color-text-primary); }
[data-theme="dark"] .session-meta { color: var(--color-text-secondary); }
[data-theme="dark"] .format-hint { background: var(--color-primary-bg); color: var(--color-text-secondary); }
</style>
