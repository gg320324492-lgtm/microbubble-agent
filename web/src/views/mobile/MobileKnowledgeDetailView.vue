<template>
  <div class="mobile-knowledge-detail">
    <PageHeader :title="knowledge?.title || '知识详情'" show-back @back="$router.back()">
      <template #right>
        <button
          type="button"
          class="header-action"
          aria-label="目录"
          title="目录"
          @click="showToc = true"
        >📑</button>
        <button
          type="button"
          class="header-action"
          aria-label="分享"
          title="分享"
          @click="shareCurrent"
        >🔗</button>
      </template>
    </PageHeader>

    <main
      v-if="knowledge"
      class="detail-main"
      :style="{ paddingBottom: 'calc(var(--tabbar-height, 56px) + var(--sab, 0px))' }"
    >
      <!-- 标题 -->
      <h1 class="detail-title">{{ knowledge.title }}</h1>

      <!-- 元信息 -->
      <div class="detail-meta">
        <span class="category-badge">{{ getCategoryLabel(knowledge.category) }}</span>
        <span v-if="knowledge.knowledge_type" class="type-badge">
          {{ knowledge.knowledge_type }}
        </span>
        <span class="detail-date">{{ formatDate(knowledge.created_at) }}</span>
      </div>

      <!-- 标签 -->
      <div v-if="knowledge.tags?.length" class="detail-tags">
        <span v-for="tag in knowledge.tags" :key="tag" class="tag-chip">#{{ tag }}</span>
      </div>

      <!-- 核心概念 -->
      <section v-if="knowledge.key_concepts?.length" class="content-section">
        <h3 class="section-title">💡 核心概念</h3>
        <div class="concept-list">
          <span v-for="c in knowledge.key_concepts" :key="c" class="concept-chip">
            {{ c }}
          </span>
        </div>
      </section>

      <!-- 关联主题 -->
      <section v-if="knowledge.related_topics?.length" class="content-section">
        <h3 class="section-title">🔗 关联主题</h3>
        <div class="concept-list">
          <span v-for="t in knowledge.related_topics" :key="t" class="topic-chip">
            {{ t }}
          </span>
        </div>
      </section>

      <!-- 知识三元组 -->
      <section v-if="knowledge.entities?.length" class="content-section">
        <h3 class="section-title">🔺 三元组</h3>
        <div class="triple-list">
          <div
            v-for="(e, i) in knowledge.entities"
            :key="i"
            class="triple-card"
          >
            <div class="triple-row">
              <span class="triple-subject">{{ e.subject }}</span>
              <span class="triple-predicate">{{ e.predicate }}</span>
              <span class="triple-object">{{ e.object }}</span>
            </div>
            <div v-if="e.condition" class="triple-condition">条件：{{ e.condition }}</div>
            <div v-if="e.confidence" class="triple-confidence">
              <div class="conf-bar" :style="{ width: (e.confidence * 100) + '%' }" />
            </div>
          </div>
        </div>
      </section>

      <!-- AI 摘要 -->
      <section v-if="knowledge.summary" class="content-section">
        <h3 class="section-title">📝 AI 摘要</h3>
        <div class="summary-text">{{ knowledge.summary }}</div>
      </section>

      <!-- 完整内容 -->
      <section v-if="knowledge.content" class="content-section">
        <h3 class="section-title">📄 完整内容</h3>
        <div class="content-text" v-html="formatContent(knowledge.content)" />
      </section>

      <!-- 来源 -->
      <section v-if="knowledge.source" class="content-section">
        <h3 class="section-title">🔗 来源</h3>
        <div class="source-text">{{ knowledge.source }}</div>
      </section>
    </main>

    <div v-else-if="loading" class="loading-state">
      <div class="loading-spinner" />
      <p>加载中...</p>
    </div>

    <!-- 目录 Sheet -->
    <Teleport to="body">
      <Transition name="toc-sheet">
        <div v-if="showToc" class="toc-overlay" @click.self="showToc = false">
          <div class="toc-panel" :style="{ paddingBottom: 'calc(16px + var(--sab, 0px) + var(--tabbar-height, 56px))' }">
            <div class="toc-handle" />
            <h3 class="toc-title">📑 目录</h3>
            <div class="toc-list">
              <button
                v-for="(section, idx) in sections"
                :key="idx"
                type="button"
                class="toc-item"
                @click="scrollToSection(section.key)"
              >
                {{ section.label }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
/**
 * MobileKnowledgeDetailView.vue — 移动端知识详情
 *
 * PR #8b: 单列堆叠布局（无桌面版双栏）
 * - 顶部元信息（分类/类型/日期/标签）
 * - 核心概念 + 关联主题（chip 展示）
 * - 三元组列表（带置信度进度条）
 * - AI 摘要 + 完整内容 + 来源
 * - 目录 Sheet（左侧弹出，章节跳转）
 */

import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import dayjs from 'dayjs'
import PageHeader from '@/components/mobile/PageHeader.vue'

const route = useRoute()
const knowledge = ref(null)
const loading = ref(true)
const showToc = ref(false)

const sections = [
  { key: 'concepts', label: '💡 核心概念' },
  { key: 'topics', label: '🔗 关联主题' },
  { key: 'triples', label: '🔺 三元组' },
  { key: 'summary', label: '📝 AI 摘要' },
  { key: 'content', label: '📄 完整内容' },
  { key: 'source', label: '🔗 来源' },
]

async function fetchKnowledge() {
  const id = route.params.id
  if (!id) return
  loading.value = true
  try {
    const res = await axios.get(`/api/v1/knowledge/${id}`)
    knowledge.value = res.data
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function getCategoryLabel(c) {
  return {
    microbubble: '微纳米气泡',
    water: '水处理',
    agriculture: '农业',
    disinfection: '消毒',
    measurement: '测量',
    application: '应用',
  }[c] || c || '未分类'
}

function formatDate(t) {
  if (!t) return ''
  return dayjs(t).format('YYYY-MM-DD')
}

// 分享当前知识条目（Web Share API 优先，fallback 复制链接）
async function shareCurrent() {
  const title = knowledge.value?.title || '知识条目'
  const url = window.location.href
  try {
    if (navigator.share) {
      await navigator.share({ title, url })
    } else if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(url)
      ElMessage.success('链接已复制')
    } else {
      ElMessage.info('请手动复制链接：' + url)
    }
  } catch (e) {
    if (e.name !== 'AbortError') {
      ElMessage.error('分享失败：' + (e.message || '未知错误'))
    }
  }
}

function formatContent(content) {
  if (!content) return ''
  // 简单换行处理
  return content.replace(/\n/g, '<br>')
}

function scrollToSection(key) {
  showToc.value = false
  setTimeout(() => {
    const el = document.querySelector(`[data-section="${key}"]`)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, 300)
}

onMounted(() => {
  fetchKnowledge()
})
</script>

<style scoped>
.mobile-knowledge-detail {
  min-height: 100vh;
  background: var(--color-bg-page);
  display: flex;
  flex-direction: column;
}

.detail-main {
  flex: 1;
  padding: var(--mobile-padding-y, 12px) var(--mobile-padding-x, 16px);
}

/* 标题 */
.detail-title {
  font-size: 20px;
  font-weight: var(--font-weight-bold, 700);
  color: var(--color-text-primary);
  line-height: 1.4;
  margin: 0 0 12px;
}

/* 元信息 */
.detail-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
  font-size: 12px;
  color: var(--color-text-secondary);
}
.category-badge, .type-badge {
  padding: 2px 8px;
  background: var(--color-primary-bg);
  color: var(--color-primary);
  border-radius: var(--radius-sm);
}
.type-badge {
  background: var(--color-bg-page);
  color: var(--color-text-regular);
}
.detail-date {
  font-size: 11px;
}

/* 标签 */
.detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 16px;
}
.tag-chip {
  padding: 4px 10px;
  background: var(--color-primary-bg);
  color: var(--color-primary);
  border-radius: var(--radius-full);
  font-size: 11px;
}

/* 内容区 */
.content-section {
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
  padding: 16px;
  margin-bottom: 12px;
}
.section-title {
  font-size: 14px;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary);
  margin: 0 0 12px;
  padding-left: 8px;
  border-left: 3px solid var(--color-primary);
}

