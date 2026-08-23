<script setup lang="ts">
/**
 * 文献智能库 — 升级版：PDF导入 + 分析 + 相关度。
 */
import { onMounted, ref } from 'vue'
import { useKnowledgeStore } from '../../stores/research/knowledge.store'
import { literatureService } from '../../services/research/literature.service'
import CitationCard from '../../components/research/CitationCard.vue'
import StatusBadge from '../../components/research/StatusBadge.vue'

const store = useKnowledgeStore()
const isAnalyzing = ref(false)
const summary = ref('')

onMounted(async () => { await store.loadDocuments(); await store.loadAssessments() })

function selectDoc(id: string) { store.selectDocument(id); summary.value = '' }
function assessment(docId: string) { return store.assessments.find(a => a.documentId === docId) }

async function analyzePaper() {
  if (!store.selectedDocumentId) return
  isAnalyzing.value = true
  try { summary.value = await literatureService.summarizePaper(store.selectedDocumentId) }
  finally { isAnalyzing.value = false }
}
</script>

<template>
  <div class="literature">
    <aside class="literature__sidebar">
      <div class="literature__upload-area">
        <div class="literature__upload-icon">📄</div>
        <div class="literature__upload-text">上传科研论文</div>
        <div class="literature__upload-hint">支持 PDF / Word 格式</div>
      </div>
      <h3 class="literature__section-title">文献库 ({{ store.totalDocuments }})</h3>
      <input class="literature__search" type="text" placeholder="搜索文献…" :value="store.searchQuery" @input="store.setSearch(($event.target as HTMLInputElement).value)" />
      <div class="literature__folder" v-for="f in store.folders" :key="f.id">
        <span>📁</span> {{ f.name }} <span class="literature__count">{{ f.count }}</span>
      </div>
    </aside>

    <main class="literature__main">
      <template v-if="store.selectedDocument">
        <div class="literature__paper-header">
          <h2 class="literature__paper-title">{{ store.selectedDocument.title }}</h2>
          <div class="literature__paper-actions">
            <button class="literature__action-btn" @click="analyzePaper" :disabled="isAnalyzing">
              {{ isAnalyzing ? '分析中...' : '分析论文' }}
            </button>
            <button class="literature__action-btn secondary">提取证据</button>
          </div>
        </div>
        <div class="literature__paper-meta">{{ store.selectedDocument.authors }} · {{ store.selectedDocument.journal }}, {{ store.selectedDocument.year }}</div>
        <div class="literature__paper-tags">
          <span v-for="t in store.selectedDocument.tags" :key="t" class="literature__tag">{{ t }}</span>
        </div>

        <!-- 相关度 -->
        <div class="literature__relevance" v-if="store.selectedDocument.relevance">
          <span class="literature__relevance-label">相关度</span>
          <div class="literature__relevance-bar"><div class="literature__relevance-fill" :style="{ width: (store.selectedDocument.relevance * 100) + '%' }" /></div>
          <span class="literature__relevance-value">{{ (store.selectedDocument.relevance * 100).toFixed(0) }}%</span>
        </div>

        <!-- 可信度评分 -->
        <div class="literature__scores" v-if="assessment(store.selectedDocument.id)">
          <div class="literature__score-item" v-for="(label, key) in { reliability: '可靠性', evidence: '证据', methodology: '方法论' }" :key="key">
            <span class="literature__score-label">{{ label }}</span>
            <div class="literature__score-bar"><div class="literature__score-fill" :style="{ width: ((assessment(store.selectedDocument.id) as any)[key] * 100) + '%' }" /></div>
            <span class="literature__score-value">{{ ((assessment(store.selectedDocument.id) as any)[key] * 100).toFixed(0) }}%</span>
          </div>
        </div>

        <!-- AI 分析结果 -->
        <div v-if="summary" class="literature__summary">
          <h3>AI 文献分析</h3>
          <p>{{ summary }}</p>
        </div>

        <div v-if="assessment(store.selectedDocument.id)?.limitations?.length" class="literature__section">
          <h3>风险提示</h3>
          <div class="literature__risk" v-for="r in assessment(store.selectedDocument.id)!.limitations" :key="r">
            <StatusBadge status="warning" label="注意" /> {{ r }}
          </div>
        </div>
      </template>
      <template v-else>
        <div class="literature__empty">
          <div class="literature__empty-icon">📚</div>
          <div>选择左侧文献查看详情</div>
        </div>
      </template>
    </main>

    <aside class="literature__right">
      <h3 class="literature__section-title">全部文献 ({{ store.filteredDocuments.length }})</h3>
      <div class="literature__doc-card" v-for="d in store.filteredDocuments" :key="d.id"
           :class="{ 'literature__doc-card--active': store.selectedDocumentId === d.id }" @click="selectDoc(d.id)">
        <div class="literature__doc-title">{{ d.title }}</div>
        <div class="literature__doc-meta">{{ d.authors }} · {{ d.year }}</div>
        <div class="literature__doc-cred">相关度 {{ ((d.relevance ?? d.credibility) * 100).toFixed(0) }}%</div>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.literature { display: flex; height: 100%; }
