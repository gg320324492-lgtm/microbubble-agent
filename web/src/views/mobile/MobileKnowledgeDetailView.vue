<template>
  <div class="mobile-knowledge-detail mg-page">
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
        <span class="category-badge" :class="knowledge.category ? `knowledge-color-${knowledge.category}` : ''">
          <span class="category-dot" aria-hidden="true" />{{ getCategoryLabel(knowledge.category) }}
        </span>
        <span v-if="knowledge.knowledge_type" class="type-badge">
          {{ knowledge.knowledge_type }}
        </span>
        <span class="detail-date">{{ formatDate(knowledge.created_at) }}</span>
      </div>

      <!-- 标签 -->
      <div v-if="knowledge.tags?.length" class="detail-tags">
        <span v-for="tag in knowledge.tags" :key="tag" class="tag-chip mg-chip">#{{ tag }}</span>
      </div>

      <!-- 核心概念 -->
      <section v-if="knowledge.key_concepts?.length" class="content-section mg-rise mg-stagger-1">
        <h3 class="section-title">💡 核心概念</h3>
        <div class="concept-list">
          <span v-for="c in knowledge.key_concepts" :key="c" class="concept-chip">
            {{ c }}
          </span>
        </div>
      </section>

      <!-- 关联主题 -->
      <section v-if="knowledge.related_topics?.length" class="content-section mg-rise mg-stagger-2">
        <h3 class="section-title">🔗 关联主题</h3>
        <div class="concept-list">
          <span v-for="t in knowledge.related_topics" :key="t" class="topic-chip">
            {{ t }}
          </span>
        </div>
      </section>

      <!-- 知识三元组 -->
      <section v-if="knowledge.entities?.length" class="content-section mg-rise mg-stagger-3">
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
      <section v-if="knowledge.summary" class="content-section content-section--main mg-rise mg-stagger-4">
        <h3 class="section-title">📝 AI 摘要</h3>
        <div class="summary-text">{{ knowledge.summary }}</div>
      </section>

      <!-- 完整内容 -->
      <section v-if="knowledge.content" class="content-section content-section--main mg-rise mg-stagger-5">
        <h3 class="section-title">📄 完整内容</h3>
        <div class="content-text" v-html="formatContent(knowledge.content)" />
      </section>

      <!-- 来源 -->
      <section v-if="knowledge.source" class="content-section mg-rise mg-stagger-5">
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
import { formatDate } from '@/utils/format'
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
  /* 2026-08-31 液态毛玻璃升级: 颜色/圆角/阴影全部走 --mg-* token,
     极光背景由根节点 .mg-page 提供. 详情页可读性优先: 正文卡背景提到 --mg-glass-bg-strong. */
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
  font-weight: 800;
  color: var(--mg-text-strong);
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
  color: var(--mg-text-soft);
}
.category-badge, .type-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  background: var(--mg-glass-bg-strong);
  border: 1.5px solid var(--mg-glass-border);
  color: var(--mg-primary);
  border-radius: var(--mg-radius-pill);
  font-weight: 600;
}
/* 分类色点: 沿用全局 .knowledge-color-* 的 --accent 原色语义, 无分类时回落主色 */
.category-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--accent, var(--mg-primary));
  flex-shrink: 0;
}
.type-badge {
  color: var(--mg-text-soft);
}
.detail-date {
  font-size: 11px;
  color: var(--mg-text-soft);
}

/* 标签 (基础胶囊形状/色由模板上的 .mg-chip 提供) */
.detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 16px;
}
.tag-chip {
  font-size: 11px;
}

/* 内容区: 玻璃卡; --main (摘要/完整内容) 背景提高保证可读性 */
.content-section {
  background: var(--mg-glass-bg);
  border: 1.5px solid var(--mg-glass-border);
  -webkit-backdrop-filter: blur(var(--mg-glass-blur));
  backdrop-filter: blur(var(--mg-glass-blur));
  border-radius: var(--mg-radius-lg);
  box-shadow: var(--mg-shadow-sm);
  padding: 16px;
  margin-bottom: 12px;
}
.content-section--main {
  background: var(--mg-glass-bg-strong);
  box-shadow: var(--mg-shadow);
}
.section-title {
  font-size: 14px;
  font-weight: 800;
  color: var(--mg-text-strong);
  margin: 0 0 12px;
  padding-left: 8px;
  border-left: 3px solid var(--mg-primary);
}

