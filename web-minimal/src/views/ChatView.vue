<template>
  <div class="chat-view">
    <header class="header">
      <div class="header-left">
        <h2>智能对话</h2>
        <p>与 AI 助手对话，获取帮助</p>
      </div>
    </header>

    <div class="chat-container">
      <div class="chat-messages">
        <div v-for="(msg, index) in messages" :key="index" class="message" :class="msg.role">
          <div class="message-avatar">
            <span v-if="msg.role === 'user'">{{ userInitial }}</span>
            <span v-else>M</span>
          </div>
          <div class="message-content">
            <div class="message-text">{{ msg.content }}</div>
            <div class="message-time">{{ msg.time }}</div>
          </div>
        </div>
      </div>

      <div class="chat-input">
        <input
          v-model="inputMessage"
          type="text"
          placeholder="输入消息..."
          class="input"
          @keyup.enter="sendMessage"
        />
        <button class="btn btn-primary" @click="sendMessage">发送</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const userInitial = computed(() => userStore.userInitial)
const inputMessage = ref('')
const messages = ref([
  {
    role: 'assistant',
    content: '你好！我是 MicroBubble Agent，有什么可以帮助你的吗？',
    time: '14:00'
  }
])

const sendMessage = () => {
  if (!inputMessage.value.trim()) return

  messages.value.push({
    role: 'user',
    content: inputMessage.value,
    time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  })

  const userMsg = inputMessage.value
  inputMessage.value = ''

  // 模拟 AI 回复
  setTimeout(() => {
    messages.value.push({
      role: 'assistant',
      content: `收到你的消息："${userMsg}"。我正在处理中...`,
      time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    })
  }, 1000)
}
</script>

<style scoped>
.chat-view {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 120px);
}

.header {
  margin-bottom: 24px;
}

.header-left h2 {
  font-size: 24px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.header-left p {
  font-size: 14px;
  color: var(--color-text-tertiary);
  margin-top: 4px;
}

.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: white;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border);
  overflow: hidden;
}

.chat-messages {
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
  width: 40px;
  height: 40px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
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

.message-time {
  font-size: 12px;
  color: var(--color-text-tertiary);
  margin-top: 4px;
}

.message.user .message-time {
  color: rgba(255, 255, 255, 0.7);
}

.chat-input {
  display: flex;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid var(--color-border);
}

.chat-input .input {
  flex: 1;
}
</style>
