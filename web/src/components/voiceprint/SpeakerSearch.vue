<template>
  <div class="speaker-search">
    <el-input
      v-model="searchKeyword"
      placeholder="搜索该成员说过的内容..."
      clearable
    />
    <div v-if="results.length > 0" class="results">
      <div
        v-for="(r, i) in results"
        :key="i"
        class="result-item"
        @click="$emit('jump', r.meeting_id)"
      >
        <div class="result-meta">
          <span class="meeting-title">{{ r.meeting_title }}</span>
          <span class="confidence">{{ Math.round(r.confidence * 100) }}%</span>
        </div>
        <div class="result-text">{{ r.text }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  memberId: { type: Number, required: true },
})
defineEmits(['jump'])

const searchKeyword = ref('')
const results = ref([])

watch(() => props.memberId, async (newId) => {
  if (newId) {
    await loadAll()
  }
}, { immediate: true })

async function loadAll() {
  const apiUrl = import.meta.env.VITE_API_BASE || '/api/v1'
  const resp = await fetch(`${apiUrl}/voiceprint/search?member_id=${props.memberId}&limit=20`, {
    headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` },
  })
  if (resp.ok) {
    results.value = await resp.json()
  }
}
</script>

<style scoped>
.speaker-search { padding: 12px; }
.results { margin-top: 12px; max-height: 300px; overflow-y: auto; }
.result-item {
  padding: 8px;
  border-bottom: 1px solid #eee;
  cursor: pointer;
}
.result-item:hover { background: #f9f9f9; }
.result-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  margin-bottom: 4px;
}
.meeting-title { color: #ff7a5c; font-weight: 500; }
.confidence { color: #999; }
.result-text { font-size: 13px; color: #333; }
</style>
