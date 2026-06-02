<template>
  <div class="agenda-panel">
    <h4>会议议程</h4>
    <el-progress v-if="items.length" :percentage="progress" />
    <div v-for="(item, idx) in items" :key="idx" class="agenda-item">
      <el-checkbox
        :model-value="item.done"
        :name="`agenda-item-${idx}`"
        @update:model-value="(v) => toggleDone(idx, v)"
      />
      <span :class="{ done: item.done }" class="agenda-text">{{ item.text }}</span>
      <el-tag v-if="item.done" type="success" size="small">已完成</el-tag>
      <el-tag v-else-if="idx === currentIdx" type="warning" size="small">进行中</el-tag>
    </div>
    <el-empty v-if="!items.length" description="暂无议程" :image-size="60" />
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import axios from 'axios'

const props = defineProps({
  meetingId: { type: Number, required: true },
  agenda: { type: Array, default: () => [] },
})
const emit = defineEmits(['update'])

const items = ref([...props.agenda.map(a => typeof a === 'string' ? { text: a, done: false } : a)])

watch(() => props.agenda, (val) => {
  items.value = val.map(a => typeof a === 'string' ? { text: a, done: false } : a)
}, { deep: true })

const currentIdx = computed(() => {
  const firstUndone = items.value.findIndex(i => !i.done)
  return firstUndone === -1 ? items.value.length - 1 : firstUndone
})

const progress = computed(() => {
  if (items.value.length === 0) return 0
  const done = items.value.filter(i => i.done).length
  return Math.round(done / items.value.length * 100)
})

async function toggleDone(idx, value) {
  items.value[idx].done = value
  emit('update', [...items.value])
  try {
    await axios.patch(`/api/v1/meetings/${props.meetingId}/agenda`, items.value)
  } catch (e) {
    console.error('agenda 同步失败', e)
  }
}
</script>

<style scoped>
.agenda-panel { padding: 12px; }
.agenda-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
}
.agenda-text { flex: 1; font-size: 14px; }
.agenda-text.done { text-decoration: line-through; color: #999; }
</style>
