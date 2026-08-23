<template>
  <div class="assistant-mock">
    <div class="left-panel">
      <h3>任务历史</h3>
      <div class="task-item" v-for="task in tasks" :key="task.id" :class="{ active: task.active }">
        {{ task.name }}
      </div>
    </div>
    <div class="center-panel">
      <h3>AI推理工作台</h3>
      <div class="message" v-for="msg in messages" :key="msg.id" :class="msg.role">
        <div class="message-role">{{ msg.role === 'user' ? '用户' : 'AI' }}</div>
        <div class="message-content">{{ msg.content }}</div>
        <div class="tool-call" v-if="msg.toolCall">
          [工具调用: {{ msg.toolCall.name }}]
          <div class="tool-result">结果: {{ msg.toolCall.result }}</div>
        </div>
      </div>
      <div class="chat-input">
        <input type="text" placeholder="输入研究问题..." />
      </div>
    </div>
    <div class="right-panel">
      <h3>引用</h3>
      <div class="citation" v-for="c in citations" :key="c.id">
        [{{ c.id }}] {{ c.authors }} ({{ c.year }})
      </div>
      <h3>证据</h3>
      <div class="evidence" v-for="e in evidence" :key="e.label">
        {{ e.label }}: {{ e.value }}
      </div>
      <h3>置信度</h3>
      <div class="confidence-bar">
        <div class="confidence-fill" :style="{ width: confidence + '%' }"></div>
      </div>
      <div class="confidence-value">{{ confidence }}%</div>
    </div>
  </div>
</template>

<script setup lang="ts">
const tasks = [
  { id: 1, name: '分析降解动力学', active: true },
  { id: 2, name: '文献综述', active: false }
]

const messages = [
  { id: 1, role: 'user', content: '分析O3降解动力学', toolCall: null },
  { id: 2, role: 'assistant', content: '根据实验数据分析...', toolCall: { name: 'fitModels', result: 'first-order, R²=0.98' } }
]

const citations = [
  { id: 1, authors: 'Zhang et al.', year: 2024 },
  { id: 2, authors: 'Li et al.', year: 2023 }
]

const evidence = [
  { label: 'kLa', value: '0.45 min⁻¹' },
  { label: 'R²', value: '0.98' }
]

const confidence = 85
</script>

<style scoped>
.assistant-mock { display: flex; height: 100%; }
.left-panel { width: 200px; border-right: 1px solid #e2e8f0; padding: 16px; }
.center-panel { flex: 1; padding: 16px; display: flex; flex-direction: column; }
.right-panel { width: 240px; border-left: 1px solid #e2e8f0; padding: 16px; }
.task-item { padding: 8px; border-radius: 4px; margin-bottom: 4px; font-size: 13px; cursor: pointer; }
.task-item.active { background: #eff6ff; color: #2563eb; }
.message { margin-bottom: 12px; padding: 8px; border-radius: 6px; }
.message.user { background: #f1f5f9; }
.message.assistant { background: #f0f9ff; border: 1px solid #bae6fd; }
.message-role { font-size: 11px; font-weight: 600; color: #64748b; margin-bottom: 2px; }
.message-content { font-size: 13px; }
.tool-call { font-size: 12px; color: #0ea5e9; margin-top: 4px; font-family: monospace; }
.tool-result { font-size: 12px; color: #64748b; }
.chat-input { margin-top: auto; }
.chat-input input { width: 100%; padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 13px; }
.citation { font-size: 12px; margin-bottom: 4px; color: #92400e; background: #fef3c7; padding: 4px 8px; border-radius: 4px; }
.evidence { font-size: 12px; margin-bottom: 4px; }
.confidence-bar { height: 6px; background: #e2e8f0; border-radius: 3px; margin: 4px 0; }
.confidence-fill { height: 100%; background: #10b981; border-radius: 3px; }
.confidence-value { font-size: 12px; font-weight: 600; color: #10b981; }
h3 { font-size: 13px; font-weight: 600; margin-bottom: 8px; color: #1e293b; }
</style>
