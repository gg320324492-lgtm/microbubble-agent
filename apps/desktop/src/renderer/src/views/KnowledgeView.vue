<script setup lang="ts">
// 知识库页（UI1-3 原生还原）— 数据来自父级服务器（M2-3b），本页只做呈现。
//
// 信息架构对齐父级 web/src/views/KnowledgeView.vue：
//   工具栏（检索/分类筛选/导入/刷新） → 统计概要 chips（health-summary 对应物）
//   → 知识卡片列表（标题/分类/标签/日期/文档徽标） → 分页器（total > pageSize 时显示）
// 去除 web 专属元素：chat-selection banner（桌面无「对话选文档」场景）。
// 实体/假设 tab 依赖图谱端点 → 本单隐藏（见交付报告遗留）。
//
// 远程知识项**无文件大小字段**（父级契约不返回）→ 显示「文档」徽标而非「0 B」。
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { KnowledgeDocFull, KnowledgeDocMeta, KnowledgeSearchHit } from '@shared/types'
import KbGuide from '../components/knowledge/KbGuide.vue'

interface GateInfo {
  state: 'ready' | 'unbound' | 'offline' | 'expired'
  title: string
  hint: string
  canOpenSettings: boolean
  actionLabel?: string
}

const PAGE_SIZE = 20

const docs = ref<KnowledgeDocMeta[]>([])
const query = ref('')
const hits = ref<KnowledgeSearchHit[] | null>(null)
const searching = ref(false)
const loading = ref(false)
const selected = ref<KnowledgeDocFull | null>(null)
const editText = ref('')
const editTitle = ref('')
const editing = ref(false)
const saving = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

const gate = ref<GateInfo>({ state: 'ready', title: '', hint: '', canOpenSettings: false })
const blocked = computed(() => gate.value.state !== 'ready')

const page = ref(1)
const category = ref('')
const stats = ref<{ total: number; categories: Record<string, number>; entityTotal: number; hypothesisTotal: number } | null>(null)

interface KbCard {
  id: number
  title: string
  tags: string[]
  fileSize: number
  updatedAt: number
  snippet: string
  category: string
}

/** 卡片数据源：检索态走服务端命中，否则全量列表 */
const allItems = computed<KbCard[]>(() => {
  if (hits.value !== null) {
    const metaById = new Map(docs.value.map((d) => [d.id, d as KnowledgeDocMeta & { category?: string }]))
    return hits.value.map((h) => ({
      id: h.id,
      title: h.title,
      tags: h.tags,
      fileSize: metaById.get(h.id)?.fileSize ?? 0,
      updatedAt: h.updatedAt,
      snippet: h.snippet,
      category: metaById.get(h.id)?.category ?? ''
    }))
  }
  return docs.value.map((d) => {
    const meta = d as KnowledgeDocMeta & { category?: string }
    return { id: d.id, title: d.title, tags: d.tags, fileSize: d.fileSize, updatedAt: d.updatedAt, snippet: '', category: meta.category ?? '' }
  })
})

const filtered = computed<KbCard[]>(() =>
  category.value ? allItems.value.filter((d) => d.category === category.value) : allItems.value
)
const total = computed(() => filtered.value.length)
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
/** 分页器显示条件对齐父级：total > pageSize */
const showPager = computed(() => total.value > PAGE_SIZE)
const shown = computed<KbCard[]>(() => filtered.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE))

const categoryOptions = computed<string[]>(() => {
  const fromStats = stats.value ? Object.keys(stats.value.categories) : []
  const fromDocs = allItems.value.map((d) => d.category).filter(Boolean)
  return [...new Set([...fromStats, ...fromDocs])].sort()
})

