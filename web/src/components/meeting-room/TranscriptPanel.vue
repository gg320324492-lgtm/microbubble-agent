<template>
  <div ref="containerRef" class="transcript-panel" @scroll="onScroll">
    <transition-group name="entry">
      <div
        v-for="entry in entries"
        :key="entry.id"
        class="entry"
        :class="`status-${entry.status}`"
      >
        <div class="entry-header">
          <span class="speaker">{{ entry.speaker }}</span>
          <span v-if="entry.status === 'pending'" class="polish-badge pending">润色中...</span>
          <span v-else-if="entry.status === 'error'" class="polish-badge error">润色失败</span>
        </div>
        <div class="entry-text" :style="{ fontSize: fontSize.size, lineHeight: fontSize.lineHeight }">
          {{ entry.text }}
        </div>
        <div v-if="entry.keyPoints && entry.keyPoints.length > 0" class="key-points">
          <span
            v-for="(kp, i) in entry.keyPoints"
            :key="i"
            class="kp-badge"
            :class="`kp-${kp.kind}`"
          >
            {{ kp.kind === 'decision' ? '✨ 决策' : kp.kind === 'todo' ? '⏰ 待办' : '⚠️ 风险' }}
            {{ kp.text }}
          </span>
        </div>
      </div>
    </transition-group>
    <div v-if="newMessageCount > 0" class="new-msg-btn" @click="scrollToBottom()">
      ↓ {{ newMessageCount }} 条新消息
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useAutoScroll } from '@/composables/useAutoScroll'

const props = defineProps({
  entries: { type: Array, default: () => [] },
  fontSize: { type: Object, default: () => ({ size: '18px', lineHeight: 1.6 }) },
})
const emit = defineEmits(['user-scroll'])

const containerRef = ref(null)
const { onScroll, scrollToBottom, newMessageCount } = useAutoScroll(containerRef)
</script>

<style scoped>
.transcript-panel {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  scroll-behavior: smooth;
}
.entry {
  padding: 12px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
.entry-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.speaker {
  font-weight: 500;
  color: #ff7a5c;
}
.polish-badge {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
}
.polish-badge.pending {
  background: rgba(255, 255, 255, 0.1);
  color: #999;
}
.polish-badge.error {
  background: rgba(245, 108, 108, 0.2);
  color: #f56c6c;
}
.entry-text {
  color: white;
  transition: font-size 0.2s, line-height 0.2s;
}
.key-points {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.kp-badge {
  font-size: 12px;
  padding: 3px 8px;
  border-radius: 4px;
}
.kp-decision {
  background: rgba(230, 162, 60, 0.2);
  color: #e6a23c;
  border: 1px solid #e6a23c;
}
.kp-todo {
  background: rgba(64, 158, 255, 0.2);
  color: #409eff;
  border: 1px solid #409eff;
}
.kp-risk {
  background: rgba(245, 108, 108, 0.2);
  color: #f56c6c;
  border: 1px solid #f56c6c;
}
.new-msg-btn {
  position: sticky;
  bottom: 20px;
  margin: 0 auto;
  width: fit-content;
  padding: 8px 16px;
  background: #ff7a5c;
  color: white;
  border-radius: 16px;
  cursor: pointer;
}
.entry-enter-active {
  transition: all 0.3s;
}
.entry-enter-from {
  opacity: 0;
  transform: translateY(20px);
}
</style>
