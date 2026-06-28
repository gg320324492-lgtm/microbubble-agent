<!--
  MeetingMinutesDialog.vue — 会议纪要查看对话框
  v77 P2.6-F.2: 从 MeetingView.vue 拆分（Step 2）

  父组件: MeetingView.vue
  Props: modelValue (v-model:show) / meeting (Object|null) / isMobile (Bool)
  Emits: update:modelValue

  复用模式（v77 P2.6-E.3 KnowledgeCreateDialog）:
  - v-model bridge: computed { get, set } 桥接 modelValue prop
  - dark 块必须非 scoped <style>（v60-v67 教训第 7 次强化）
-->
<template>
  <el-dialog
    v-model="visible"
    title="会议纪要"
    :width="isMobile ? '90vw' : '600px'"
    top="5vh"
  >
    <div v-if="meeting" class="minutes-content">
      <h3>{{ meeting.title }}</h3>
      <div class="minutes-time">{{ formatDate(meeting.start_time) }}</div>

      <div v-if="meeting.summary" class="minutes-section">
        <h4>会议摘要</h4>
        <p>{{ meeting.summary }}</p>
      </div>

      <div v-if="meeting.key_points?.length" class="minutes-section">
        <h4>讨论要点</h4>
        <ul>
          <li v-for="(point, i) in meeting.key_points" :key="i">{{ point }}</li>
        </ul>
      </div>

      <div v-if="meeting.decisions?.length" class="minutes-section">
        <h4>决议事项</h4>
        <ul>
          <li v-for="(decision, i) in meeting.decisions" :key="i">{{ decision }}</li>
        </ul>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { computed } from 'vue'
import { formatDateTime } from '@/utils/format'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  meeting: { type: Object, default: null },
  isMobile: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

// v-model bridge（KnowledgeCreateDialog line 96-100 模式）
const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const formatDate = (date) => formatDateTime(date)
</script>

<style scoped>
.minutes-content h3 { margin-bottom: var(--space-2); }
.minutes-time { color: var(--color-text-secondary); margin-bottom: var(--space-5); }
.minutes-section { margin-bottom: var(--space-5); }
.minutes-section h4 {
  margin-bottom: var(--space-2);
  color: var(--color-text-primary);
  font-weight: var(--font-weight-semibold);
}
.minutes-section ul { padding-left: var(--space-5); }
.minutes-section li {
  margin-bottom: var(--space-2);
  line-height: 1.5;
  color: var(--color-text-regular);
}
</style>

<!-- v60-v67 教训第 7 次强化: dark mode 必须非 scoped -->
<style>
[data-theme="dark"] .minutes-content h3 { color: var(--color-text-primary); }
[data-theme="dark"] .minutes-section li { color: var(--color-text-regular); }
</style>