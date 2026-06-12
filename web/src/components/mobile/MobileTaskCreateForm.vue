<template>
  <MobileFormSheet
    v-model:show="show"
    :title="editingTask ? '编辑任务' : '创建任务'"
    :fields="fields"
    v-model:form="form"
    :submit-text="editingTask ? '更新' : '创建'"
    :submitting="submitting"
    @submit="onSubmit"
  />
</template>

<script setup>
/**
 * MobileTaskCreateForm.vue — 移动端任务创建/编辑表单
 *
 * PR #6: 用 MobileFormSheet 配置化渲染（不用 el-dialog + CSS 全屏）
 * - 6 个字段：title / assignee_id / priority / due_date / description
 * - 字段配置在 fields[] 中定义
 * - 数据流：v-model:form 双向绑定
 *
 * 用法：
 *   <MobileTaskCreateForm
 *     v-model:show="showCreate"
 *     :editing-task="task"
 *     @success="onSuccess"
 *   />
 *
 * 关键纪律：
 * - 桌面端 TaskCreateDialog 保持原样（不删）
 * - 移动端组件独立使用 MobileFormSheet
 * - 数据层 useTask composable 共用
 */

import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useMemberStore } from '@/stores/member'
import { useTask } from '@/composables/useTask'
import MobileFormSheet from '@/components/mobile/MobileFormSheet.vue'

const props = defineProps({
  editingTask: { type: Object, default: null },
})
const emit = defineEmits(['success', 'update:show'])

const show = defineModel('show', { default: false })

const memberStore = useMemberStore()
const { createTask, updateTask } = useTask()

const submitting = ref(false)

const defaultForm = () => ({
  title: '',
  assignee_id: null,
  priority: 'medium',
  status: 'in_progress',
  due_date: null,
  description: '',
  reminders: [],
})

const form = ref(defaultForm())

// 字段配置（MobileFormSheet 渲染）
const fields = computed(() => [
  {
    key: 'title',
    label: '任务标题',
    type: 'input',
    required: true,
    placeholder: '请输入任务标题',
    maxlength: 100,
  },
  {
    key: 'assignee_id',
    label: '负责人',
    type: 'select',
    placeholder: '选择负责人',
    options: [
      { value: null, label: '未分配' },
      ...memberStore.members.map((m) => ({ value: m.id, label: m.name })),
    ],
  },
  {
    key: 'priority',
    label: '优先级',
    type: 'radio',
    required: true,
    options: [
      { value: 'high', label: '🔴 高' },
      { value: 'medium', label: '🟡 中' },
      { value: 'low', label: '🟢 低' },
    ],
  },
  {
    key: 'due_date',
    label: '截止日期',
    type: 'date',
    placeholder: '选择截止日期',
  },
  {
    key: 'description',
    label: '描述',
    type: 'textarea',
    placeholder: '详细描述任务内容...',
    rows: 4,
    maxlength: 500,
  },
])

// 监听编辑对象变化
watch(
  () => props.editingTask,
  (task) => {
    if (task) {
      form.value = {
        title: task.title || '',
        assignee_id: task.assignee_id || null,
        priority: task.priority || 'medium',
        status: task.status || 'in_progress',
        due_date: task.due_date ? String(task.due_date).slice(0, 10) : null,
        description: task.description || '',
        reminders: task.reminders || [],
      }
    } else {
      form.value = defaultForm()
    }
  },
  { immediate: true }
)

// 监听显示状态：关闭时重置表单
watch(show, (v) => {
  if (!v && !props.editingTask) {
    form.value = defaultForm()
  }
})

// 提交
async function onSubmit(submittedForm) {
  submitting.value = true
  try {
    if (props.editingTask) {
      await updateTask(props.editingTask.id, submittedForm)
      ElMessage.success('任务更新成功')
    } else {
      await createTask(submittedForm)
      ElMessage.success('任务创建成功')
    }
    show.value = false
    emit('success')
  } catch (e) {
    ElMessage.error(e.response?.data?.error?.message || e.message || '操作失败')
  } finally {
    submitting.value = false
  }
}
</script>