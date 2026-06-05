<template>
  <div class="dialog-overlay" @click.self="$emit('close')">
    <div class="dialog">
      <div class="dialog-header">
        <h3>知识问答</h3>
        <button class="btn btn-ghost" @click="$emit('close')">✕</button>
      </div>
      <div class="dialog-body">
        <div class="qa-messages">
          <div v-for="(msg, index) in messages" :key="index" class="message" :class="msg.role">
            <div class="message-avatar">
              <span v-if="msg.role === 'user'">你</span>
              <span v-else>M</span>
            </div>
            <div class="message-content">
              <div class="message-text">{{ msg.content }}</div>
            </div>
          </div>
        </div>
        <div class="qa-input">
          <input
            v-model="question"
            type="text"
            placeholder="输入你的问题..."
            class="input"
            @keyup.enter="handleAsk"
          />
          <button class="btn btn-primary" @click="handleAsk">提问</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const emit = defineEmits(['close'])

const question = ref('')
const messages = ref([
  {
    role: 'assistant',
    content: '你好！我是知识库助手，有什么可以帮助你的吗？'
  }
])

const handleAsk = () => {
  if (!question.value.trim()) return

  messages.value.push({
    role: 'user',
    content: question.value
  })

  const userQuestion = question.value
  question.value = ''

  // 模拟回答
  setTimeout(() => {
    messages.value.push({
      role: 'assistant',
      content: `关于"${userQuestion}"，我正在查询知识库...`
    })
  }, 500)
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
  max-width: 600px;
  max-height: 80vh;
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
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.qa-messages {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.message {
  display: flex;
  gap: 12px;
  max-width: 80%;
}

.message.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 14px;
  flex-shrink: 0;
}

.message.assistant .message-avatar {
  background: var(--color-primary);
  color: white;
}

.message.user .message-avatar {
  background: var(--color-accent);
  color: white;
}

.message-content {
  background: var(--color-bg-page);
  padding: 12px 16px;
  border-radius: var(--radius-lg);
}

.message.user .message-content {
  background: var(--color-primary);
  color: white;
}

.message-text {
  font-size: 14px;
  line-height: 1.6;
}

.qa-input {
  display: flex;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid var(--color-border);
}

.qa-input .input {
  flex: 1;
}
</style>