.literature__sidebar { width: 220px; border-right: 1px solid #e5e7eb; padding: 16px; overflow-y: auto; background: #fafbfc; }
.literature__main { flex: 1; padding: 20px 28px; overflow-y: auto; }
.literature__right { width: 260px; border-left: 1px solid #e5e7eb; padding: 16px; overflow-y: auto; background: #fafbfc; }
.literature__upload-area { border: 2px dashed #d1d5db; border-radius: 8px; padding: 16px; text-align: center; margin-bottom: 16px; cursor: pointer; }
.literature__upload-area:hover { border-color: #3b82f6; background: #f0f9ff; }
.literature__upload-icon { font-size: 24px; margin-bottom: 4px; }
.literature__upload-text { font-size: 13px; font-weight: 500; color: #1e293b; }
.literature__upload-hint { font-size: 11px; color: #94a3b8; }
.literature__section-title { margin: 0 0 10px; font-size: 13px; font-weight: 600; color: #0f172a; }
.literature__search { width: 100%; padding: 8px 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 12px; margin-bottom: 12px; outline: none; }
.literature__folder { font-size: 13px; color: #475569; padding: 6px 8px; border-radius: 4px; cursor: pointer; display: flex; align-items: center; gap: 6px; }
.literature__folder:hover { background: #f1f5f9; }
.literature__count { color: #94a3b8; font-size: 11px; margin-left: auto; }
.literature__paper-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.literature__paper-title { margin: 0 0 6px; font-size: 18px; font-weight: 700; color: #0f172a; }
.literature__paper-actions { display: flex; gap: 8px; flex-shrink: 0; }
.literature__action-btn { padding: 8px 14px; border-radius: 6px; font-size: 12px; font-weight: 500; cursor: pointer; border: 1px solid #3b82f6; background: #3b82f6; color: #fff; }
.literature__action-btn:hover { background: #2563eb; }
.literature__action-btn.secondary { background: #fff; color: #3b82f6; }
.literature__action-btn:disabled { opacity: .5; cursor: not-allowed; }
.literature__paper-meta { font-size: 13px; color: #64748b; margin-bottom: 8px; }
.literature__paper-tags { display: flex; gap: 6px; margin-bottom: 12px; flex-wrap: wrap; }
.literature__tag { font-size: 12px; padding: 3px 10px; background: #eff6ff; color: #2563eb; border-radius: 4px; }
.literature__relevance { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
.literature__relevance-label { font-size: 13px; color: #64748b; min-width: 48px; }
.literature__relevance-bar { flex: 1; height: 8px; background: #f1f5f9; border-radius: 4px; overflow: hidden; max-width: 200px; }
.literature__relevance-fill { height: 100%; background: linear-gradient(90deg, #10b981, #34d399); border-radius: 4px; }
.literature__relevance-value { font-size: 13px; font-weight: 600; color: #10b981; }
.literature__scores { margin-bottom: 16px; }
.literature__score-item { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.literature__score-label { font-size: 13px; color: #64748b; min-width: 48px; }
.literature__score-bar { flex: 1; height: 8px; background: #f1f5f9; border-radius: 4px; overflow: hidden; max-width: 200px; }
.literature__score-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #60a5fa); border-radius: 4px; }
.literature__score-value { font-size: 13px; font-weight: 600; color: #3b82f6; }
.literature__summary { background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 8px; padding: 14px; margin-bottom: 16px; }
.literature__summary h3 { margin: 0 0 6px; font-size: 13px; }
.literature__summary p { margin: 0; font-size: 13px; color: #334155; line-height: 1.6; }
.literature__section { margin-bottom: 16px; }
.literature__section h3 { font-size: 14px; font-weight: 600; margin: 0 0 8px; }
.literature__risk { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #92400e; margin-bottom: 6px; }
.literature__empty { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; color: #94a3b8; font-size: 14px; gap: 8px; }
.literature__empty-icon { font-size: 32px; }
.literature__doc-card { padding: 10px 12px; border: 1px solid #e5e7eb; border-radius: 6px; margin-bottom: 6px; cursor: pointer; font-size: 12px; }
.literature__doc-card:hover { background: #f8fafc; }
.literature__doc-card--active { border-color: #3b82f6; background: #eff6ff; }
.literature__doc-title { font-weight: 500; color: #1e293b; margin-bottom: 2px; }
.literature__doc-meta { color: #94a3b8; }
.literature__doc-cred { color: #10b981; font-weight: 500; margin-top: 4px; }
</style>