/* 概念 / 主题 */
.concept-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.concept-chip, .topic-chip {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  background: var(--mg-glass-bg-strong);
  border: 1px solid var(--mg-glass-border);
  color: var(--mg-text);
  border-radius: var(--mg-radius-pill);
  font-size: 12px;
}
.topic-chip {
  background: var(--mg-warning-soft);
  border-color: transparent;
  color: var(--mg-warning);
}

/* 三元组 */
.triple-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.triple-card {
  padding: 10px 12px;
  background: var(--mg-glass-bg-strong);
  border: 1px solid var(--mg-glass-border);
  border-radius: var(--mg-radius-md);
}
.triple-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  flex-wrap: wrap;
}
.triple-subject, .triple-object {
  font-weight: 700;
  color: var(--mg-primary);
}
.triple-predicate {
  color: var(--mg-text-soft);
  font-size: 12px;
}
.triple-condition {
  font-size: 11px;
  color: var(--mg-text-soft);
  margin-top: 4px;
}
.triple-confidence {
  margin-top: 6px;
  height: 3px;
  background: var(--mg-glass-border);
  border-radius: 2px;
  overflow: hidden;
}
.conf-bar {
  height: 100%;
  background: var(--mg-gradient-btn);
}

/* 摘要 + 内容 */
.summary-text, .content-text, .source-text {
  font-size: 14px;
  color: var(--mg-text);
  line-height: 1.7;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.source-text {
  color: var(--mg-primary);
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
  color: var(--mg-text-soft);
}
.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--mg-glass-border);
  border-top-color: var(--mg-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
/* Header — 玻璃胶囊 (与列表页一致, 触摸目标 44px) */
.header-action {
  width: 44px;
  height: 44px;
  border-radius: var(--mg-radius-pill);
  background: var(--mg-glass-bg-strong);
  border: 1.5px solid var(--mg-glass-border);
  -webkit-backdrop-filter: blur(12px);
  backdrop-filter: blur(12px);
  box-shadow: var(--mg-shadow-sm);
  font-size: 18px;
  color: var(--mg-text);
  cursor: pointer;
  transition: transform 150ms ease;
  -webkit-tap-highlight-color: transparent;
}
.header-action:active { transform: scale(0.94); }

/* 目录 Sheet — 悬浮强玻璃面板 (mg token 自带 dark 变体) */
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
  background: var(--mg-glass-bg-strong);
  border: 1.5px solid var(--mg-glass-border);
  -webkit-backdrop-filter: blur(24px);
  backdrop-filter: blur(24px);
  box-shadow: var(--mg-shadow-lg);
  border-radius: 0 var(--mg-radius-lg) var(--mg-radius-lg) 0;
  padding: 8px 16px;
  height: 100%;
  overflow-y: auto;
}
.toc-handle {
  display: none;
}
.toc-title {
  font-size: 16px;
  font-weight: 800;
  color: var(--mg-text-strong);
  margin: 12px 0 16px;
}
.toc-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.toc-item {
  min-height: 44px;
  padding: 12px;
  background: transparent;
  border: none;
  border-radius: var(--mg-radius-md);
  font-size: 14px;
  color: var(--mg-text);
  text-align: left;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.toc-item:active { background: var(--mg-glass-bg); color: var(--mg-primary); }

.toc-sheet-enter-active, .toc-sheet-leave-active {
  transition: opacity 0.25s ease;
}
.toc-sheet-enter-active .toc-panel, .toc-sheet-leave-active .toc-panel {
  transition: transform 0.3s var(--ease-sheet);
}
.toc-sheet-enter-from, .toc-sheet-leave-to { opacity: 0; }
.toc-sheet-enter-from .toc-panel, .toc-sheet-leave-to .toc-panel {
  transform: translateX(-100%);
}
</style>