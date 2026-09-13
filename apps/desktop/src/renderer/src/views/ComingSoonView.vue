<script setup lang="ts">
// 通用"即将到来"占位页 — ELN/稿件/知识库/会议（路由 meta 提供标题与里程碑）
import { useRoute } from 'vue-router'

const route = useRoute()
const title = (route.meta.title as string) ?? '模块'
const milestone = (route.meta.milestone as string) ?? '后续版本'
</script>

<template>
  <div class="coming">
    <div class="coming-card card">
      <span class="coming-badge">{{ milestone }}</span>
      <h1>{{ title }}</h1>
      <p>
        {{ title }}将按里程碑规划逐个落地，采用本地优先架构——数据存本机、断网可用。
        实际验收不达标的功能会被移出桌面端，保留在网页端使用。
      </p>
    </div>
  </div>
</template>

<style scoped>
.coming {
  height: 100%;
  display: grid;
  place-items: center;
}
.coming-card {
  max-width: 480px;
  padding: var(--space-10);
  text-align: center;
}
.coming-badge {
  display: inline-block;
  padding: 3px 12px;
  border-radius: var(--radius-full);
  background: var(--color-primary-bg);
  color: var(--color-primary-dark);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
}
.coming-card h1 {
  margin-top: var(--space-4);
  font-size: 20px;
  font-weight: var(--font-weight-semibold);
}
.coming-card p {
  margin-top: var(--space-3);
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  line-height: 1.8;
}
</style>