function fmtDate(ms: number): string {
  if (!ms) return ''
  const d = new Date(ms)
  const pad = (n: number): string => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

async function loadGate(): Promise<void> {
  try {
    gate.value = (await window.api.knowledge.sourceState()) as GateInfo
  } catch {
    gate.value = { state: 'ready', title: '', hint: '', canOpenSettings: false }
  }
}

async function loadAll(): Promise<void> {
  if (blocked.value) return
  loading.value = true
  try {
    docs.value = await window.api.knowledge.list()
    page.value = 1
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadStats(): Promise<void> {
  if (blocked.value) return
  try {
    stats.value = (await window.api.knowledge.stats()) as typeof stats.value
  } catch {
    stats.value = null // 统计失败不阻塞页面
  }
}

/** 检索：回车触发**服务端语义检索**（本地 bigram 不适用于远程模式） */
async function doSearch(): Promise<void> {
  const q = query.value.trim()
  if (!q) {
    hits.value = null
    page.value = 1
    return
  }
  searching.value = true
  try {
    hits.value = await window.api.knowledge.search(q)
    page.value = 1
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '检索失败')
  } finally {
    searching.value = false
  }
}

function clearSearch(): void {
  query.value = ''
  hits.value = null
  page.value = 1
}

function pickCategory(c: string): void {
  category.value = category.value === c ? '' : c
  page.value = 1
}

async function openDoc(id: number): Promise<void> {
  try {
    selected.value = await window.api.knowledge.get(id)
    editTitle.value = selected.value?.title ?? ''
    editText.value = selected.value?.content ?? ''
    editing.value = false
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '打开失败')
  }
}

function backToList(): void {
  selected.value = null
  editing.value = false
}

async function saveEdit(): Promise<void> {
  if (!selected.value) return
  saving.value = true
  try {
    const updated = await window.api.knowledge.update(selected.value.id, { title: editTitle.value, content: editText.value })
    if (updated) selected.value = updated
    editing.value = false
    await loadAll()
    ElMessage.success('已保存')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    saving.value = false
  }
}

async function removeDoc(id: number): Promise<void> {
  try {
    await ElMessageBox.confirm('确定删除这条知识？', '删除确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await window.api.knowledge.delete(id)
    backToList()
    await loadAll()
    await loadStats()
    ElMessage.success('已删除')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '删除失败')
  }
}

function triggerImport(): void {
  fileInput.value?.click()
}

async function onFilesPicked(ev: Event): Promise<void> {
  const input = ev.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  if (!files.length) return
  try {
    const payload = await Promise.all(files.map(async (f) => ({ name: f.name, content: await f.text() })))
    const res = await window.api.knowledge.import(payload)
    if (res.imported.length) ElMessage.success(`已导入 ${res.imported.length} 个文档`)
    for (const s of res.skipped) ElMessage.warning(`${s.name}：${s.reason}`)
    await loadAll()
    await loadStats()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '导入失败')
  } finally {
    input.value = ''
  }
}

function openSettings(): void {
  location.hash = '/app/settings'
}

onMounted(async () => {
  await loadGate()
  if (blocked.value) return
  await loadAll()
  await loadStats()
})
</script>

<template>
  <div class="kb">
    <!-- 引导态（独立组件；文案来自主进程集中状态机，零硬编码） -->
    <KbGuide v-if="blocked" :gate="gate" feature="知识库" @open-settings="openSettings" @retry="loadAll" />

    <template v-else>
      <!-- ===== 详情 / 编辑态 ===== -->
      <section v-if="selected" class="kb-detail card" data-testid="kb-detail">
        <header class="kb-detail-head">
          <button class="ghost-btn" data-testid="kb-back" @click="backToList">← 返回列表</button>
          <input v-if="editing" v-model="editTitle" class="kb-title-input" data-testid="kb-edit-title" />
          <h2 v-else class="kb-detail-title">{{ selected.title }}</h2>
          <div class="kb-detail-actions">
            <template v-if="editing">
              <button class="btn-primary" :disabled="saving" data-testid="kb-save" @click="saveEdit">
                {{ saving ? '保存中…' : '保存' }}
              </button>
              <button class="ghost-btn" @click="editing = false">取消</button>
            </template>
            <template v-else>
              <button class="mini-btn" data-testid="kb-edit" @click="editing = true">编辑</button>
              <button class="mini-btn danger" data-testid="kb-delete" @click="removeDoc(selected.id)">删除</button>
            </template>
          </div>
        </header>
        <p class="kb-detail-meta">
          {{ fmtDate(selected.updatedAt) }}<span class="kb-badge" data-testid="kb-detail-badge">文档</span>
        </p>
        <textarea v-if="editing" v-model="editText" class="kb-editor" data-testid="kb-edit-content"></textarea>
        <pre v-else class="kb-content">{{ selected.content }}</pre>
      </section>

      <!-- ===== 列表态 ===== -->
      <template v-else>
        <header class="kb-head">
          <h1 class="kb-title">知识库</h1>
          <div class="kb-actions">
            <button class="btn-primary" data-testid="kb-import" :disabled="loading" @click="triggerImport">导入文档</button>
            <button class="ghost-btn" data-testid="kb-refresh" @click="loadAll">刷新</button>
            <input ref="fileInput" type="file" accept=".md,.txt,.markdown" multiple hidden @change="onFilesPicked" />
          </div>
        </header>

        <!-- 工具栏：检索 + 分类筛选 -->
        <div class="kb-toolbar">
          <div class="kb-search">
            <input
              v-model="query"
              data-testid="kb-search-input"
              placeholder="检索知识（回车，走服务端语义检索）"
              @keyup.enter="doSearch"
            />
            <button class="ghost-btn" data-testid="kb-search-btn" :disabled="searching" @click="doSearch">
              {{ searching ? '检索中…' : '检索' }}
            </button>
            <button v-if="hits !== null" class="ghost-btn" data-testid="kb-search-clear" @click="clearSearch">清除</button>
          </div>
          <div v-if="categoryOptions.length" class="kb-chips" data-testid="kb-category-chips">
            <button
              v-for="c in categoryOptions"
              :key="c"
              class="kb-chip"
              :class="{ 'is-active': category === c }"
              :data-testid="`kb-cat-${c}`"
              @click="pickCategory(c)"
            >
              {{ c }}
            </button>
          </div>
        </div>

        <!-- 统计概要（对齐父级 health-summary） -->
        <div v-if="stats" class="kb-summary" data-testid="kb-summary">
          <span class="kb-stat" data-testid="kb-stat-knowledge">📚 知识 {{ stats.total }}</span>
          <span class="kb-stat">🔗 实体 {{ stats.entityTotal }}</span>
          <span class="kb-stat">🧪 假设 {{ stats.hypothesisTotal }}</span>
          <span class="kb-stat">📁 分类 {{ categoryOptions.length }}</span>
        </div>

        <p v-if="loading" class="kb-hint">加载中…</p>

        <!-- 卡片列表 -->
        <p v-else-if="shown.length === 0" class="kb-hint" data-testid="kb-empty">
          <template v-if="hits !== null">没有找到与「{{ query }}」相关的文档。</template>
          <template v-else>知识库还是空的，点「导入文档」添加 Markdown / 文本。</template>
        </p>
        <ul v-else class="kb-list" data-testid="kb-list">
          <li v-for="d in shown" :key="d.id" class="kb-item card" :data-testid="`kb-item-${d.id}`">
            <button class="kb-item-main" @click="openDoc(d.id)">
              <span class="kb-item-title">{{ d.title }}</span>
              <span v-if="d.snippet" class="kb-item-snippet">{{ d.snippet }}</span>
            </button>
            <div class="kb-item-meta">
              <span v-if="d.category" class="kb-cat">{{ d.category }}</span>
              <span v-for="t in d.tags" :key="t" class="kb-tag">{{ t }}</span>
              <span class="kb-date">{{ fmtDate(d.updatedAt) }}</span>
              <!-- 远程知识项无字节大小 → 文档徽标（不显示「0 B」） -->
              <span class="kb-badge" data-testid="kb-badge">文档</span>
            </div>
          </li>
        </ul>

        <!-- 分页器（total > pageSize 时显示，对齐父级） -->
        <div v-if="showPager" class="kb-pager" data-testid="kb-pager">
          <span class="kb-pager-total" data-testid="kb-pager-total">共 {{ total }} 条</span>
          <button class="mini-btn" data-testid="kb-pager-prev" :disabled="page <= 1" @click="page -= 1">上一页</button>
          <span class="kb-pager-page" data-testid="kb-pager-page">{{ page }} / {{ pageCount }}</span>
          <button class="mini-btn" data-testid="kb-pager-next" :disabled="page >= pageCount" @click="page += 1">下一页</button>
        </div>
      </template>
    </template>
  </div>
