<!--
  TagsEditor.vue — #043 Phase 6 标签 / 收藏 / 归档 编辑对话框

  - 标签输入（el-select multiple filterable allow-create，键盘回车新增）
  - 收藏 toggle
  - 归档 toggle
  - 调 chatSessionsStore.setTags / setPinned / setArchived（已实现双向同步 server）
-->
<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="onModelUpdate"
    title="编辑标签 / 收藏 / 归档"
    :width="isMobile ? '90vw' : '500px'"
    top="8vh"
    destroy-on-close
    @open="onOpen"
  >
    <div v-if="session" class="tags-editor">
      <div class="session-preview">
        <div class="session-title">{{ session.title || '新对话' }}</div>
        <div class="session-meta">{{ session.messageCount || 0 }} 条消息</div>
      </div>

      <el-form label-width="80px">
        <el-form-item label="标签">
          <el-select
            v-model="formTags"
            multiple
            filterable
            allow-create
            default-first-option
            :reserve-keyword="false"
            name="chat-tags-input"
            placeholder="输入标签后回车"
            style="width: 100%"
          >
            <el-option
              v-for="tag in availableTags"
              :key="tag"
              :label="tag"
              :value="tag"
            />
          </el-select>
          <div class="field-hint">按回车保存新标签</div>
        </el-form-item>

        <el-form-item label="收藏">
          <el-switch
            v-model="formPinned"
            inline-prompt
            active-text="已收藏"
            inactive-text="未收藏"
          />
        </el-form-item>

        <el-form-item label="归档">
          <el-switch
            v-model="formArchived"
            inline-prompt
            active-text="已归档"
            inactive-text="未归档"
          />
          <div class="field-hint">归档后会话从侧栏默认列表隐藏（搜索仍可见）</div>
        </el-form-item>
      </el-form>
    </div>

    <template #footer>
      <el-button @click="onModelUpdate(false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useChatSessionsStore } from '@/stores/chatSessions'
import { useChatHistoryStore } from '@/stores/chatHistory'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  session: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue'])

const chatSessionsStore = useChatSessionsStore()
const chatHistoryStore = useChatHistoryStore()

const isMobile = computed(() => window.innerWidth <= 768)
const saving = ref(false)

const formTags = ref([])
const formPinned = ref(false)
const formArchived = ref(false)

/** 全局已有标签（从服务端会话聚合去重） */
const availableTags = computed(() => {
  const set = new Set()
  for (const s of chatHistoryStore.serverSessions || []) {
    for (const t of (s.tags || [])) set.add(t)
  }
  return Array.from(set).sort()
})

function onOpen() {
  if (!props.session) return
  formTags.value = [...(props.session.tags || [])]
  formPinned.value = !!props.session.is_pinned
  formArchived.value = !!props.session.is_archived
}

function onModelUpdate(v) {
  if (!v) {
    formTags.value = []
    formPinned.value = false
    formArchived.value = false
  }
  emit('update:modelValue', v)
}

async function onSave() {
  if (!props.session?.id) return
  saving.value = true
  try {
    // 三个调用互不依赖，并发跑（best-effort，内部已 try/catch）
    const tasks = []
    tasks.push(chatSessionsStore.setTags(props.session.id, [...formTags.value]))
    if (formPinned.value !== !!props.session.is_pinned) {
      tasks.push(chatSessionsStore.setPinned(props.session.id, formPinned.value))
    }
    if (formArchived.value !== !!props.session.is_archived) {
      tasks.push(chatSessionsStore.setArchived(props.session.id, formArchived.value))
    }
    await Promise.all(tasks)
    ElMessage.success('已保存')
    emit('update:modelValue', false)
  } catch (e) {
    ElMessage.error('保存失败：' + (e?.message || '未知错误'))
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.tags-editor { padding: 4px 0; }
.session-preview {
  padding: 12px; margin-bottom: 16px;
  background: var(--color-bg-warm, #f8f9fa);
  border-radius: 8px;
}
.session-title { font-size: 14px; font-weight: 500; color: var(--color-text-primary); }
.session-meta { font-size: 12px; color: var(--color-text-secondary); margin-top: 4px; }
.field-hint { font-size: 11px; color: var(--color-text-secondary); margin-top: 4px; line-height: 1.4; }
</style>

<!-- v77 P2.6 / v69 P1b: dark 覆盖（v60-v67 教训：必须非 scoped） -->
<style>
[data-theme="dark"] .session-preview { background: var(--color-bg-warm); }
[data-theme="dark"] .session-title { color: var(--color-text-primary); }
[data-theme="dark"] .session-meta { color: var(--color-text-secondary); }
[data-theme="dark"] .field-hint { color: var(--color-text-secondary); }
</style>
