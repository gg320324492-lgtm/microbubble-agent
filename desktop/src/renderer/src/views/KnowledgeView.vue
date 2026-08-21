<script setup lang="ts">
/**
 * Knowledge View (Phase 2-Impl-2A 基础模块)。
 *
 * 双栏布局:
 *   ┌──────────┬────────────────────────────┐
 *   │ 左侧分类  │ 右上 搜索框 + 中 文档列表       │
 *   └──────────┴────────────────────────────┘
 *
 * 数据源 (全部走 window.api.api.request → main api.service → 后端):
 *   - GET /knowledge/categories      → 左侧分类
 *   - GET /knowledge?category=&keyword=&page=  → 中间列表
 *   - GET /knowledge/{id}             → 详情入口 (Phase 2-Impl-2B 占位)
 *
 * 范围外 (Phase 2-Impl-2A 不做):
 *   - 语义搜索 UI (Phase 3+ RAG streaming)
 *   - 上传大文件 (Phase 3+)
 *   - 详情页内容渲染 (Phase 2-Impl-2B)
 */
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useKnowledgeStore } from '../stores/knowledge'
import {
  Card,
  Loading,
  EmptyState,
  ErrorState,
  Pagination
} from '../components/ui'
import { statusLabel, statusVariant, formatDateTime } from '@shared/knowledge-types'
import type { KnowledgeListItem } from '@shared/knowledge-types'

const router = useRouter()
const store = useKnowledgeStore()

const searchInput = ref(store.keyword)
// 防抖搜索
let searchTimer: ReturnType<typeof setTimeout> | null = null

function onSearchInput(): void {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    void store.search(searchInput.value)
  }, 300)
}

function onCategoryClick(name: string): void {
  void store.selectCategory(name)
}

async function onCardClick(item: KnowledgeListItem): Promise<void> {
  // Phase 2-Impl-2A: 仅路由占位, 详情页 next phase
  const ok = await store.loadDetail(item.id)
  if (ok) {
    await router.push({ name: 'knowledge-detail', query: { id: item.id } })
  }
}

function onPageChange(p: number): void {
  void store.goToPage(p)
}

const statusClassMap: Record<'ok' | 'warn' | 'error' | 'mute', string> = {
  ok: 'status-ok',
  warn: 'status-warn',
  error: 'status-error',
  mute: 'status-mute'
}

function variantClass(variant: 'ok' | 'warn' | 'error' | 'mute'): string {
  return statusClassMap[variant]
}

function tagClass(tag: string): string {
  // 简单 hash 给 tag 一个稳定颜色
  let hash = 0
  for (let i = 0; i < tag.length; i++) hash = (hash * 31 + tag.charCodeAt(i)) >>> 0
  return `tag-h${hash % 6}`
}

onMounted(() => {
  void store.bootstrap()
})
</script>

<template>
  <div class="knowledge-view">
    <!-- 左侧分类 -->
    <aside class="knowledge-view__sidebar">
      <div class="sidebar-section-title">知识库分类</div>
      <Loading v-if="store.loading && store.categories.length === 0" variant="skeleton" :rows="6" />
      <EmptyState
        v-else-if="store.categories.length === 0 && !store.loading"
        icon="🗂️"
        title="暂无分类"
        description="知识库还没有条目"
      />
      <ul v-else class="category-list">
        <li>
          <button
            type="button"
            :class="['category-item', { 'is-active': store.selectedCategory === 'all' }]"
            @click="onCategoryClick('all')"
          >
            <span class="category-name">⌬ 全部</span>
            <span class="category-count">{{ store.totalCount }}</span>
          </button>
        </li>
        <li v-for="cat in store.categories" :key="cat.name">
          <button
            type="button"
            :class="['category-item', { 'is-active': store.selectedCategory === cat.name }]"
            @click="onCategoryClick(cat.name)"
          >
            <span class="category-name">{{ cat.name }}</span>
            <span class="category-count">{{ cat.count }}</span>
          </button>
        </li>
      </ul>
    </aside>

    <!-- 主区 -->
    <section class="knowledge-view__main">
      <div class="knowledge-view__search">
        <input
          v-model="searchInput"
          type="search"
          placeholder="搜索知识库标题 / 内容关键词..."
          class="search-input"
          @input="onSearchInput"
        />
        <button class="search-btn" type="button" disabled title="Phase 3+ RAG">
          🔍 语义搜索
        </button>
      </div>

      <ErrorState
        v-if="store.lastError && store.items.length === 0"
        :message="store.lastError.message"
        @retry="() => store.loadList()"
      />

      <div v-else>
        <div class="list-meta">
          <span>
            {{ store.selectedCategory === 'all' ? '全部' : store.selectedCategory }} ·
            {{ store.total }} 条 · 第 {{ store.page }} 页
          </span>
        </div>

        <Loading v-if="store.loading && store.items.length === 0" variant="skeleton" :rows="4" />

        <EmptyState
          v-else-if="store.items.length === 0 && !store.loading"
          icon="🔍"
          title="无匹配条目"
          :description="searchInput ? `没有与「${searchInput}」匹配的文档` : '该分类下还没有文档'"
        />

        <ul v-else class="card-list">
          <li v-for="item in store.items" :key="item.id">
            <Card padding="md">
              <template #header>
                <div class="card-header">
                  <h3 class="card-title" @click="onCardClick(item)">{{ item.title }}</h3>
                  <span :class="['status-pill', variantClass(statusVariant(item.analysis_status))]">
                    {{ statusLabel(item.analysis_status) }}
                  </span>
                </div>
              </template>
              <p v-if="item.snippet" class="card-snippet">{{ item.snippet }}</p>
              <p v-else-if="item.summary" class="card-snippet">{{ item.summary }}</p>
              <p v-else class="card-snippet muted">（无摘要 / snippet）</p>

              <div v-if="item.tags && item.tags.length > 0" class="tag-row">
                <span v-for="t in item.tags" :key="t" :class="['tag', tagClass(t)]">{{ t }}</span>
              </div>

              <template #footer>
                <div class="card-footer">
                  <span class="footer-item">
                    🕒 更新于 {{ formatDateTime(item.updated_at) || '未知' }}
                  </span>
                  <span v-if="item.category" class="footer-item">分类: {{ item.category }}</span>
                  <span v-if="item.file_name" class="footer-item">📎 {{ item.file_name }}</span>
                  <span v-if="item.image_count > 0" class="footer-item">🖼 {{ item.image_count }}</span>
                  <button type="button" class="detail-btn" @click="onCardClick(item)">
                    查看详情 →
                  </button>
                </div>
              </template>
            </Card>
          </li>
        </ul>

        <!-- 分页器 (Phase 2-Impl-2B) -->
        <Pagination
          v-if="store.items.length > 0 && store.pageInfo.totalPages > 1"
          :info="store.pageInfo"
          :loading="store.loading"
          @page-change="onPageChange"
        />
      </div>
    </section>
  </div>
