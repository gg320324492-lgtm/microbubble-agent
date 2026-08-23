<script setup lang="ts">
/**
 * 文献智能库 — Pinia store 驱动。
 */
import { onMounted } from 'vue'
import { useKnowledgeStore } from '../../stores/research/knowledge.store'
import CitationCard from '../../components/research/CitationCard.vue'
import StatusBadge from '../../components/research/StatusBadge.vue'

const store = useKnowledgeStore()
onMounted(async () => {
  await store.loadDocuments()
  await store.loadAssessments()
})

function selectDoc(id: string) { store.selectDocument(id) }
function assessment(docId: string) { return store.assessments.find(a => a.documentId === docId) }
</script>

<template>
  <div class="literature">
    <aside class="literature__sidebar">
      <h3 class="literature__section-title">文献库 ({{ store.totalDocuments }})</h3>
      <input class="literature__search" type="text" placeholder="搜索文献…" :value="store.searchQuery" @input="store.setSearch(($event.target as HTMLInputElement).value)" />
      <div class="literature__folder" v-for="f in store.folders" :key="f.id">
        <span>📁</span> {{ f.name }} <span class="literature__count">{{ f.count }}</span>
      </div>
    </aside>

    <main class="literature__main">
      <template v-if="store.selectedDocument">
        <h2 class="literature__paper-title">{{ store.selectedDocument.title }}</h2>
        <div class="literature__paper-meta">{{ store.selectedDocument.authors }} · {{ store.selectedDocument.journal }}, {{ store.selectedDocument.year }}</div>
        <div class="literature__paper-tags">
          <span v-for="t in store.selectedDocument.tags" :key="t" class="literature__tag">{{ t }}</span>
        </div>
        <div class="literature__scores" v-if="assessment(store.selectedDocument.id)">
          <div class="literature__score-item" v-for="(label, key) in { reliability: '可靠性', evidence: '证据', methodology: '方法论' }" :key="key">
            <span class="literature__score-label">{{ label }}</span>
            <div class="literature__score-bar"><div class="literature__score-fill" :style="{ width: ((assessment(store.selectedDocument.id) as any)[key] * 100) + '%' }" /></div>
            <span class="literature__score-value">{{ ((assessment(store.selectedDocument.id) as any)[key] * 100).toFixed(0) }}%</span>
          </div>
        </div>
        <div v-if="assessment(store.selectedDocument.id)?.limitations?.length" class="literature__section">
          <h3>风险提示</h3>
          <div class="literature__risk" v-for="r in assessment(store.selectedDocument.id)!.limitations" :key="r">
            <StatusBadge status="warning" label="注意" /> {{ r }}
          </div>
        </div>
      </template>
      <template v-else>
        <div class="literature__empty">选择左侧文献查看详情</div>
      </template>
    </main>

    <aside class="literature__right">
      <h3 class="literature__section-title">全部文献 ({{ store.filteredDocuments.length }})</h3>
      <div class="literature__doc-card" v-for="d in store.filteredDocuments" :key="d.id"
           :class="{ 'literature__doc-card--active': store.selectedDocumentId === d.id }" @click="selectDoc(d.id)">
        <div class="literature__doc-title">{{ d.title }}</div>
        <div class="literature__doc-meta">{{ d.authors }} · {{ d.year }}</div>
        <div class="literature__doc-cred">可信度 {{ (d.credibility * 100).toFixed(0) }}%</div>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.literature { display: flex; height: 100%; }
.literature__sidebar { width: 220px; border-right: 1px solid #e5e7eb; padding: 16px; overflow-y: auto; background: #fafbfc; }
.literature__main { flex: 1; padding: 20px 28px; overflow-y: auto; }
.literature__right { width: 260px; border-left: 1px solid #e5e7eb; padding: 16px; overflow-y: auto; background: #fafbfc; }
.literature__section-title { margin: 0 0 10px; font-size: 13px; font-weight: 600; color: #0f172a; }
.literature__search { width: 100%; padding: 8px 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 12px; margin-bottom: 12px; outline: none; }
.literature__search:focus { border-color: #3b82f6; }
.literature__folder { font-size: 13px; color: #475569; padding: 6px 8px; border-radius: 4px; cursor: pointer; display: flex; align-items: center; gap: 6px; }
.literature__folder:hover { background: #f1f5f9; }
.literature__count { color: #94a3b8; font-size: 11px; margin-left: auto; }
.literature__paper-title { margin: 0 0 6px; font-size: 18px; font-weight: 700; color: #0f172a; }
.literature__paper-meta { font-size: 13px; color: #64748b; margin-bottom: 8px; }
.literature__paper-tags { display: flex; gap: 6px; margin-bottom: 16px; flex-wrap: wrap; }
.literature__tag { font-size: 12px; padding: 3px 10px; background: #eff6ff; color: #2563eb; border-radius: 4px; }
.literature__scores { margin-bottom: 20px; }
.literature__score-item { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.literature__score-label { font-size: 13px; color: #64748b; min-width: 48px; }
.literature__score-bar { flex: 1; height: 8px; background: #f1f5f9; border-radius: 4px; overflow: hidden; max-width: 200px; }
.literature__score-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #60a5fa); border-radius: 4px; }
.literature__score-value { font-size: 13px; font-weight: 600; color: #3b82f6; }
.literature__section { margin-bottom: 16px; }
.literature__section h3 { font-size: 14px; font-weight: 600; margin: 0 0 8px; }
.literature__risk { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #92400e; margin-bottom: 6px; }
.literature__empty { display: flex; align-items: center; justify-content: center; height: 100%; color: #94a3b8; font-size: 14px; }
.literature__doc-card { padding: 10px 12px; border: 1px solid #e5e7eb; border-radius: 6px; margin-bottom: 6px; cursor: pointer; font-size: 12px; }
.literature__doc-card:hover { background: #f8fafc; }
.literature__doc-card--active { border-color: #3b82f6; background: #eff6ff; }
.literature__doc-title { font-weight: 500; color: #1e293b; margin-bottom: 2px; }
.literature__doc-meta { color: #94a3b8; }
.literature__doc-cred { color: #10b981; font-weight: 500; margin-top: 4px; }
</style>
