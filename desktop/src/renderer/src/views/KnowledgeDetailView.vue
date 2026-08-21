<script setup lang="ts">
/**
 * Knowledge Detail Pro View (Phase 2-Impl-2B) + Phase 3-D Back Nav.
 *
 * 3 栏布局:
 *   ┌──────────────────────────────────────────┬──────────────┐
 *   │ Header (title + status + meta)             │              │
 *   │ Summary 卡片 (LLM 摘要)                     │   Metadata   │
 *   │ Content (MarkdownViewer 安全渲染 content)    │   (sticky)   │
 *   │ Citations 占位 (Phase 3+ 接 RAG)             │              │
 *   └──────────────────────────────────────────┴──────────────┘
 *
 * 数据源: window.api.api.request → main api.service → FastAPI GET /knowledge/{id}
 *
 * Phase 3-D: back navigation 智能返回 (citation 来源 -> 返回 Chat, 否则 -> 知识库列表).
 * - 从 ChatView 的 citation 点击进入: query ?from=chat -> back 走 router.back() 保留 ChatView 状态
 *   (Pinia store 全局保持 sessions/messages; ChatView 重新 mount 即可)
 * - 从 KnowledgeView 列表进入: 默认走知识库列表
 *
 * 范围 (Phase 3-D 严格):
 *   - ✅ Citation click -> router.push('/knowledge/detail?id=N&from=chat') 闭环
 *   - ✅ KnowledgeDetailView back nav 区分来源
 *   - ❌ RAG / Retriever / Knowledge API / Agent Tool / Backend schema
 */
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useKnowledgeStore } from '../stores/knowledge'
import { Card, Loading, ErrorState, MarkdownViewer } from '../components/ui'
import { cameFromChat, validateKnowledgeIdFromQuery } from '../utils/knowledge-route'
import {
  statusLabel,
  statusVariant,
  formatDateTime
} from '@shared/knowledge-types'
import type { ApiError } from '@shared/preload-api'

const route = useRoute()
const router = useRouter()
const store = useKnowledgeStore()

const detailId = computed(() => {
  const raw = route.query['id']
  return validateKnowledgeIdFromQuery(raw)
})

/**
 * Phase 3-D: 来源标记 (从 citation click 进入 vs 从 knowledge 列表直接进入).
 * - from=chat -> router.back() (history; ChatView 保留)
 * - 其它 -> 知识库列表 (与 Phase 2-Impl-2B 行为一致)
 */
const fromChat = computed(() => cameFromChat(route.query))

const detail = computed(() => store.currentDetail)
const metaJson = computed(() => {
  if (!detail.value?.meta) return null
  try {
    return JSON.stringify(detail.value.meta, null, 2)
  } catch (_e) {
    return null
  }
})
const hasTags = computed(() => !!(detail.value?.tags && detail.value.tags.length > 0))
const hasKeyConcepts = computed(() => !!(detail.value?.key_concepts && detail.value.key_concepts.length > 0))
const hasRelatedTopics = computed(() => !!(detail.value?.related_topics && detail.value.related_topics.length > 0))

async function load(): Promise<void> {
  // Phase 3-D: detailId 已通过 validateKnowledgeIdFromQuery 严格校验 (positive integer).
  // 这里再 double-check (类型; future-proof).
  const id = detailId.value
  if (id === null) return
  await store.loadDetail(id)
}

async function goBack(): Promise<void> {
  // Phase 3-D: 来源 chat -> history back (Pinia 状态天然保持).
  // 其它 -> 知识库列表 (Phase 2-Impl-2B 行为).
  if (fromChat.value) {
    if (window.history.length > 1) {
      router.back()
      return
    }
    // 边界: history 空 (e.g. 直接深链接进入 ChatView -> 点击, 也兜底到 chat)
    await router.push({ name: 'chat' })
    return
  }
  await router.push({ name: 'knowledge' })
}

function asError(e: ApiError | null): string {
  return e?.message ?? ''
}

function statusPillClass(s: string | null | undefined): string {
  switch (statusVariant(s)) {
    case 'ok': return 'status-pill status-ok'
    case 'warn': return 'status-pill status-warn'
    case 'error': return 'status-pill status-error'
    default: return 'status-pill status-mute'
  }
}

onMounted(load)
watch(detailId, load)
</script>

