<template>
  <div class="knowledge-extractions-panel">
    <div v-if="loading" class="panel-loading">
      <el-skeleton :rows="3" animated />
    </div>

    <div v-else>
      <!-- 统计条 -->
      <div class="extraction-stats">
        <el-tag
          v-for="(count, kind) in byKind"
          :key="kind"
          :type="kindTagType(kind)"
          effect="light"
          size="small"
        >
          {{ kindIcon(kind) }} {{ kindLabel(kind) }} {{ count }}
        </el-tag>
        <el-button v-if="showTrigger && total === 0" size="small" type="primary" plain :loading="triggering" @click="handleTrigger">
          <el-icon><Refresh /></el-icon> 触发提取
        </el-button>
      </div>

      <!-- 子 tab 切换 -->
      <el-tabs v-if="total > 0" v-model="activeKind" class="extraction-tabs">
        <el-tab-pane
          v-for="kind in visibleKinds"
          :key="kind"
          :name="kind"
          :label="`${kindLabel(kind)} (${byKind[kind] || 0})`"
          lazy
        >
          <div v-loading="loading" class="kind-list">
            <div
              v-for="item in kindItems(kind)"
              :key="item.id"
              class="extraction-card"
              @click="openDetail(item)"
            >
              <!-- 公式 -->
              <template v-if="item.kind === 'formula'">
                <div class="extraction-card-header">
                  <el-tag type="primary" size="small" effect="light">📐 公式</el-tag>
                  <span v-if="item.page_number" class="extraction-page">P{{ item.page_number }}</span>
                </div>
                <div class="formula-latex">$${{ (item.data && item.data.latex) || item.content_text || '' }}$$</div>
                <div v-if="item.data?.caption" class="extraction-caption">{{ item.data.caption }}</div>
              </template>

              <!-- 表格 -->
              <template v-else-if="item.kind === 'table'">
                <div class="extraction-card-header">
                  <el-tag type="success" size="small" effect="light">📊 表格</el-tag>
                  <span v-if="item.page_number" class="extraction-page">P{{ item.page_number }}</span>
                </div>
                <div v-if="item.data?.caption" class="extraction-caption">**{{ item.data.caption }}**</div>
                <div v-if="renderedTables[item.id]" class="extraction-table" v-html="renderedTables[item.id]"></div>
                <div v-else class="extraction-text">{{ truncate(item.content_text, 300) }}</div>
              </template>

              <!-- 图表 -->
              <template v-else-if="item.kind === 'chart'">
                <div class="extraction-card-header">
                  <el-tag type="warning" size="small" effect="light">📈 图表</el-tag>
                  <span v-if="item.page_number" class="extraction-page">P{{ item.page_number }}</span>
                </div>
                <div class="extraction-text">{{ (item.data && item.data.description) || item.content_text }}</div>
              </template>

              <!-- OCR 块 -->
              <template v-else>
                <div class="extraction-card-header">
                  <el-tag size="small" effect="light">📷 OCR</el-tag>
                  <span v-if="item.page_number" class="extraction-page">P{{ item.page_number }}</span>
                </div>
                <div class="extraction-text">{{ truncate(item.content_text, 300) }}</div>
              </template>

              <div class="extraction-card-footer">
                <span class="extraction-confidence">
                  置信度 {{ (item.confidence * 100).toFixed(0) }}%
                </span>
                <el-button text size="small" type="primary" @click.stop="copyContent(item)">
                  <el-icon><CopyDocument /></el-icon> 复制
                </el-button>
              </div>
            </div>
            <el-empty v-if="kindItems(kind).length === 0" :description="`暂无${kindLabel(kind)}`" :image-size="60" />
          </div>
        </el-tab-pane>
      </el-tabs>

      <el-empty
        v-else
        :description="emptyText"
        :image-size="80"
      />
    </div>

    <!-- 详情 dialog -->
    <el-dialog
      v-model="detailVisible"
      :title="detailTitle"
      width="70%"
      top="5vh"
    >
      <div v-if="currentItem" class="detail-content">
        <div class="detail-meta">
          <el-tag :type="kindTagType(currentItem.kind)" size="small">
            {{ kindLabel(currentItem.kind) }}
          </el-tag>
          <span v-if="currentItem.page_number">第 {{ currentItem.page_number }} 页</span>
          <span>置信度 {{ (currentItem.confidence * 100).toFixed(0) }}%</span>
          <span v-if="currentItem.model_used">模型：{{ currentItem.model_used }}</span>
        </div>
        <pre v-if="currentItem.kind === 'formula'" class="detail-pre">$$\n{{ (currentItem.data && currentItem.data.latex) || currentItem.content_text }}\n$$</pre>
        <pre v-else-if="currentItem.kind === 'table'" class="detail-pre">{{ currentItem.content_text }}</pre>
        <pre v-else class="detail-pre">{{ currentItem.content_text }}</pre>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { Refresh, CopyDocument } from '@element-plus/icons-vue'

const props = defineProps({
  knowledgeId: { type: Number, required: true },
  showTrigger: { type: Boolean, default: true },
  emptyText: { type: String, default: '该知识条目暂无提取内容（公式/表格/图表）' },
})

const extractions = ref([])
const loading = ref(false)
const triggering = ref(false)
const activeKind = ref('formula')
const renderedTables = ref({})

const byKind = computed(() => {
  const map = { formula: 0, table: 0, chart: 0, image_block: 0 }
  for (const e of extractions.value) {
    map[e.kind] = (map[e.kind] || 0) + 1
  }
  return map
})

