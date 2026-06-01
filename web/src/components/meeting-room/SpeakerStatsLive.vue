<template>
  <div class="speaker-stats-live">
    <h4>实时发言统计</h4>
    <div v-for="s in stats" :key="s.name" class="stat-row">
      <el-avatar :src="s.avatar" :size="32">{{ s.name?.[0] || '?' }}</el-avatar>
      <span class="name">{{ s.name }}</span>
      <span class="turn-count">{{ s.turn_count || 0 }} 句</span>
      <el-progress :percentage="Math.round((s.speaking_ratio || 0) * 100)" :stroke-width="6" />
    </div>
    <el-empty v-if="stats.length === 0" description="暂无数据" :image-size="60" />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import axios from 'axios'

const props = defineProps({ meetingId: { type: Number, required: true } })

const stats = ref([])
let timer = null

async function loadStats() {
  try {
    const resp = await axios.get(`/api/v1/meetings/${props.meetingId}/analytics`)
    if (resp.data?.speaker_stats) {
      stats.value = resp.data.speaker_stats
    }
  } catch (e) {
    // 静默失败
  }
}

onMounted(() => {
  loadStats()
  timer = setInterval(loadStats, 5000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.speaker-stats-live { padding: 12px; }
.stat-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
}
.name { flex: 1; font-size: 14px; }
.turn-count { color: #999; font-size: 12px; min-width: 40px; text-align: right; }
</style>
