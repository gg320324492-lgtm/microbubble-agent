<template>
  <Teleport to="body">
    <Transition name="speaker-sheet">
      <div v-if="modelValue" class="speaker-sheet-root" @click.self="onClose">
        <div class="sheet-panel" :style="{ paddingBottom: 'calc(16px + var(--sab, 0px) + var(--tabbar-height, 56px))' }">
          <div class="sheet-handle" />
          <div class="sheet-header">
            <h3 class="sheet-title">🔍 说话记录</h3>
            <button
              type="button"
              class="close-btn"
              aria-label="关闭"
              title="关闭"
              @click="onClose"
            >✕</button>
          </div>

          <div v-if="!member" class="empty-tip">未选择成员</div>
          <div v-else class="member-info">
            <div class="member-avatar">{{ member.name?.charAt(0) }}</div>
            <div>
              <div class="member-name">{{ member.name }}</div>
              <div class="member-meta">
                录入 {{ member.voice_sample_count || 0 }} 次
              </div>
            </div>
          </div>

          <div v-if="loading" class="loading">
            <div class="loading-spinner" />
            <span>加载中...</span>
          </div>

          <div v-else-if="errorMessage" class="error-toast" @click="errorMessage = ''">
            ⚠️ {{ errorMessage }}
          </div>

          <div v-else-if="history.length === 0" class="empty-state">
            <div class="empty-icon">📭</div>
            <div class="empty-title">暂无说话记录</div>
            <div class="empty-hint">该成员暂未在任何会议中被声纹识别</div>
          </div>

          <div v-else class="history-list">
            <button
              v-for="(h, i) in history"
              :key="`${h.meeting_id}-${i}`"
              type="button"
              class="history-item"
              :aria-label="`在 ${h.meeting_title} 被识别，置信度 ${Math.round(h.confidence * 100)}%`"
              :title="`在 ${h.meeting_title} 被识别，置信度 ${Math.round(h.confidence * 100)}%`"
              @click="onItemClick(h)"
            >
              <div class="history-main">
                <div class="history-title">📅 {{ h.meeting_title || `会议 #${h.meeting_id}` }}</div>
                <div class="history-time">{{ formatDate(h.recorded_at) }}</div>
              </div>
              <div class="confidence-bar" :title="`置信度 ${Math.round(h.confidence * 100)}%`">
                <div
                  class="confidence-fill"
                  :style="{ width: `${Math.round(h.confidence * 100)}%`, background: confidenceColor(h.confidence) }"
                />
                <span class="confidence-text">{{ Math.round(h.confidence * 100) }}%</span>
              </div>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
/**
 * SpeakerSearchSheet.vue — 移动端"说话记录"底部弹层
 *
 * 数据源：GET /api/v1/voiceprint/{member_id}/history
 * 返回结构：[{ meeting_id, meeting_title, confidence, recorded_at }]
 *
 * 参考 VoiceprintEnrollFlow 的 Teleport 模式 (web/src/components/mobile/VoiceprintEnrollFlow.vue:434)
 */

import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import dayjs from 'dayjs'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  member: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue'])

const router = useRouter()

const history = ref([])
const loading = ref(false)
const errorMessage = ref('')

watch(
  () => [props.modelValue, props.member?.id],
  async ([visible, memberId]) => {
    if (visible && memberId) {
      await fetchHistory(memberId)
    } else {
      history.value = []
      errorMessage.value = ''
    }
  },
  { immediate: true }  // 首次 mount 触发（避免依赖外层 nextTick）
)

