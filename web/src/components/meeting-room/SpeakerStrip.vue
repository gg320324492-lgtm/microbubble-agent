<template>
  <div class="speaker-strip">
    <div v-for="p in speakers" :key="p.id" class="speaker-card" :class="{ active: p.id === activeSpeakerId }">
      <el-avatar :src="p.avatar" :size="50">
        {{ p.name?.charAt(0) }}
      </el-avatar>
      <div class="name">{{ p.name }}</div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  speakers: { type: Array, default: () => [] },
  activeSpeakerId: { type: [Number, String], default: null },
})
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
}
.speaker-card.active {
  opacity: 1;
  transform: scale(1.1);
}
.name {
  font-size: 12px;
}
</style>
