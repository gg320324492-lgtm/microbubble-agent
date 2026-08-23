<script setup lang="ts">
/**
 * 论文助手 — SCI 写作工作台。
 */
import StatusBadge from '../../components/research/StatusBadge.vue'
import CitationCard from '../../components/research/CitationCard.vue'

const sections = [
  { type: 'abstract', title: '摘要', icon: '📋' },
  { type: 'introduction', title: '1 引言', icon: '📖' },
  { type: 'methods', title: '2 材料与方法', icon: '🔬' },
  { type: 'results', title: '3 结果与讨论', icon: '📊' },
  { type: 'conclusion', title: '4 结论', icon: '✅' },
]
const activeSection = 'introduction'

const content = `四环素（TC）是一种广谱抗生素，广泛用于人类疾病治疗和动物养殖，其在水体中的残留会对生态环境和人类健康造成潜在风险[1-2]。传统处理技术（如活性污泥、生物膜等）对 TC 去除效果有限，难以满足日益严格的排放标准[3]。

臭氧微纳米气泡（O₃-MNBs）技术通过微纳米气泡的界面效应提高臭氧的利用效率，增强传质与反应速率；同时微纳米气泡具有较长的停留时间和较大的比表面积，可产生丰富的自由基和非自由基活性物种[4-6]。`

const issues = [
  { severity: 'medium' as const, desc: '文献中部分数据尚未进行重复性分析', icon: '⚠' },
  { severity: 'medium' as const, desc: '建议补充自然水体中基质效应讨论', icon: '⚠' },
  { severity: 'low' as const, desc: '参考文献中近三年文献占比偏低', icon: '💡' },
]

const citations = [
  { index: 1, authors: 'Zhang J., et al.', title: 'Impact of microbubble size on ozonation performance', journal: 'Sep. Purif. Technol., 246', year: 2020, tags: ['O₃-MNBs', 'TC'], citedBy: 71 },
  { index: 2, authors: 'Chen X., et al.', title: 'Synergistic effect of O₃-MNBs and biochar for TC removal', journal: 'Water Res., 229', year: 2023, tags: ['协同效应', '材料耦合'], citedBy: 18 },
]
</script>

<template>
  <div class="manuscript">
    <!-- 左栏：大纲 -->
    <aside class="manuscript__outline">
      <h3>论文大纲</h3>
      <div class="manuscript__section" v-for="s in sections" :key="s.type"
           :class="{ 'manuscript__section--active': activeSection === s.type }">
        <span>{{ s.icon }}</span> {{ s.title }}
      </div>
      <h3 style="margin-top: 16px;">图注 (6)</h3>
      <div class="manuscript__figure">📊 图1 TC 浓度随反应时间的变化曲线</div>
      <h3 style="margin-top: 16px;">参考文献 (48)</h3>
      <div class="manuscript__ref" v-for="i in 5" :key="i">[{{ i }}]</div>
    </aside>

    <!-- 中部：正文 -->
    <main class="manuscript__editor">
      <div class="manuscript__editor-header">
        <h2>论文草稿：臭氧微纳米气泡降解四环素的效率与机理研究</h2>
        <div class="manuscript__wordcount">字数：6,842</div>
      </div>
      <div class="manuscript__toolbar">
        <span>正文</span>
        <span class="manuscript__tb-sep">|</span>
        <span>B</span><span>I</span><span>U</span>
        <span class="manuscript__tb-sep">|</span>
        <span>📷</span><span>📊</span><span>📎</span>
      </div>
      <div class="manuscript__content" style="white-space: pre-line; line-height: 1.8;">{{ content }}</div>
    </main>

    <!-- 右栏：AI审稿 -->
    <aside class="manuscript__reviewer">
      <h3>AI 写作助手</h3>
      <StatusBadge status="warning" label="3 项待改进" />
      <div class="manuscript__issue" v-for="(iss, i) in issues" :key="i">
        <span>{{ iss.icon }}</span> {{ iss.desc }}
      </div>
      <h3 style="margin-top: 16px;">高亮总结</h3>
      <div class="manuscript__highlight">
        在最优条件下，O₃-MNBs 对 TC 的去除率高达 98.6%，主要活性物种为 ·OH 与 ¹O₂，降解过程以羟基化、脱甲基、开环反应为主，矿化率达 62.7%。
      </div>
      <h3 style="margin-top: 16px;">证据支持</h3>
      <CitationCard v-for="c in citations" :key="c.index" v-bind="c" style="margin-bottom: 8px;" />
    </aside>
  </div>
</template>

<style scoped>
.manuscript { display: flex; height: 100%; }
.manuscript__outline { width: 200px; border-right: 1px solid #e5e7eb; padding: 16px; overflow-y: auto; background: #fafbfc; }
.manuscript__editor { flex: 1; padding: 20px 28px; overflow-y: auto; display: flex; flex-direction: column; }
.manuscript__reviewer { width: 260px; border-left: 1px solid #e5e7eb; padding: 16px; overflow-y: auto; background: #fafbfc; }
.manuscript__outline h3 { margin: 0 0 8px; font-size: 13px; font-weight: 600; color: #0f172a; }
.manuscript__reviewer h3 { margin: 0 0 8px; font-size: 13px; font-weight: 600; color: #0f172a; }
.manuscript__section { display: flex; align-items: center; gap: 6px; padding: 7px 10px; border-radius: 6px; font-size: 13px; color: #475569; cursor: pointer; margin-bottom: 2px; }
.manuscript__section--active { background: #eff6ff; color: #2563eb; font-weight: 500; }
.manuscript__figure, .manuscript__ref { font-size: 12px; color: #64748b; margin-bottom: 4px; }
.manuscript__editor-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
.manuscript__editor-header h2 { margin: 0; font-size: 18px; font-weight: 700; color: #0f172a; }
.manuscript__wordcount { font-size: 12px; color: #94a3b8; white-space: nowrap; }
.manuscript__toolbar { display: flex; align-items: center; gap: 10px; padding: 8px 12px; background: #f8fafc; border: 1px solid #e5e7eb; border-radius: 8px; margin-bottom: 16px; font-size: 13px; color: #64748b; }
.manuscript__tb-sep { color: #e5e7eb; }
.manuscript__content { font-size: 14px; color: #334155; }
.manuscript__issue { display: flex; align-items: flex-start; gap: 6px; font-size: 12px; color: #92400e; margin-bottom: 8px; padding: 8px 10px; background: #fffbeb; border-radius: 6px; }
.manuscript__highlight { font-size: 12px; color: #166534; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 10px 12px; line-height: 1.6; }
</style>
