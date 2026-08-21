<script setup lang="ts">
/**
 * 分页器组件 —— 通用, Phase 2-Impl-2B KnowledgeView 已用。
 * 接收 PageInfo 直接渲染; emit page-change 事件。
 */
import type { PageInfo } from '@shared/knowledge-types'
import { computed } from 'vue'

interface Props {
  info: PageInfo
  /** 加载中显示 spinner 替代按钮 */
  loading?: boolean
}
const props = withDefaults(defineProps<Props>(), { loading: false })

const emit = defineEmits<{ 'page-change': [page: number] }>()

const windowSize = computed(() => {
  // 显示当前页前后各 1 页, 总共 ≤ 5 个数字
  const { page, totalPages } = props.info
  const pages: number[] = []
  const start = Math.max(1, page - 1)
  const end = Math.min(totalPages, page + 1)
  for (let p = start; p <= end; p++) pages.push(p)
  return pages
})

function goTo(p: number): void {
  if (p < 1 || p > props.info.totalPages) return
  if (p === props.info.page) return
  emit('page-change', p)
}

function prev(): void {
  if (props.info.hasPrev) goTo(props.info.page - 1)
}
function next(): void {
  if (props.info.hasNext) goTo(props.info.page + 1)
}
</script>

<template>
  <div class="paginator">
    <button
      type="button"
      class="pag-btn"
      :disabled="!info.hasPrev || loading"
      @click="prev"
    >
      ← 上一页
    </button>

    <button
      v-if="windowSize[0]! > 1"
      type="button"
      class="pag-btn"
      @click="goTo(1)"
    >
      1
    </button>
    <span v-if="windowSize[0]! > 2" class="pag-ellipsis">…</span>

    <button
      v-for="p in windowSize"
      :key="p"
      type="button"
      :class="['pag-btn', { 'is-active': p === info.page }]"
      @click="goTo(p)"
    >
      {{ p }}
    </button>

    <span v-if="windowSize[windowSize.length - 1]! < info.totalPages - 1" class="pag-ellipsis">…</span>
    <button
      v-if="windowSize[windowSize.length - 1]! < info.totalPages"
      type="button"
      class="pag-btn"
      @click="goTo(info.totalPages)"
    >
      {{ info.totalPages }}
    </button>

    <span class="pag-meta">
      第 {{ info.page }} / {{ info.totalPages }} 页 · 共 {{ info.total }} 条
    </span>

    <button
      type="button"
      class="pag-btn"
      :disabled="!info.hasNext || loading"
      @click="next"
    >
      下一页 →
    </button>
  </div>
</template>

<style scoped>
.paginator {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
  padding: 0.6rem 0;
  font-size: 0.85rem;
}
.pag-btn {
  background: transparent;
  border: 1px solid #334155;
  color: #cbd5e1;
  padding: 0.25rem 0.6rem;
  border-radius: 3px;
  cursor: pointer;
  font-family: inherit;
  font-size: 0.85rem;
  min-width: 1.8rem;
  text-align: center;
}
.pag-btn:hover:not(:disabled) {
  border-color: #f97316;
  color: #f97316;
}
.pag-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.pag-btn.is-active {
  background: #f97316;
  border-color: #f97316;
  color: #fff;
}
.pag-ellipsis {
  color: #64748b;
  padding: 0 0.2rem;
}
.pag-meta {
  margin: 0 0.5rem;
  color: #94a3b8;
  font-size: 0.8rem;
}
</style>