<template>
  <div class="knowledge-detail">
    <button type="button" class="back-btn" @click="goBack">
      ← {{ fromChat ? '返回 Chat' : '返回知识库' }}
    </button>

    <Loading
      v-if="store.detailLoading && !detail"
      variant="spinner"
      text="加载文档详情中..."
    />

    <ErrorState
      v-else-if="!detail && store.lastError"
      :message="asError(store.lastError)"
      @retry="load"
    />

    <div v-else-if="detail" class="kd-grid">
      <!-- 主区 -->
      <main class="kd-main">
        <!-- Header: title + status pill + category + 时间 + tags -->
        <header class="kd-header">
          <div class="kd-header-row">
            <h1 class="kd-title">{{ detail.title }}</h1>
            <span :class="statusPillClass(detail.analysis_status)">
              {{ statusLabel(detail.analysis_status) }}
            </span>
          </div>
          <div class="kd-meta-row">
            <span v-if="detail.category" class="kd-category-badge">📁 {{ detail.category }}</span>
            <span class="kd-time">🕒 更新于 {{ formatDateTime(detail.updated_at) }}</span>
            <span class="kd-id">#{{ detail.id }}</span>
          </div>
          <div v-if="hasTags" class="kd-tag-row">
            <span v-for="t in detail.tags" :key="t" class="kd-tag-pill">{{ t }}</span>
          </div>
        </header>

        <!-- Summary -->
        <Card v-if="detail.summary" title="LLM 摘要" padding="md" class="kd-summary-card">
          <p class="kd-summary">{{ detail.summary }}</p>
        </Card>

        <!-- Content (Markdown 安全渲染) -->
        <Card title="正文" subtitle="Markdown 渲染 (Phase 2-Impl-2B 安全版)" padding="md" class="kd-content-card">
          <template v-if="detail.content">
            <MarkdownViewer :source="detail.content" />
          </template>
          <p v-else class="muted">（无正文内容）</p>
        </Card>

        <!-- Citations 占位 (Phase 3+ 启用 RAG) -->
        <Card title="📚 引用与关联" subtitle="Citations & References" padding="md" class="kd-citation-card">
          <div class="citation-placeholder">
            <p>🔍 RAG 引用与关联知识（Phase 3+ 集成）</p>
            <p class="muted">
              来源后端：<code>GET /api/v1/knowledge/{id}/related</code> →
              <code>RelatedKnowledge[]</code>
            </p>
            <p class="muted">
              数据流：knowledge-detail-contract.md §5 已 freeze 接口与 UI 占位
            </p>
          </div>
        </Card>
      </main>

      <!-- Sidebar sticky -->
      <aside class="kd-sidebar">
        <Card title="📋 元信息" padding="md" class="kd-meta-card">
          <dl class="kd-meta-list">
            <div v-if="detail.knowledge_type">
              <dt>类型</dt>
              <dd>{{ detail.knowledge_type }}</dd>
            </div>
            <div v-if="detail.topic">
              <dt>学科领域</dt>
              <dd>{{ detail.topic }}</dd>
            </div>
            <div v-if="detail.source_type">
              <dt>来源类型</dt>
              <dd><code>{{ detail.source_type }}</code></dd>
            </div>
            <div v-if="detail.source">
              <dt>原文链接</dt>
              <dd><a :href="detail.source" target="_blank" rel="noopener noreferrer" class="kd-link">{{ detail.source }}</a></dd>
            </div>
            <div v-if="detail.file_name">
              <dt>附件</dt>
              <dd>📎 {{ detail.file_name }} <span v-if="detail.file_type" class="muted">({{ detail.file_type }})</span></dd>
            </div>
            <div>
              <dt>创建于</dt>
              <dd>{{ formatDateTime(detail.created_at) || '—' }}</dd>
            </div>
            <div>
              <dt>质量评分</dt>
              <dd>
                <span v-if="detail.quality_score != null">{{ detail.quality_score.toFixed(2) }}</span>
                <span v-else class="muted">—</span>
              </dd>
            </div>
            <div v-if="detail.needs_review">
              <dt>人工复核</dt>
              <dd><span class="kd-review-badge">⚠️ 需要复核</span></dd>
            </div>
            <div v-if="detail.image_count > 0">
              <dt>图片数</dt>
              <dd>🖼 {{ detail.image_count }}</dd>
            </div>
            <div v-if="detail.created_by">
              <dt>创建者</dt>
              <dd>用户 #{{ detail.created_by }}</dd>
            </div>
          </dl>
        </Card>

        <Card v-if="hasKeyConcepts" title="🔑 关键概念" padding="md" class="kd-key-concepts-card">
          <div class="kd-key-concepts">
            <span v-for="(c, i) in detail.key_concepts" :key="`kc-${i}`" class="kd-key-concept-pill">{{ c }}</span>
          </div>
        </Card>

        <Card v-if="hasRelatedTopics" title="🔗 相关主题" padding="md" class="kd-related-topics-card">
          <div class="kd-related-topics">
            <span v-for="(t, i) in detail.related_topics" :key="`rt-${i}`" class="kd-topic-pill">{{ t }}</span>
          </div>
        </Card>

        <Card v-if="metaJson" title="🗂 原始 meta" padding="md" class="kd-meta-json-card">
          <pre class="kd-meta-json">{{ metaJson }}</pre>
        </Card>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.knowledge-detail {
  padding: 1.5rem 2rem;
  max-width: 1200px;
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
.back-btn:hover { color: #f97316; }

.kd-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 1.2rem;
  align-items: start;
}
.kd-main {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-width: 0;
}
.kd-sidebar {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  position: sticky;
  top: 0.5rem;
}

.kd-header {
  background: linear-gradient(135deg, rgba(249, 115, 22, 0.08), rgba(251, 191, 36, 0.03));
  border: 1px solid rgba(249, 115, 22, 0.18);
  border-radius: 8px;
  padding: 1.2rem 1.4rem;
}
.kd-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
}
.kd-title {
  margin: 0;
  font-size: 1.4rem;
  font-weight: 600;
  color: #f1f5f9;
  line-height: 1.3;
  word-break: break-word;
}
.status-pill {
  font-size: 0.7rem;
  padding: 0.15rem 0.55rem;
  border-radius: 3px;
  flex-shrink: 0;
}
.status-pill.status-ok { background: rgba(16, 185, 129, 0.15); color: #10b981; }
.status-pill.status-warn { background: rgba(251, 191, 36, 0.15); color: #fbbf24; }
.status-pill.status-error { background: rgba(239, 68, 68, 0.15); color: #ef4444; }
.status-pill.status-mute { background: #334155; color: #94a3b8; }

.kd-meta-row {
  margin-top: 0.6rem;
  display: flex;
  gap: 0.8rem;
  flex-wrap: wrap;
  font-size: 0.8rem;
  color: #94a3b8;
}
.kd-category-badge {
  background: rgba(99, 102, 241, 0.15);
  color: #c7d2fe;
  padding: 0.15rem 0.5rem;
  border-radius: 3px;
}
.kd-id { color: #64748b; font-family: monospace; }

.kd-tag-row {
  margin-top: 0.6rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}
.kd-tag-pill {
  font-size: 0.7rem;
  padding: 0.15rem 0.5rem;
  border-radius: 3px;
  background: #334155;
  color: #cbd5e1;
}

.kd-summary-card, .kd-content-card, .kd-citation-card {
  background: #1e293b;
  border: 1px solid #334155;
}
.kd-summary {
  margin: 0;
  font-size: 0.95rem;
  line-height: 1.6;
  color: #e2e8f0;
  white-space: pre-wrap;
}
.muted { color: #64748b; font-size: 0.85rem; }

.citation-placeholder {
  padding: 1rem;
  border: 1px dashed #475569;
  border-radius: 6px;
  text-align: center;
  font-size: 0.85rem;
  color: #cbd5e1;
}
.citation-placeholder code {
  background: #0f172a;
  padding: 0.1em 0.3em;
  border-radius: 3px;
  color: #fbbf24;
  font-size: 0.8rem;
}

.kd-meta-card, .kd-key-concepts-card, .kd-related-topics-card, .kd-meta-json-card {
  background: #1e293b;
  border: 1px solid #334155;
}
.kd-meta-list {
  margin: 0;
  display: grid;
  grid-template-columns: auto;
  gap: 0.5rem;
  font-size: 0.82rem;
}
.kd-meta-list > div {
  display: flex;
  flex-direction: column;
}
.kd-meta-list dt {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #64748b;
  margin-bottom: 0.15rem;
}
.kd-meta-list dd {
  margin: 0;
  color: #e2e8f0;
  word-break: break-all;
}
.kd-link { color: #f97316; text-decoration: underline; }
.kd-review-badge {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
  padding: 0.15rem 0.5rem;
  border-radius: 3px;
  font-size: 0.75rem;
}
code {
  background: #0f172a;
  padding: 0.05em 0.3em;
  border-radius: 2px;
  font-size: 0.85em;
  color: #fbbf24;
}

.kd-key-concepts, .kd-related-topics {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}
.kd-key-concept-pill {
  background: rgba(139, 92, 246, 0.15);
  color: #c4b5fd;
  padding: 0.15rem 0.5rem;
  border-radius: 3px;
  font-size: 0.75rem;
}
.kd-topic-pill {
  background: rgba(20, 184, 166, 0.15);
  color: #5eead4;
  padding: 0.15rem 0.5rem;
  border-radius: 3px;
  font-size: 0.75rem;
}
.kd-meta-json {
  margin: 0;
  background: #0b1220;
  border: 1px solid #1e293b;
  border-radius: 4px;
  padding: 0.6rem;
  font-size: 0.75rem;
  color: #94a3b8;
  max-height: 250px;
  overflow-y: auto;
  white-space: pre-wrap;
}

@media (max-width: 900px) {
  .kd-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .kd-sidebar {
    position: static;
  }
}
</style>
