<script setup lang="ts">
import { computed } from 'vue'
import type { ResearchProgress } from '../../../../shared/workspace/research-workspace-schema'

const props = withDefaults(defineProps<{ progress: ResearchProgress | null }>(), {
  progress: null
})

const percent = computed(() => props.progress?.percent ?? 0)
const tasksPct = computed(() => {
  if (!props.progress || props.progress.totalTasks === 0) return 0
  return Math.round((props.progress.completedTasks / props.progress.totalTasks) * 100)
})
const experimentsPct = computed(() => {
  if (!props.progress || props.progress.totalExperiments === 0) return 0
  return Math.round((props.progress.completedExperiments / props.progress.totalExperiments) * 100)
})
const manuscriptsPct = computed(() => {
  if (!props.progress || props.progress.totalManuscripts === 0) return 0
  return Math.round((props.progress.publishedManuscripts / props.progress.totalManuscripts) * 100)
})
const knowledgePct = computed(() => {
  if (!props.progress || props.progress.totalKnowledge === 0) return 0
  return Math.round((props.progress.indexedKnowledge / props.progress.totalKnowledge) * 100)
})
</script>

<template>
  <div class="progress-card">
    <div class="progress-card__head">
      <span class="progress-card__title">研究进度</span>
      <span class="progress-card__overall">{{ percent }}%</span>
    </div>
    <div class="progress-card__bar">
      <div class="progress-card__bar-fill" :style="{ width: percent + '%' }"></div>
    </div>
    <div class="progress-card__grid">
      <div class="progress-card__item">
        <span class="progress-card__label">任务</span>
        <span class="progress-card__val">{{ progress?.completedTasks ?? 0 }} / {{ progress?.totalTasks ?? 0 }}</span>
        <span class="progress-card__pct">{{ tasksPct }}%</span>
      </div>
      <div class="progress-card__item">
        <span class="progress-card__label">实验</span>
        <span class="progress-card__val">{{ progress?.completedExperiments ?? 0 }} / {{ progress?.totalExperiments ?? 0 }}</span>
        <span class="progress-card__pct">{{ experimentsPct }}%</span>
      </div>
      <div class="progress-card__item">
        <span class="progress-card__label">论文</span>
        <span class="progress-card__val">{{ progress?.publishedManuscripts ?? 0 }} / {{ progress?.totalManuscripts ?? 0 }}</span>
        <span class="progress-card__pct">{{ manuscriptsPct }}%</span>
      </div>
      <div class="progress-card__item">
        <span class="progress-card__label">知识</span>
        <span class="progress-card__val">{{ progress?.indexedKnowledge ?? 0 }} / {{ progress?.totalKnowledge ?? 0 }}</span>
        <span class="progress-card__pct">{{ knowledgePct }}%</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.progress-card {
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 12px;
  padding: 20px;
}
.progress-card__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 12px;
}
.progress-card__title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}
.progress-card__overall {
  font-size: 24px;
  font-weight: 700;
  color: #FF7A5C;
}
.progress-card__bar {
  height: 8px;
  background: rgba(15, 23, 42, 0.06);
  border-radius: 999px;
  margin-bottom: 16px;
  overflow: hidden;
}
.progress-card__bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #FF7A5C 0%, #FFB347 100%);
  border-radius: 999px;
  transition: width 400ms ease;
}
.progress-card__grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}
.progress-card__item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 12px;
  background: rgba(15, 23, 42, 0.02);
  border-radius: 8px;
}
.progress-card__label {
  font-size: 11px;
  color: #94a3b8;
}
.progress-card__val {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}
.progress-card__pct {
  font-size: 11px;
  color: #FF7A5C;
}
</style>