<script setup lang="ts">
/**
 * 论文助手 — 升级版：结构树 + 写作状态 + SCI审稿。
 */
import { onMounted, ref } from 'vue'
import { useManuscriptStore } from '../../stores/research/manuscript.store'
import { manuscriptService } from '../../services/research/manuscript.service'
import StatusBadge from '../../components/research/StatusBadge.vue'

const store = useManuscriptStore()
const isGenerating = ref(false)
const generatingSection = ref('')
onMounted(() => store.loadManuscript())

async function generateContent(sectionType: string) {
  if (!store.manuscript || isGenerating.value) return
  isGenerating.value = true
  generatingSection.value = sectionType
  try { await manuscriptService.generateSection(sectionType, store.manuscript.title) }
  finally { isGenerating.value = false; generatingSection.value = '' }
}

const reviewScores = [
  { label: '语言质量', score: 82, icon: '📝' },
  { label: '逻辑完整性', score: 78, icon: '🔗' },
  { label: '创新性', score: 85, icon: '💡' },
  { label: '文献覆盖', score: 75, icon: '📚' },
]
</script>

<template>
  <div class="manuscript">
    <!-- 左栏：结构树 -->
    <aside class="manuscript__outline">
      <h3>论文结构</h3>
      <div class="manuscript__section" v-for="s in store.sections" :key="s.sectionType"
           :class="{ 'manuscript__section--active': store.activeSection === s.sectionType }"
           @click="store.setActiveSection(s.sectionType)">
        <span class="manuscript__section-status">
          <StatusBadge status="success" label="✓" />
        </span>
        {{ s.title }}
      </div>
      <div class="manuscript__outline-stats">
        <div>{{ store.wordCount.toLocaleString() }} 字</div>
        <div>{{ store.issueCount }} 个问题</div>
      </div>
      <h3 style="margin-top: 16px;">高亮总结</h3>
      <div class="manuscript__highlight-item" v-for="(h, i) in store.highlights.slice(0, 3)" :key="i">{{ h }}</div>
    </aside>

    <!-- 中栏：正文 -->
    <main class="manuscript__editor">
      <div class="manuscript__editor-header" v-if="store.manuscript">
        <h2>{{ store.manuscript.title }}</h2>
        <div class="manuscript__wordcount">{{ store.wordCount.toLocaleString() }} 字</div>
      </div>
      <div class="manuscript__content">
        <div v-for="s in store.sections" :key="s.sectionType" v-show="store.activeSection === s.sectionType">
          <div class="manuscript__section-header">
            <h3>{{ s.title }}</h3>
            <button class="manuscript__gen-btn" @click="generateContent(s.sectionType)" :disabled="isGenerating">
              {{ generatingSection === s.sectionType ? '生成中...' : 'AI 生成' }}
            </button>
          </div>
          <p style="white-space: pre-line; line-height: 1.8; font-size: 14px; color: #334155;">{{ s.content }}</p>
          <div v-if="s.citations.length" class="manuscript__citations">
            引用: {{ s.citations.join(' ') }}
          </div>
        </div>
      </div>
    </main>

    <!-- 右栏：SCI审稿 -->
    <aside class="manuscript__reviewer">
      <h3>SCI 审稿面板</h3>
      <div class="manuscript__review-scores">
        <div class="manuscript__review-score" v-for="r in reviewScores" :key="r.label">
          <span class="manuscript__review-icon">{{ r.icon }}</span>
          <span class="manuscript__review-label">{{ r.label }}</span>
          <div class="manuscript__review-bar"><div class="manuscript__review-fill" :style="{ width: r.score + '%', background: r.score > 80 ? '#10b981' : r.score > 60 ? '#f59e0b' : '#ef4444' }" /></div>
          <span class="manuscript__review-val">{{ r.score }}%</span>
        </div>
      </div>
      <h3 style="margin-top: 12px;">待改进建议 ({{ store.issueCount }})</h3>
      <div class="manuscript__issue" v-for="(iss, i) in store.issues" :key="i">
        <StatusBadge :status="iss.severity === 'medium' ? 'warning' : 'info'" :label="iss.severity === 'medium' ? '⚠' : '💡'" />
        <span>{{ iss.description }}</span>
        <div class="manuscript__suggestion">→ {{ iss.suggestion }}</div>
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
.manuscript__section { display: flex; align-items: center; gap: 8px; padding: 7px 10px; border-radius: 6px; font-size: 13px; color: #475569; cursor: pointer; margin-bottom: 2px; }
.manuscript__section--active { background: #eff6ff; color: #2563eb; font-weight: 500; }
.manuscript__section-status :deep(.status-badge) { font-size: 9px; padding: 1px 4px; }
.manuscript__outline-stats { margin-top: 12px; font-size: 12px; color: #64748b; }
.manuscript__highlight-item { font-size: 11px; color: #64748b; padding: 4px 0; border-bottom: 1px solid #f1f5f9; }
.manuscript__editor-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.manuscript__editor-header h2 { margin: 0; font-size: 18px; font-weight: 700; color: #0f172a; }
.manuscript__wordcount { font-size: 12px; color: #94a3b8; }
.manuscript__section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.manuscript__section-header h3 { margin: 0; }
.manuscript__gen-btn { padding: 4px 10px; background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 4px; font-size: 11px; color: #2563eb; cursor: pointer; }
.manuscript__gen-btn:hover { background: #dbeafe; }
.manuscript__gen-btn:disabled { opacity: .5; cursor: not-allowed; }
.manuscript__citations { font-size: 11px; color: #64748b; margin-top: 8px; padding: 6px 10px; background: #f8fafc; border-radius: 4px; }
.manuscript__review-scores { display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
.manuscript__review-score { display: flex; align-items: center; gap: 6px; font-size: 12px; }
.manuscript__review-icon { font-size: 14px; }
.manuscript__review-label { min-width: 72px; color: #475569; }
.manuscript__review-bar { flex: 1; height: 6px; background: #f1f5f9; border-radius: 3px; overflow: hidden; }
.manuscript__review-fill { height: 100%; border-radius: 3px; }
.manuscript__review-val { min-width: 32px; text-align: right; font-weight: 600; color: #1e293b; }
.manuscript__issue { font-size: 12px; margin-bottom: 8px; padding: 8px 10px; background: #fffbeb; border-radius: 6px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.manuscript__suggestion { width: 100%; font-size: 11px; color: #64748b; margin-top: 2px; }
</style>