async function fetchHistory(memberId) {
  loading.value = true
  errorMessage.value = ''
  try {
    const res = await axios.get(`/api/v1/voiceprint/${memberId}/history`, {
      params: { limit: 50 },
    })
    history.value = Array.isArray(res.data) ? res.data : []
  } catch (e) {
    errorMessage.value = e.response?.data?.detail || e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function onClose() {
  emit('update:modelValue', false)
}

function onItemClick(h) {
  onClose()
  // 跳到会议详情
  if (h.meeting_id) {
    router.push(`/mobile/meetings/${h.meeting_id}`)
  }
}

function formatDate(t) {
  if (!t) return ''
  return dayjs(t).format('YYYY-MM-DD HH:mm')
}

function confidenceColor(c) {
  if (c >= 0.8) return 'var(--color-success, #67C23A)'
  if (c >= 0.6) return 'var(--color-warning, #E6A23C)'
  return 'var(--color-danger, #F56C6C)'
}
</script>

<style scoped>
.speaker-sheet-root {
  position: fixed;
  inset: 0;
  z-index: 4500;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: flex-end;
}
.sheet-panel {
  width: 100%;
  background: var(--color-bg-card);
  border-radius: var(--sheet-radius, 16px) var(--sheet-radius, 16px) 0 0;
  padding: 8px 20px;
  max-height: 70vh;
  overflow-y: auto;
}
[data-theme="dark"] .sheet-panel { background: var(--color-bg-card); }
.sheet-handle {
  width: var(--sheet-handle-w, 36px);
  height: var(--sheet-handle-h, 4px);
  background: var(--color-border);
  border-radius: 2px;
  margin: 0 auto 16px;
}
.sheet-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.sheet-title {
  margin: 0;
  font-size: 17px;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary);
}
.close-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: transparent;
  border: none;
  font-size: 18px;
  color: var(--color-text-regular);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.close-btn:active { background: var(--color-bg-hover); }

.empty-tip {
  text-align: center;
  padding: 20px;
  color: var(--color-text-secondary);
}

.member-info {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--color-bg-page);
  border-radius: var(--radius-md);
  margin-bottom: 16px;
}
.member-avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  color: white;
  font-size: 18px;
  font-weight: var(--font-weight-semibold, 600);
  display: flex;
  align-items: center;
  justify-content: center;
}
.member-name {
  font-size: 15px;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary);
}
.member-meta {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 4px;
}

.loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 30px 20px;
  color: var(--color-text-secondary);
  font-size: 13px;
}
.loading-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid var(--color-border);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.error-toast {
  background: var(--color-danger-bg);
  color: var(--color-danger, #F56C6C);
  padding: 12px 16px;
  border-radius: var(--radius-md);
  font-size: 13px;
  cursor: pointer;
}

.empty-state {
  text-align: center;
  padding: 40px 20px;
}
.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
}
.empty-title {
  font-size: 15px;
  color: var(--color-text-regular);
  margin-bottom: 4px;
}
.empty-hint {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.history-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--color-bg-page);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  text-align: left;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.history-item:active {
  background: var(--color-primary-bg);
  border-color: var(--color-primary);
}
.history-main {
  flex: 1;
  min-width: 0;
}
.history-title {
  font-size: 14px;
  font-weight: var(--font-weight-medium, 500);
  color: var(--color-text-primary);
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.history-time {
  font-size: 11px;
  color: var(--color-text-secondary);
}
.confidence-bar {
  position: relative;
  width: 80px;
  height: 22px;
  background: var(--color-border);
  border-radius: 11px;
  overflow: hidden;
  flex-shrink: 0;
}
.confidence-fill {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  border-radius: 11px;
  transition: width 0.3s ease;
}
.confidence-text {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  font-size: 11px;
  font-weight: var(--font-weight-semibold, 600);
  color: white;
  text-shadow: 0 1px 1px rgba(0, 0, 0, 0.2);
}

.speaker-sheet-enter-active, .speaker-sheet-leave-active {
  transition: opacity 0.25s ease;
}
.speaker-sheet-enter-active .sheet-panel, .speaker-sheet-leave-active .sheet-panel {
  transition: transform 0.3s cubic-bezier(0.32, 0.72, 0, 1);
}
.speaker-sheet-enter-from, .speaker-sheet-leave-to { opacity: 0; }
.speaker-sheet-enter-from .sheet-panel, .speaker-sheet-leave-to .sheet-panel {
  transform: translateY(100%);
}
</style>
