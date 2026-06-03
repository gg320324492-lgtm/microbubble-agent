<template>
  <div class="live-speaker-panel">
    <div class="main-avatar" :class="{ active: activeSpeakerId != null }">
      <el-avatar :src="activeSpeaker?.avatar" :size="120">
        {{ activeSpeaker?.name?.[0] || '?' }}
      </el-avatar>
      <div class="wave-bars">
        <div
          v-for="i in 16"
          :key="i"
          class="bar"
          :style="{ height: getBarHeight(i) + '%' }"
        ></div>
      </div>
      <div class="name">{{ activeSpeaker?.name || '等待发言...' }}</div>
      <div v-if="activeSpeakerId === 'unknown'" class="name unknown-hint">
        🔇 未识别发言人 — 请在成员管理页面录入声纹
      </div>
      <div class="confidence" v-if="activeSpeaker?.confidence">
        置信度: {{ Math.round(activeSpeaker.confidence * 100) }}%
      </div>
    </div>
    <div v-if="otherParticipants.length" class="others-row">
      <div
        v-for="p in otherParticipants"
        :key="p.id"
        class="mini-avatar"
        :class="{ active: p.id === activeSpeakerId }"
        :title="p.name"
      >
        <el-avatar :src="p.avatar" :size="40">{{ p.name?.[0] || '?' }}</el-avatar>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  participants: { type: Array, default: () => [] },
  activeSpeakerId: { type: [Number, String], default: null },
  audioLevels: { type: Object, default: () => ({}) },
})

const activeSpeaker = computed(() =>
  props.participants.find(p => p.id === props.activeSpeakerId) || null
)

const otherParticipants = computed(() =>
  props.participants.filter(p => p.id !== props.activeSpeakerId)
)

function getBarHeight(i) {
  // 2026-06-02 修复：activeSpeakerId 为 null 时读 'self' 槽位
  // 之前：activeSpeakerId=null 时 props.audioLevels[null] 永远 undefined → level=0，
  // 5 根声波条不跳动。MeetingRoom 写入 audioLevels 时用 'self' 兜底，
  // 这里读不到时也降级到 'self'，保证声音波动可见
  const id = props.activeSpeakerId
  const level = (id != null && props.audioLevels[id]) || props.audioLevels['self'] || 0
  const offset = (i % 3) * 0.15
  return Math.max(10, Math.min(100, (level + offset) * 100))
}
</script>

<style scoped>
.live-speaker-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px;
}
.main-avatar {
  text-align: center;
  transition: all 0.3s;
}
.main-avatar.active { transform: scale(1.05); }
.wave-bars {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 40px;
  width: 200px;
  margin: 12px auto;
  justify-content: center;
}
.bar {
  width: 8px;
  background: linear-gradient(180deg, #ff7a5c 0%, #ffb347 100%);
  border-radius: 4px;
  transition: height 0.1s ease-out;
}
.name { font-size: 16px; color: white; font-weight: 500; }
.unknown-hint { font-size: 12px; color: #ff7a5c; margin-top: 4px; font-weight: 400; }
.confidence { font-size: 12px; color: #aaa; margin-top: 4px; }
.others-row {
  display: flex;
  gap: 8px;
  margin-top: 20px;
  opacity: 0.7;
}
.mini-avatar.active { opacity: 1; transform: scale(1.1); }
</style>
