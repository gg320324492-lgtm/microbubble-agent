<template>
  <div class="dialog-overlay" @click.self="$emit('close')">
    <div class="dialog">
      <div class="dialog-header">
        <h3>创建会议</h3>
        <button class="btn btn-ghost" @click="$emit('close')">✕</button>
      </div>
      <div class="dialog-body">
        <div class="form-group">
          <label>会议标题</label>
          <input v-model="form.title" type="text" class="input" placeholder="请输入会议标题" />
        </div>
        <div class="form-group">
          <label>会议描述</label>
          <textarea v-model="form.description" class="input textarea" placeholder="请输入会议描述"></textarea>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>开始时间</label>
            <input v-model="form.start_time" type="datetime-local" class="input" />
          </div>
          <div class="form-group">
            <label>结束时间</label>
            <input v-model="form.end_time" type="datetime-local" class="input" />
          </div>
        </div>
        <div class="form-group">
          <label>会议地点</label>
          <input v-model="form.location" type="text" class="input" placeholder="请输入会议地点" />
        </div>
        <div class="form-group">
          <label>参与者</label>
          <select v-model="form.participants" class="input" multiple>
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
  start_time: '',
  end_time: '',
  location: '',
  participants: []
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
