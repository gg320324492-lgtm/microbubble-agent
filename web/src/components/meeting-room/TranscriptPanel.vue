<template>
  <div class="transcript-panel-wrapper">
    <!-- 视图模式 Tab（2026-06-02 三级润色：实时原文 vs AI 润色版） -->
    <div class="view-tabs">
      <el-radio-group v-model="viewModeProxy" size="small">
        <el-radio-button value="raw">
          实时原文
          <span v-if="entries.length" class="entry-count">({{ entries.length }})</span>
        </el-radio-button>
        <el-radio-button value="polished" :disabled="!hasAnyPolished">
          AI 润色版
          <span v-if="polishedCount" class="entry-count">({{ polishedCount }})</span>
        </el-radio-button>
      </el-radio-group>
      <div class="view-hint">
        <span v-if="viewModeProxy === 'raw' && hasAnyPolished" class="hint-text hint-highlight">
          ✨ AI 润色版已就绪，点击查看
        </span>
      </div>
    </div>

    <div ref="containerRef" class="transcript-panel" @scroll="onScroll">
      <transition-group name="entry">
        <div
          v-for="entry in displayEntries"
          :key="entry.id"
          class="entry"
          :class="[`status-${entry.status}`, { 'entry-removed': entry.removed }]"
        >
          <div class="entry-header">
            <span class="speaker">{{ entry.speaker }}</span>
            <!-- 状态徽章：raw / batch_polished / full_polished / error -->
            <span v-if="entry.status === 'raw'" class="polish-badge raw">实时</span>
            <span v-else-if="entry.status === 'pending'" class="polish-badge pending">润色中...</span>
            <span v-else-if="entry.status === 'batch_polished'" class="polish-badge batch">AI 润色</span>
            <span v-else-if="entry.status === 'full_polished'" class="polish-badge full">精润完成</span>
            <span v-else-if="entry.status === 'polished'" class="polish-badge polished">已润色</span>
            <span v-else-if="entry.status === 'error'" class="polish-badge error">润色失败</span>
            <!-- L3 标记：被识别为 ASR 幻觉 -->
            <span v-if="entry.removed" class="polish-badge removed">已过滤幻觉</span>
            <span v-else-if="entry.polishFailed" class="polish-badge failed">精润失败</span>
          </div>
          <div class="entry-text" :style="{ fontSize: fontSize.size, lineHeight: fontSize.lineHeight }">
            {{ entry.displayText }}
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
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useAutoScroll } from '@/composables/useAutoScroll'

const props = defineProps({
  entries: { type: Array, default: () => [] },
  displayEntries: { type: Array, default: () => [] },  // 2026-06-02 三级润色
  hasAnyPolished: { type: Boolean, default: false },
  viewMode: { type: String, default: 'raw' },         // 'raw' | 'polished'
  fontSize: { type: Object, default: () => ({ size: '18px', lineHeight: 1.6 }) },
})
const emit = defineEmits(['user-scroll', 'update:viewMode'])

const containerRef = ref(null)
const { onScroll, scrollToBottom, newMessageCount } = useAutoScroll(containerRef)

// v-model:viewMode 双向绑定
const viewModeProxy = computed({
  get: () => props.viewMode,
  set: (v) => emit('update:viewMode', v),
})

// 已精润的 entry 数（用于 Tab 角标）
const polishedCount = computed(() => {
  return props.entries.filter(
    (e) => e.fullPolishedText || e.polishedText || e.status === 'batch_polished' || e.status === 'full_polished'
  ).length
})
</script>

<style scoped>
.transcript-panel-wrapper {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.view-tabs {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background: rgba(0, 0, 0, 0.2);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
.entry-count {
  font-size: 11px;
  color: #999;
  margin-left: 4px;
}
.view-hint { flex: 1; }
.hint-text {
  font-size: 11px;
  color: #999;
  font-style: italic;
}
.hint-highlight {
  color: #ff7a5c;
  font-style: normal;
  font-weight: 500;
  animation: hint-pulse 2s ease-in-out infinite;
}
@keyframes hint-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}
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
.entry-removed .entry-text {
  text-decoration: line-through;
  opacity: 0.5;
  font-style: italic;
}
.entry-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  flex-wrap: wrap;
}
.speaker {
  font-weight: 500;
  color: #ff7a5c;
}
.polish-badge {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  white-space: nowrap;
}
.polish-badge.raw {
  background: rgba(255, 255, 255, 0.1);
  color: #999;
}
.polish-badge.pending {
  background: rgba(255, 255, 255, 0.1);
  color: #999;
}
.polish-badge.polished,
.polish-badge.batch {
  background: rgba(64, 158, 255, 0.2);
  color: #409eff;
}
.polish-badge.full {
  background: rgba(103, 194, 58, 0.2);
  color: #67c23a;
}
.polish-badge.error,
.polish-badge.failed {
  background: rgba(245, 108, 108, 0.2);
  color: #f56c6c;
}
.polish-badge.removed {
  background: rgba(150, 150, 150, 0.3);
  color: #ccc;
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
