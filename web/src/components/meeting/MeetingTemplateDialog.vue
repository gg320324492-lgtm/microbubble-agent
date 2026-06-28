<!--
  MeetingTemplateDialog.vue — 模板编辑对话框（创建/编辑自定义模板）
  v77 P2.6-F.2 Step 3: 从 MeetingView.vue 拆分

  父组件: MeetingView.vue
  Props: modelValue (v-model:show) / editingTemplate (Object|null, null=新建) / members (Array) / isMobile (Bool)
  Emits: update:modelValue / saved

  复用模式（v77 P2.6-E.3 KnowledgeCreateDialog）:
  - v-model bridge: computed { get, set } 桥接 modelValue prop
  - TDZ 防御: resetForm 必须 function declaration（commit 7f0ac109 教训第 1 次复用）
  - watch(immediate: true) 监听 editingTemplate 变化回填表单
  - dark 块必须非 scoped <style>（v60-v67 教训第 7 次强化）
-->
<template>
  <el-dialog
    v-model="visible"
    :title="editingTemplate ? '编辑模板' : '存为新模板'"
    :width="isMobile ? '92vw' : '500px'"
    top="8vh"
  >
    <el-form :model="form" label-width="80px">
      <el-form-item label="模板名称" required>
        <el-input v-model="form.name" name="template-form-name" placeholder="如：组会、组内复盘..." maxlength="50" show-word-limit />
      </el-form-item>
      <el-form-item label="默认时长">
        <el-input-number v-model="form.default_duration_minutes" name="template-form-duration" :min="15" :max="240" :step="15" />
        <span class="form-hint">分钟</span>
      </el-form-item>
      <el-form-item label="默认地点">
        <el-input v-model="form.default_location" name="template-form-location" placeholder="可选，如：组会室、腾讯会议..." maxlength="100" />
      </el-form-item>
      <el-form-item label="会议说明">
        <el-input v-model="form.description" name="template-form-description" type="textarea" :rows="2" placeholder="可选" />
      </el-form-item>
      <el-form-item label="标题模板">
        <el-input v-model="form.title_template" name="template-form-title-template" placeholder="可选，支持 {date} 占位符" maxlength="100" />
        <div class="form-hint">如：组会 - {date}</div>
      </el-form-item>
      <el-form-item label="默认议题">
        <div class="item-list" style="width:100%">
          <div v-for="(item, idx) in form.agenda" :key="idx" class="item-row">
            <span class="item-dot" />
            <el-input v-model="form.agenda[idx]" :name="`template-form-agenda-${idx}`" placeholder="议题描述" />
            <el-button :icon="Delete" circle size="small" class="item-del" @click="form.agenda.splice(idx, 1)" />
          </div>
          <el-button dashed size="small" class="item-add" @click="form.agenda.push('')">
            <el-icon><Plus /></el-icon> 添加议题
          </el-button>
        </div>
      </el-form-item>
      <el-form-item label="默认参与人">
        <el-select v-model="form.default_participant_ids" name="template-form-participants" multiple filterable collapse-tags collapse-tags-tooltip placeholder="可选" style="width:100%">
          <el-option v-for="member in members" :key="member.id" :label="member.name" :value="member.id" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSubmit">
        {{ editingTemplate ? '保存' : '创建' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
/**
 * MeetingTemplateDialog.vue — 模板编辑对话框
 *
 * ★ TDZ 防御（v77 P2.6-E.3 + commit 7f0ac109 教训第 1 次复用）:
 *   resetForm 必须 function declaration 而非 const arrow，
 *   watch(immediate: true) 同步触发时会捕获 TDZ → 'Cannot access 'resetForm' before initialization'
 *   minify 后报错变 "f is not defined"，整个 dialog 路由白屏
 */
import { ref, computed, watch } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { Delete, Plus } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  editingTemplate: { type: Object, default: null },
  members: { type: Array, default: () => [] },
  isMobile: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'saved'])

// v-model bridge（KnowledgeCreateDialog line 96-100 模式）
const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const defaultForm = () => ({
  name: '',
  description: '',
  title_template: '',
  default_duration_minutes: 60,
  default_location: '',
  default_participant_ids: [],
  agenda: [],
})

const form = ref(defaultForm())
const saving = ref(false)

// ★ 必须 function declaration 而非 const arrow
function resetForm() {
  form.value = defaultForm()
}

// v77 P2.6-E.3 模式：监听 editingTemplate 变化回填表单
watch(() => props.editingTemplate, (val) => {
  if (val) {
    form.value = {
      name: val.name || '',
      description: val.description || '',
      title_template: val.title_template || '',
      default_duration_minutes: val.default_duration_minutes || 60,
      default_location: val.default_location || '',
      default_participant_ids: val.default_participant_ids || [],
      agenda: val.agenda ? [...val.agenda] : [],
    }
  } else {
    resetForm()
  }
}, { immediate: true })

const handleSubmit = async () => {
  if (!form.value.name?.trim()) {
    ElMessage.error('请填写模板名称')
    return
  }
  saving.value = true
  try {
    const payload = { ...form.value }
    if (props.editingTemplate) {
      await axios.put(`/api/v1/meeting-templates/${props.editingTemplate.id}`, payload)
      ElMessage.success('模板已更新')
    } else {
      await axios.post('/api/v1/meeting-templates', payload)
      ElMessage.success('模板已创建')
    }
    visible.value = false
    emit('saved')
  } catch (e) {
    ElMessage.error(`保存失败：${e.response?.data?.detail || e.message}`)
  } finally {
    saving.value = false
  }
}

defineExpose({ resetForm, handleSubmit })
</script>

<style scoped>
.form-hint { font-size: 11px; color: var(--color-text-placeholder); margin-left: 8px; }
.item-list { display: flex; flex-direction: column; gap: 8px; }
.item-row {
  display: flex; align-items: center; gap: 10px;
  padding: 6px 10px; background: var(--color-bg-page); border-radius: var(--radius-md);
  border: 1px solid transparent; transition: var(--transition-all-normal);
}
.item-row:hover, .item-row:focus-within {
  border-color: var(--color-primary-border); background: var(--color-primary-bg);
}
.item-dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
  background: var(--color-primary);
}
.item-del { opacity: 0; transition: opacity 0.2s; }
.item-row:hover .item-del { opacity: 1; }
.item-add { width: 100%; justify-content: center; border-style: dashed; }
</style>

<!-- v60-v67 教训第 7 次强化: dark mode 必须非 scoped -->
<style>
[data-theme="dark"] .item-row { background: var(--color-bg-page); }
[data-theme="dark"] .form-hint { color: var(--color-text-placeholder); }
</style>