</template>

<style scoped>
.knowledge-view {
  display: flex;
  height: 100%;
  background: #020617;
  color: #e2e8f0;
}

.knowledge-view__sidebar {
  width: 240px;
  min-width: 240px;
  padding: 1.2rem 0.8rem;
  background: #0f172a;
  border-right: 1px solid #1e293b;
  overflow-y: auto;
}
.sidebar-section-title {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
  margin-bottom: 0.6rem;
  padding: 0 0.6rem;
}

.category-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}
.category-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 0.5rem 0.6rem;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 4px;
  color: #cbd5e1;
  font-size: 0.85rem;
  cursor: pointer;
  text-align: left;
  font-family: inherit;
  transition: background 0.12s;
}
.category-item:hover {
  background: rgba(148, 163, 184, 0.06);
}
.category-item.is-active {
  background: rgba(249, 115, 22, 0.12);
  color: #f97316;
  font-weight: 600;
}
.category-name {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.category-count {
  font-size: 0.7rem;
  color: #64748b;
  margin-left: 0.5rem;
}
.category-item.is-active .category-count {
  color: #f97316;
}

.knowledge-view__main {
  flex: 1;
  padding: 1.5rem 2rem;
  overflow-y: auto;
}

.knowledge-view__search {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}
.search-input {
  flex: 1;
  padding: 0.5rem 0.8rem;
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 4px;
  color: #f1f5f9;
  font-size: 0.9rem;
  font-family: inherit;
}
.search-input:focus {
  outline: none;
  border-color: #f97316;
}
.search-btn {
  padding: 0.5rem 0.9rem;
  background: transparent;
  border: 1px solid #475569;
  color: #94a3b8;
  border-radius: 4px;
  font-size: 0.85rem;
  cursor: pointer;
}
.search-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.list-meta {
  font-size: 0.8rem;
  color: #64748b;
  margin-bottom: 0.6rem;
}

.card-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
}
.card-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: #f1f5f9;
  flex: 1;
  cursor: pointer;
}
.card-title:hover {
  color: #f97316;
}

.status-pill {
  font-size: 0.7rem;
  padding: 0.15rem 0.5rem;
  border-radius: 3px;
  flex-shrink: 0;
}
.status-ok {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
}
.status-warn {
  background: rgba(251, 191, 36, 0.15);
  color: #fbbf24;
}
.status-error {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}
.status-mute {
  background: #334155;
  color: #94a3b8;
}

.card-snippet {
  margin: 0.5rem 0 0;
  font-size: 0.85rem;
  line-height: 1.4;
  color: #cbd5e1;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: pre-wrap;
}
.card-snippet.muted {
  color: #64748b;
  font-style: italic;
}

.tag-row {
  margin-top: 0.5rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}
.tag {
  font-size: 0.7rem;
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
}
.tag-h0 { background: #1e40af; color: #dbeafe; }
.tag-h1 { background: #5b21b6; color: #ede9fe; }
.tag-h2 { background: #9d174d; color: #fce7f3; }
.tag-h3 { background: #b45309; color: #fed7aa; }
.tag-h4 { background: #166534; color: #dcfce7; }
.tag-h5 { background: #475569; color: #f1f5f9; }

.card-footer {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  font-size: 0.75rem;
  color: #64748b;
}
.footer-item {
  white-space: nowrap;
}
.detail-btn {
  margin-left: auto;
  background: transparent;
  border: 0;
  color: #f97316;
  font-size: 0.8rem;
  cursor: pointer;
  font-family: inherit;
}
.detail-btn:hover {
  text-decoration: underline;
}
</style>
