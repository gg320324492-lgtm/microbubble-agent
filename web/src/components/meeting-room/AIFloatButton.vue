<template>
  <div class="ai-float-btn" @click="toggle">
    <span v-if="!expanded">🤖</span>
    <div v-else class="ai-panel">
      <div class="ai-title">小气助手</div>
      <div class="ai-actions">
        <el-button size="small" @click.stop>📝 总结最近 30 秒</el-button>
        <el-button size="small" @click.stop>🌐 中英翻译</el-button>
        <el-button size="small" disabled>🤔 AI 提问（第二波）</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
const expanded = ref(false)
function toggle() {
  expanded.value = !expanded.value
}
</script>

<style scoped>
.ai-float-btn {
  position: fixed;
  right: 24px;
  bottom: 100px;
  z-index: 100;
}
.ai-float-btn > span {
  display: block;
  width: 50px;
  height: 50px;
  line-height: 50px;
  text-align: center;
  font-size: 24px;
  background: #ff7a5c;
  border-radius: 50%;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(255, 122, 92, 0.4);
}
.ai-panel {
  width: 200px;
  background: rgba(30, 30, 50, 0.95);
  border-radius: 8px;
  padding: 12px;
}
.ai-title {
  font-size: 14px;
  margin-bottom: 8px;
  color: white;
}
.ai-actions {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
</style>
