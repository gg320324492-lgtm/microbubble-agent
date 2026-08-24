<script setup lang="ts">
import { computed } from 'vue'
import type { WorkspaceActivity } from '../../../../shared/workspace/research-workspace-schema'

const props = withDefaults(defineProps<{ activities: WorkspaceActivity[] }>(), {
  activities: () => []
})

const sorted = computed(() => [...props.activities].sort((a, b) => b.timestamp - a.timestamp))

const kindColors: Record<string, string> = {
  agent: '#FF7A5C',
  experiment: '#3b82f6',
  manuscript: '#8b5cf6',
  device: '#10b981',
  twin: '#f59e0b',
  knowledge: '#ec4899',
  system: '#94a3b8'
}

const kindLabel: Record<string, string> = {
  agent: '智能体',
  experiment: '实验',
  manuscript: '论文',
  device: '设备',
  twin: '孪生',
  knowledge: '知识',
  system: '系统'
}

function color(kind: string): string { return kindColors[kind] ?? '#94a3b8' }
function label(kind: string): string { return kindLabel[kind] ?? kind }

function format(ts: number): string {
  return new Date(ts).toLocaleTimeString('zh-CN')
}
</script>

<template>
  <div class="activity-timeline">
    <div class="activity-timeline__title">活动时间线</div>
    <div v-if="sorted.length === 0" class="activity-timeline__empty">暂无活动</div>
    <div v-for="a in sorted" :key="a.id" class="activity-timeline__entry">
      <div class="activity-timeline__dot" :style="{ background: color(a.kind) }"></div>
      <div class="activity-timeline__body">
        <div class="activity-timeline__head">
          <span class="activity-timeline__kind" :style="{ color: color(a.kind) }">{{ label(a.kind) }}</span>
          <span class="activity-timeline__time">{{ format(a.timestamp) }}</span>
        </div>
        <div class="activity-timeline__event">{{ a.title }}</div>
        <div class="activity-timeline__desc">{{ a.description }}</div>
        <div class="activity-timeline__actor">{{ a.actor }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.activity-timeline {
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 12px;
  padding: 16px;
}
.activity-timeline__title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 12px;
}
.activity-timeline__empty {
  text-align: center;
  color: #94a3b8;
  padding: 24px;
}
.activity-timeline__entry {
  display: flex;
  gap: 12px;
  padding: 8px 0;
  border-left: 2px solid rgba(15, 23, 42, 0.06);
  margin-left: 6px;
  padding-left: 12px;
  position: relative;
}
.activity-timeline__dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  position: absolute;
  left: -6px;
  top: 14px;
}
.activity-timeline__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.activity-timeline__kind {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
}
.activity-timeline__time {
  font-size: 11px;
  color: #94a3b8;
}
.activity-timeline__event {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}
.activity-timeline__desc {
  font-size: 12px;
  color: #475569;
  margin-top: 2px;
}
.activity-timeline__actor {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 4px;
}
</style>