const total = computed(() => extractions.value.length)

const visibleKinds = computed(() => {
  return Object.entries(byKind.value)
    .filter(([_, c]) => c > 0)
    .map(([k]) => k)
})

const detailVisible = ref(false)
const currentItem = ref(null)
const detailTitle = computed(() => currentItem.value ? `${kindLabel(currentItem.value.kind)}详情` : '')

const fetchExtractions = async () => {
  loading.value = true
  try {
    const { data } = await axios.get(`/api/v1/knowledge/${props.knowledgeId}/extractions`, {
      params: { page: 1, page_size: 200 },
    })
    extractions.value = data.items || []
    // 默认切到第一个有数据的 kind
    if (visibleKinds.value.length > 0 && !visibleKinds.value.includes(activeKind.value)) {
      activeKind.value = visibleKinds.value[0]
    }
    await nextTick()
    renderTables()
  } catch (e) {
    ElMessage.error('获取提取物失败')
    extractions.value = []
  } finally {
    loading.value = false
  }
}

const renderTables = () => {
  for (const e of extractions.value) {
    if (e.kind === 'table' && e.data) {
      const headers = e.data.headers || []
      const rows = e.data.rows || []
      if (headers.length === 0) continue
      const thead = '<thead><tr>' + headers.map((h) => `<th>${escapeHtml(h)}</th>`).join('') + '</tr></thead>'
      const tbody = '<tbody>' + rows.map((r) =>
        '<tr>' + r.map((c) => `<td>${escapeHtml(c)}</td>`).join('') + '</tr>'
      ).join('') + '</tbody>'
      renderedTables.value[e.id] = `<table>${thead}${tbody}</table>`
    }
  }
}

const escapeHtml = (s) => String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

const kindItems = (kind) => extractions.value.filter((e) => e.kind === kind)

const kindLabel = (kind) => ({ formula: '公式', table: '表格', chart: '图表', image_block: 'OCR 块' }[kind] || kind)
const kindIcon = (kind) => ({ formula: '📐', table: '📊', chart: '📈', image_block: '📷' }[kind] || '📄')
const kindTagType = (kind) => ({ formula: 'primary', table: 'success', chart: 'warning', image_block: 'info' }[kind] || '')

const truncate = (text, n) => {
  if (!text) return ''
  return text.length > n ? text.slice(0, n) + '…' : text
}

const openDetail = (item) => {
  currentItem.value = item
  detailVisible.value = true
}

const copyContent = async (item) => {
  const text = item.kind === 'formula'
    ? (item.data?.latex || item.content_text || '')
    : item.content_text || ''
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制')
  } catch {
    ElMessage.error('复制失败')
  }
}

const handleTrigger = async () => {
  triggering.value = true
  try {
    const { data } = await axios.post(`/api/v1/knowledge/${props.knowledgeId}/extract-multimodal`)
    if (data.ok) {
      const msg = data.skipped
        ? `未提取（${data.reason}）`
        : `提取完成：${data.images_total} 张图片`
      ElMessage.success(msg)
      await fetchExtractions()
    } else {
      ElMessage.warning(data.error || data.reason || '提取失败')
    }
  } catch (e) {
    ElMessage.error('触发提取失败')
  } finally {
    triggering.value = false
  }
}

watch(() => props.knowledgeId, () => fetchExtractions(), { immediate: true })
</script>

<style scoped>
.knowledge-extractions-panel {
  width: 100%;
}

.extraction-stats {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
  flex-wrap: wrap;
}

.extraction-tabs {
  margin-top: var(--space-2);
}

.kind-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-2) 0;
}

.extraction-card {
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  background: var(--color-bg-card);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}

.extraction-card:hover {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-sm);
}

.extraction-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-2);
}

.extraction-page {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.extraction-caption {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-2);
  font-style: italic;
}

.formula-latex {
  font-family: 'KaTeX_Main', 'Latin Modern Math', serif;
  font-size: 1.05em;
  padding: var(--space-2) 0;
  text-align: center;
  color: var(--color-text-primary);
  background: var(--color-bg-secondary);
  border-radius: var(--radius-sm);
  margin-bottom: var(--space-2);
}

.extraction-table {
  overflow-x: auto;
  margin-bottom: var(--space-2);
}

.extraction-table :deep(table) {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);
}

.extraction-table :deep(th),
.extraction-table :deep(td) {
  border: 1px solid var(--color-border);
  padding: var(--space-2);
  text-align: left;
}

.extraction-table :deep(th) {
  background: var(--color-bg-secondary);
  font-weight: 600;
}

.extraction-text {
  line-height: 1.6;
  color: var(--color-text-primary);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  background: var(--color-bg-secondary);
  padding: var(--space-2);
  border-radius: var(--radius-sm);
  font-family: var(--font-family-mono, 'Courier New', monospace);
  font-size: 12px;
  max-height: 200px;
  overflow-y: auto;
  margin-bottom: var(--space-2);
}

.extraction-card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px solid var(--color-border-light);
}

.extraction-confidence {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.detail-content {
  font-size: var(--font-size-sm);
}

.detail-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
  flex-wrap: wrap;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.detail-pre {
  background: var(--color-bg-secondary);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  font-family: var(--font-family-mono, 'Courier New', monospace);
  font-size: var(--font-size-sm);
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-height: 60vh;
  overflow-y: auto;
}
</style>
