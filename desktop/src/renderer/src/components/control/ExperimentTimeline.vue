<script setup lang="ts">
import { computed } from 'vue'
import type { ExperimentTimelineEntry } from '../../../../shared/control/experiment-control-schema'

const props = withDefaults(defineProps<{ entries: ExperimentTimelineEntry[] }>(), {
  entries: () => []
})

const sorted = computed(() => [...props.entries].sort((a, b) => b.timestamp - a.timestamp))

function format(ts: number): string {
  return new Date(ts).toLocaleTimeString('zh-CN')
}
</script>

<template>
  <div class="timeline">
    <div class="timeline__title">实验时间线</div>
    <div class="timeline__list">
      <div v-for="entry in sorted" :key="entry.id" class="timeline__entry">
        <div class="timeline__dot"></div>
        <div class="timeline__body">
          <div class="timeline__event">{{ entry.event }}</div>
          <div class="timeline__desc">{{ entry.description }}</div>
          <div class="timeline__time">{{ format(entry.timestamp) }}</div>
        </div>
      </div>
      <div v-if="sorted.length === 0" class="timeline__empty">暂无事件</div>
    </div>
  </div>
</template>

<style scoped>
.timeline {
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 12px;
  padding: 16px;
}
.timeline__title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 12px;
}
.timeline__list {
  position: relative;
}
.timeline__entry {
  display: flex;
  gap: 12px;
  padding: 8px 0;
  border-left: 2px solid rgba(255, 122, 92, 0.2);
  margin-left: 6px;
  padding-left: 12px;
  position: relative;
}
.timeline__dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #FF7A5C;
  position: absolute;
  left: -6px;
  top: 14px;
}
.timeline__event {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}
.timeline__desc {
  font-size: 12px;
  color: #475569;
  margin-top: 2px;
}
.timeline__time {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 4px;
}
.timeline__empty {
  text-align: center;
  color: #94a3b8;
  padding: 24px;
}
</style>