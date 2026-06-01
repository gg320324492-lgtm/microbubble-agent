<template>
  <div class="speaker-strip">
    <div
      v-for="p in speakers"
      :key="p.id"
      class="speaker-card"
      :class="{ active: p.id === activeSpeakerId }"
    >
      <el-avatar :src="p.avatar" :size="50">
        {{ p.name?.charAt(0) }}
      </el-avatar>
      <div class="name">{{ p.name }}</div>
      <div class="wave-bar">
        <div
          v-for="i in 5"
          :key="i"
          class="bar"
          :style="{ height: getBarHeight(p.id, i) + '%' }"
        ></div>
      </div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  speakers: { type: Array, default: () => [] },
  activeSpeakerId: { type: [Number, String], default: null },
  audioLevels: { type: Object, default: () => ({}) },  // { memberId: 0-1 }
})

function getBarHeight(memberId, barIdx) {
  const level = props.audioLevels[memberId] || 0
  // 5 根条错落跳动（奇偶不同步）
  const offset = barIdx % 2 === 0 ? 0 : 0.3
  return Math.max(10, Math.min(100, (level + offset) * 100))
}
</script>

<style scoped>
.speaker-strip {
  display: flex;
  gap: 16px;
  padding: 16px 24px;
  overflow-x: auto;
}
.speaker-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  opacity: 0.5;
  transition: opacity 0.3s, transform 0.3s;
  min-width: 60px;
}
.speaker-card.active {
  opacity: 1;
  transform: scale(1.1);
}
.name {
  font-size: 12px;
}
.wave-bar {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 24px;
  width: 30px;
  justify-content: center;
}
.bar {
  width: 4px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 2px;
  transition: height 0.1s ease-out;
}
.speaker-card.active .bar {
  background: linear-gradient(180deg, #ff7a5c 0%, #ffb347 100%);
  animation: wave-pulse 0.5s ease infinite alternate;
}
.speaker-card.active .bar:nth-child(1) { animation-delay: 0s; }
.speaker-card.active .bar:nth-child(2) { animation-delay: 0.1s; }
.speaker-card.active .bar:nth-child(3) { animation-delay: 0.2s; }
.speaker-card.active .bar:nth-child(4) { animation-delay: 0.15s; }
.speaker-card.active .bar:nth-child(5) { animation-delay: 0.05s; }
@keyframes wave-pulse {
  from { transform: scaleY(0.6); }
  to { transform: scaleY(1.4); }
}
</style>
