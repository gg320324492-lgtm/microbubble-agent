<template>
  <div class="dialog-overlay" @click.self="$emit('close')">
    <div class="dialog">
      <div class="dialog-header">
        <h3>上传文档</h3>
        <button class="btn btn-ghost" @click="$emit('close')">✕</button>
      </div>
      <div class="dialog-body">
        <div class="upload-area">
          <div class="upload-icon">📁</div>
          <p>拖拽文件到此处或点击上传</p>
          <input type="file" class="file-input" @change="handleFileChange" />
        </div>
        <div class="form-group">
          <label>文档标题</label>
          <input v-model="form.title" type="text" class="input" placeholder="请输入文档标题" />
        </div>
        <div class="form-group">
          <label>文档描述</label>
          <textarea v-model="form.description" class="input textarea" placeholder="请输入文档描述"></textarea>
        </div>
        <div class="form-group">
          <label>分类</label>
          <select v-model="form.category" class="input">
            <option value="">请选择分类</option>
            <option value="基础知识">基础知识</option>
            <option value="操作规范">操作规范</option>
            <option value="数据分析">数据分析</option>
          </select>
        </div>
        <div class="form-group">
          <label>标签</label>
          <input v-model="form.tags" type="text" class="input" placeholder="多个标签用逗号分隔" />
        </div>
      </div>
      <div class="dialog-footer">
        <button class="btn btn-secondary" @click="$emit('close')">取消</button>
        <button class="btn btn-primary" @click="handleSubmit">上传</button>
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
  category: '',
  tags: ''
})

const handleFileChange = (e) => {
  const file = e.target.files[0]
  if (file) {
    form.value.title = file.name
  }
}

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

.upload-area {
  border: 2px dashed var(--color-border);
  border-radius: var(--radius-lg);
  padding: 40px;
  text-align: center;
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  position: relative;
}

.upload-area:hover {
  border-color: var(--color-primary);
  background: var(--color-bg-hover);
}

.upload-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.upload-area p {
  font-size: 14px;
  color: var(--color-text-secondary);
}

.file-input {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  opacity: 0;
  cursor: pointer;
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

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid var(--color-border);
}
</style>
