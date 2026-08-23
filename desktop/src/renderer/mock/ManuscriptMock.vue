<template>
  <div class="manuscript-mock">
    <div class="outline-panel">
      <h3>大纲</h3>
      <div class="section-item" v-for="s in outline" :key="s.type"
           :class="{ active: activeSection === s.type }" @click="activeSection = s.type">
        <span class="section-icon">{{ sectionIcon(s.type) }}</span>
        {{ s.title }}
      </div>
      <h3>图表</h3>
      <div class="figure-item" v-for="f in figures" :key="f">📊 {{ f }}</div>
      <h3>参考文献</h3>
      <div class="ref-item" v-for="r in references" :key="r">[{{ r }}]</div>
    </div>
    <div class="content-panel">
      <h3>{{ currentSection?.title }}</h3>
      <div class="section-content">{{ currentSection?.content }}</div>
      <div class="language-review">
        <h4>SCI语言审查</h4>
        <div class="issue" v-for="i in issues" :key="i.desc" :class="i.severity">
          <span class="issue-icon">{{ i.severity === 'medium' ? '⚠' : '✓' }}</span>
          {{ i.desc }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const activeSection = ref('introduction')

const outline = [
  { type: 'introduction', title: '引言', content: '科学研究需要系统性调查来解决知识空白。O3微纳米气泡降解是一种有效的水处理技术...' },
  { type: 'methods', title: '材料与方法', content: '实验材料包括高纯度O3发生器、微纳米气泡发生器、紫外分光光度计...' },
  { type: 'results', title: '结果与讨论', content: '实验结果表明一级动力学模型最佳描述了O3降解过程 (R²=0.998)...' },
  { type: 'discussion', title: '讨论', content: '一级动力学模型提供了优异的拟合 (R²=0.998)，表明降解过程遵循浓度依赖行为...' },
  { type: 'conclusion', title: '结论', content: '本研究的主要贡献：1. 验证了一级动力学模型 2. 确定了最优气泡尺寸...' }
]

const currentSection = computed(() => outline.find(s => s.type === activeSection.value))

const figures = ['O3浓度-时间曲线', '模型拟合图', '粒径分布']
const references = ['Zhang 2024', 'Li 2023', 'Wang 2023']

const issues = [
  { severity: 'medium', desc: '过度表述: "proves" → 建议替换为 "suggests"' },
  { severity: 'low', desc: '无重复句子 ✓' },
  { severity: 'medium', desc: '结果部分缺少数据支持' }
]

function sectionIcon(type: string) {
  const icons: Record<string, string> = { introduction: '📖', methods: '🔬', results: '📊', discussion: '💬', conclusion: '✅' }
  return icons[type] || '📄'
}
</script>

<style scoped>
.manuscript-mock { display: flex; height: 100%; }
.outline-panel { width: 220px; border-right: 1px solid #e2e8f0; padding: 16px; overflow-y: auto; }
.content-panel { flex: 1; padding: 16px; overflow-y: auto; }
.section-item { display: flex; align-items: center; gap: 6px; padding: 8px; border-radius: 4px; margin-bottom: 4px; font-size: 13px; cursor: pointer; }
.section-item.active { background: #eff6ff; color: #2563eb; font-weight: 500; }
.section-icon { font-size: 14px; }
.figure-item, .ref-item { font-size: 12px; color: #64748b; margin-bottom: 4px; }
.section-content { font-size: 14px; line-height: 1.6; margin-bottom: 24px; }
.language-review { background: #fefce8; border: 1px solid #fde68a; border-radius: 8px; padding: 16px; }
.issue { font-size: 12px; margin-bottom: 6px; display: flex; align-items: center; gap: 6px; }
.issue.medium { color: #92400e; }
.issue.low { color: #166534; }
.issue-icon { font-size: 14px; }
h3 { font-size: 14px; font-weight: 600; margin-bottom: 8px; }
h4 { font-size: 13px; font-weight: 500; margin-bottom: 8px; }
</style>
