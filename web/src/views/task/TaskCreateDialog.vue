<template>
  <el-dialog
    v-model="visible"
    :title="editingTask ? '编辑任务' : '创建任务'"
    width="500px"
    @close="onClose"
  >
    <el-form :model="form" label-width="80px">
      <el-form-item label="标题" required>
        <el-input v-model="form.title" placeholder="请输入任务标题" />
      </el-form-item>
      <el-form-item label="负责人">
        <el-select v-model="form.assignee_id" placeholder="选择负责人" clearable>
          <el-option
            v-for="member in members"
            :key="member.id"
            :label="member.name"
            :value="member.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="优先级">
        <el-select v-model="form.priority">
          <el-option label="高" value="high" />
          <el-option label="中" value="medium" />
          <el-option label="低" value="low" />
        </el-select>
      </el-form-item>
      <el-form-item label="截止日期">
        <el-date-picker
          v-model="form.due_date"
          type="datetime"
          placeholder="选择截止日期"
        />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" :rows="3" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="onSubmit">{{ editingTask ? '更新' : '创建' }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useMemberStore } from '@/stores/member'
import { useTask } from '@/composables/useTask'

const props = defineProps({
  editingTask: { type: Object, default: null }
})

const emit = defineEmits(['success'])

const visible = defineModel('visible', { default: false })
const memberStore = useMemberStore()
const members = computed(() => memberStore.members)
const { createTask, updateTask } = useTask()

const defaultForm = {
  title: '',
  assignee_id: null,
  priority: 'medium',
  status: 'in_progress',
  due_date: null,
  description: '',
  reminders: []
}

const form = ref({ ...defaultForm })

const onSubmit = async () => {
  if (!form.value.title) {
    ElMessage.warning('请输入任务标题')
    return
  }
  try {
    if (props.editingTask) {
      await updateTask(props.editingTask.id, form.value)
      ElMessage.success('任务更新成功')
    } else {
      await createTask(form.value)
      ElMessage.success('任务创建成功')
    }
    visible.value = false
    emit('success')
  } catch (e) {
    ElMessage.error(e.response?.data?.error?.message || '操作失败')
  }
}

const onClose = () => {
  form.value = { ...defaultForm }
}
</script>
