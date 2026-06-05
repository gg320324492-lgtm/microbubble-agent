<template>
  <div class="dialog-overlay" @click.self="$emit('close')">
    <div class="dialog">
      <div class="dialog-header">
        <h3>创建任务</h3>
        <button class="btn btn-ghost" @click="$emit('close')">✕</button>
      </div>
      <div class="dialog-body">
        <div class="form-group">
          <label>任务标题</label>
          <input v-model="form.title" type="text" class="input" placeholder="请输入任务标题" />
        </div>
        <div class="form-group">
          <label>任务描述</label>
          <textarea v-model="form.description" class="input textarea" placeholder="请输入任务描述"></textarea>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>优先级</label>
            <select v-model="form.priority" class="input">
              <option value="high">紧急</option>
              <option value="medium">中等</option>
              <option value="low">普通</option>
            </select>
          </div>
          <div class="form-group">
            <label>截止日期</label>
            <input v-model="form.due_date" type="date" class="input" />
          </div>
        </div>
        <div class="form-group">
          <label>负责人</label>
          <select v-model="form.assignee_id" class="input">
            <option value="">请选择负责人</option>
            <option v-for="member in members" :key="member.id" :value="member.id">
              {{ member.name }}
            </option>
          </select>
        </div>
      </div>
      <div class="dialog-footer">
        <button class="btn btn-secondary" @click="$emit('close')">取消</button>
        <button class="btn btn-primary" @click="handleSubmit">创建</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const emit = defineEmits(['close', 'submit'])

const form = ref({
  title: '',
  description: '',
  priority: 'medium',
  due_date: '',
  assignee_id: ''
})

const members = ref([
  { id: 1, name: '张三' },
  { id: 2, name: '李四' },
  { id: 3, name: '王五' }
])

const handleSubmit = () => {
  emit('submit', form.value)
}
</script>

<style scoped>
.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.dialog {
  background: white;
  border-radius: var(--radius-lg);
  width: 100%;
  max-width: 500px;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid var(--color-border);
}

.dialog-header h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.dialog-body {
  padding: 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-group label {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary);
}

.textarea {
  min-height: 100px;
  resize: vertical;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid var(--color-border);
}
</style>