</template>

<style scoped>
.kb {
  padding: var(--space-4);
  height: 100%;
  overflow-y: auto;
}
.kb-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}
.kb-title {
  margin: 0;
  font-size: var(--font-size-xl);
}
.kb-actions {
  display: flex;
  gap: var(--space-2);
}
.kb-toolbar {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}
.kb-search {
  display: flex;
  gap: var(--space-2);
}
.kb-search input {
  flex: 1;
}
.kb-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}
.kb-chip {
  padding: 2px 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  background: transparent;
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  cursor: pointer;
}
.kb-chip.is-active {
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.kb-summary {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  padding: var(--space-2) 0;
  margin-bottom: var(--space-3);
  border-bottom: 1px solid var(--color-border);
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}
.kb-hint {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}
.kb-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.kb-item {
  padding: var(--space-3);
}
.kb-item-main {
  display: block;
  width: 100%;
  text-align: left;
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0;
}
.kb-item-title {
  display: block;
  font-size: var(--font-size-md);
  color: var(--color-text-primary);
  margin-bottom: 4px;
}
.kb-item-snippet {
  display: block;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.kb-item-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-2);
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}
.kb-cat {
  color: var(--color-primary);
}
.kb-tag {
  padding: 0 6px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}
.kb-badge {
  padding: 0 6px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
}
.kb-pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-4) 0;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}
.kb-detail {
  padding: var(--space-4);
}
.kb-detail-head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
}
.kb-detail-title {
  margin: 0;
  flex: 1;
  font-size: var(--font-size-lg);
}
.kb-title-input {
  flex: 1;
}
.kb-detail-actions {
  display: flex;
  gap: var(--space-2);
}
.kb-detail-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-3);
}
.kb-content {
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: var(--font-size-sm);
  line-height: 1.8;
  color: var(--color-text-primary);
  margin: 0;
}
.kb-editor {
  width: 100%;
  min-height: 320px;
  font-family: inherit;
  font-size: var(--font-size-sm);
  line-height: 1.8;
}
</style>