/* 概念 / 主题 */
.concept-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.concept-chip, .topic-chip {
  padding: 4px 10px;
  background: var(--color-bg-page);
  color: var(--color-text-primary);
  border-radius: var(--radius-sm);
  font-size: 12px;
}
.topic-chip {
  background: var(--color-warning-bg);
  color: var(--color-warning, #E6A23C);
}

/* 三元组 */
.triple-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.triple-card {
  padding: 10px 12px;
  background: var(--color-bg-page);
  border-radius: var(--radius-sm);
}
.triple-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  flex-wrap: wrap;
}
.triple-subject, .triple-object {
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-primary);
}
.triple-predicate {
  color: var(--color-text-secondary);
  font-size: 12px;
}
.triple-condition {
  font-size: 11px;
  color: var(--color-text-secondary);
  margin-top: 4px;
}
.triple-confidence {
  margin-top: 6px;
  height: 3px;
  background: var(--color-border);
  border-radius: 2px;
  overflow: hidden;
}
.conf-bar {
  height: 100%;
  background: var(--color-primary);
}

/* 摘要 + 内容 */
.summary-text, .content-text, .source-text {
  font-size: 14px;
  color: var(--color-text-primary);
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}
.source-text {
  color: var(--color-primary);
  text-decoration: underline;
}

/* 加载 */
.loading-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
}
.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--color-border);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Header */
.header-action {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: transparent;
  border: none;
  font-size: 18px;
  color: var(--color-text-regular);
  cursor: pointer;
}
.header-action:active { background: var(--color-primary-bg); }

/* 目录 Sheet */
.toc-overlay {
  position: fixed;
  inset: 0;
  z-index: 4500;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: flex-end;
}
.toc-panel {
  width: 80%;
  max-width: 320px;
  background: var(--color-bg-card);
  border-radius: 0 var(--sheet-radius, 16px) var(--sheet-radius, 16px) 0;
  padding: 8px 16px;
  height: 100%;
  overflow-y: auto;
}
[data-theme="dark"] .toc-panel { background: var(--color-bg-card); }
.toc-handle {
  display: none;
}
.toc-title {
  font-size: 16px;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary);
  margin: 12px 0 16px;
}
.toc-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.toc-item {
  padding: 12px;
  background: transparent;
  border: none;
  border-radius: var(--radius-md);
  font-size: 14px;
  color: var(--color-text-primary);
  text-align: left;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.toc-item:active { background: var(--color-primary-bg); color: var(--color-primary); }

.toc-sheet-enter-active, .toc-sheet-leave-active {
  transition: opacity 0.25s ease;
}
.toc-sheet-enter-active .toc-panel, .toc-sheet-leave-active .toc-panel {
  transition: transform 0.3s cubic-bezier(0.32, 0.72, 0, 1);
}
.toc-sheet-enter-from, .toc-sheet-leave-to { opacity: 0; }
.toc-sheet-enter-from .toc-panel, .toc-sheet-leave-to .toc-panel {
  transform: translateX(-100%);
}
</style>