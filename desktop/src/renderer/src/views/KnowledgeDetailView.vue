<script setup lang="ts">
/**
 * Knowledge Detail View —— Phase 2-Impl-2A 占位。
 *
 * 完整内容/引用/图谱渲染在 Phase 2-Impl-2B。本 Phase 仅:
 *   - 从 query 读 id
 *   - 调用 store.loadDetail(id)
 *   - 简单展示 title / category / tags / analysis_status / meta
 *
 * 数据源: window.api.api.request → main → GET /api/v1/knowledge/{id}
 */
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useKnowledgeStore } from '../stores/knowledge'
import { Card, Loading, ErrorState } from '../components/ui'
import { statusLabel, formatDateTime } from '@shared/knowledge-types'
import type { ApiError } from '@shared/preload-api'

const route = useRoute()
const router = useRouter()
const store = useKnowledgeStore()

const detailId = computed(() => {
  const raw = route.query['id']
  if (typeof raw === 'string') return Number(raw)
  if (typeof raw === 'number') return raw
  return NaN
})

async function load(): Promise<void> {
  if (!Number.isFinite(detailId.value) || detailId.value <= 0) return
  await store.loadDetail(detailId.value)
}

async function goBack(): Promise<void> {
  await router.push({ name: 'knowledge' })
}

onMounted(load)
watch(detailId, load)

function asError(e: ApiError | null): string {
  return e?.message ?? ''
}
</script>

<template>
  <div class="knowledge-detail">
    <button type="button" class="back-btn" @click="goBack">← 返回知识库</button>

    <Loading
      v-if="store.detailLoading && !store.currentDetail"
      variant="spinner"
      text="加载文档详情中..."
    />

    <ErrorState
      v-else-if="!store.currentDetail && store.lastError"
      :message="asError(store.lastError)"
      @retry="load"
    />

    <Card v-else-if="store.currentDetail" padding="lg" :title="store.currentDetail.title">
      <template #header>
        <div class="meta-row">
          <span class="meta-status">
            {{ statusLabel(store.currentDetail.analysis_status) }}
          </span>
          <span v-if="store.currentDetail.category" class="meta-cat">
            分类: {{ store.currentDetail.category }}
          </span>
          <span class="meta-time">
            更新于 {{ formatDateTime(store.currentDetail.updated_at) }}
          </span>
        </div>
      </template>

      <p v-if="store.currentDetail.summary" class="summary">{{ store.currentDetail.summary }}</p>

      <div v-if="store.currentDetail.tags && store.currentDetail.tags.length > 0" class="tag-row">
        <span v-for="t in store.currentDetail.tags" :key="t" class="tag-pill">{{ t }}</span>
      </div>

      <p class="placeholder">
        📄 详情页正文渲染 + 引用图谱 + 评论 + RAG streaming — Phase 2-Impl-2B+ 接入
        <br />
        当前 id = <code>{{ store.currentDetail.id }}</code>, 标题 = "{{ store.currentDetail.title }}"
      </p>
    </Card>
  </div>
</template>

<style scoped>
.knowledge-detail {
  padding: 1.5rem 2rem;
  max-width: 900px;
}
.back-btn {
  background: transparent;
  border: 0;
  color: #94a3b8;
  font-size: 0.85rem;
  cursor: pointer;
  margin-bottom: 1rem;
  font-family: inherit;
}
.back-btn:hover {
  color: #f97316;
}
.meta-row {
  display: flex;
  gap: 0.6rem;
  font-size: 0.8rem;
  color: #94a3b8;
}
.meta-status {
  background: rgba(249, 115, 22, 0.15);
  color: #f97316;
  padding: 0.15rem 0.5rem;
  border-radius: 3px;
}
.meta-cat, .meta-time {
  align-self: center;
}
.summary {
  margin: 0.5rem 0;
  font-size: 0.95rem;
  line-height: 1.6;
  color: #e2e8f0;
}
.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  margin-top: 0.4rem;
}
.tag-pill {
  font-size: 0.7rem;
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
  background: #334155;
  color: #cbd5e1;
}
.placeholder {
  margin: 2rem 0 0;
  padding: 1rem;
  background: rgba(99, 102, 241, 0.06);
  border: 1px dashed rgba(99, 102, 241, 0.3);
  border-radius: 6px;
  font-size: 0.85rem;
  color: #a5b4fc;
  text-align: center;
  line-height: 1.5;
}
.placeholder code {
  background: #0f172a;
  padding: 0.1em 0.3em;
  border-radius: 3px;
  color: #fbbf24;
}
</style>
