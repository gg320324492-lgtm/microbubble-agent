<script setup lang="ts">
/**
 * 论文助手 — Pinia store 驱动。
 */
import { onMounted } from 'vue'
import { useManuscriptStore } from '../../stores/research/manuscript.store'
import StatusBadge from '../../components/research/StatusBadge.vue'
import CitationCard from '../../components/research/CitationCard.vue'

const store = useManuscriptStore()
onMounted(() => store.loadManuscript())
</script>

<template>
  <div class="manuscript">
    <aside class="manuscript__outline">
      <h3>论文大纲</h3>
      <div class="manuscript__section" v-for="s in store.sections" :key="s.sectionType"
           :class="{ 'manuscript__section--active': store.activeSection === s.sectionType }"
           @click="store.setActiveSection(s.sectionType)">
        {{ s.title }}
      </div>
      <h3 style="margin-top: 16px;">高亮总结 ({{ store.highlights.length }})</h3>
      <div class="manuscript__highlight-item" v-for="(h, i) in store.highlights" :key="i">{{ h }}</div>
      <h3 style="margin-top: 16px;">写作问题 ({{ store.issueCount }})</h3>
      <StatusBadge v-for="(iss, i) in store.issues" :key="i"
                   :status="iss.severity === 'medium' ? 'warning' : 'info'"
                   :label="iss.description" style="margin-bottom: 4px;" />
    </aside>

    <main class="manuscript__editor">
      <div class="manuscript__editor-header" v-if="store.manuscript">
        <h2>{{ store.manuscript.title }}</h2>
        <div class="manuscript__wordcount">{{ store.wordCount.toLocaleString() }} 字</div>
      </div>
      <div class="manuscript__content">
        <div v-for="s in store.sections" :key="s.sectionType" v-show="store.activeSection === s.sectionType">
          <h3>{{ s.title }}</h3>
          <p style="white-space: pre-line; line-height: 1.8; font-size: 14px; color: #334155;">{{ s.content }}</p>
        </div>
      </div>
    </main>

    <aside class="manuscript__reviewer">
      <h3>AI 写作助手</h3>
      <StatusBadge :status="store.issueCount > 0 ? 'warning' : 'success'" :label="store.issueCount + ' 项待改进'" />
      <div class="manuscript__issue" v-for="(iss, i) in store.issues" :key="i">
        <span>{{ iss.severity === 'medium' ? '⚠' : '💡' }}</span> {{ iss.description }}
        <div class="manuscript__suggestion">建议: {{ iss.suggestion }}</div>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.manuscript { display: flex; height: 100%; }
.manuscript__outline { width: 200px; border-right: 1px solid #e5e7eb; padding: 16px; overflow-y: auto; background: #fafbfc; }
.manuscript__editor { flex: 1; padding: 20px 28px; overflow-y: auto; display: flex; flex-direction: column; }
.manuscript__reviewer { width: 260px; border-left: 1px solid #e5e7eb; padding: 16px; overflow-y: auto; background: #fafbfc; }
.manuscript__outline h3, .manuscript__reviewer h3 { margin: 0 0 8px; font-size: 13px; font-weight: 600; color: #0f172a; }
.manuscript__section { padding: 7px 10px; border-radius: 6px; font-size: 13px; color: #475569; cursor: pointer; margin-bottom: 2px; }
.manuscript__section--active { background: #eff6ff; color: #2563eb; font-weight: 500; }
.manuscript__highlight-item { font-size: 11px; color: #64748b; padding: 4px 0; border-bottom: 1px solid #f1f5f9; }
.manuscript__editor-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.manuscript__editor-header h2 { margin: 0; font-size: 18px; font-weight: 700; color: #0f172a; }
.manuscript__wordcount { font-size: 12px; color: #94a3b8; }
.manuscript__issue { font-size: 12px; color: #92400e; margin-bottom: 8px; padding: 8px 10px; background: #fffbeb; border-radius: 6px; }
.manuscript__suggestion { font-size: 11px; color: #64748b; margin-top: 4px; }
</style>
