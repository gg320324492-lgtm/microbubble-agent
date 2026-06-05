<template>
  <el-dialog
    v-model="visible"
    title="创建会议"
    width="500px"
    @close="onClose"
  >
    <el-form :model="form" label-width="80px">
      <el-form-item label="标题" required>
        <el-input v-model="form.title" placeholder="请输入会议标题" />
      </el-form-item>
      <el-form-item label="开始时间" required>
        <el-date-picker
          v-model="form.start_time"
          type="datetime"
          placeholder="选择开始时间"
        />
      </el-form-item>
      <el-form-item label="议程">
        <div v-for="(item, idx) in form.agenda" :key="idx" class="agenda-item">
          <el-input v-model="form.agenda[idx]" placeholder="议程项目" />
          <el-button @click="form.agenda.splice(idx, 1)">删除</el-button>
        </div>
        <el-button @click="form.agenda.push('')">添加议程</el-button>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="onSubmit">创建</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useMeeting } from '@/composables/useMeeting'

const emit = defineEmits(['success'])
const visible = defineModel('visible', { default: false })
const { createMeeting } = useMeeting()

const defaultForm = {
  title: '',
  start_time: null,
  agenda: []
}

const form = ref({ ...defaultForm })

const onSubmit = async () => {
  if (!form.value.title) {
    ElMessage.warning('请输入会议标题')
    return
  }
  try {
    await createMeeting(form.value)
    ElMessage.success('会议创建成功')
    visible.value = false
    emit('success')
  } catch (e) {
    ElMessage.error(e.response?.data?.error?.message || '创建失败')
  }
}

const onClose = () => {
  form.value = { ...defaultForm }
}
</script>
