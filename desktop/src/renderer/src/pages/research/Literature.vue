<script setup lang="ts">
/**
 * 文献智能库 — 论文管理与可信度评分。
 */
import CitationCard from '../../components/research/CitationCard.vue'
import StatusBadge from '../../components/research/StatusBadge.vue'

const papers = [
  { id: 1, title: '臭氧微纳米气泡降解四环素的动力学与机理研究', authors: '李小红, 张伟, 陈晨', journal: '环境科学学报', year: 2021, stars: 4, reliability: 0.82, risks: ['统计方法不充分', '样本量偏小'], tags: ['O₃-MNBs', 'TC', '降解动力学'] },
  { id: 2, title: 'Nanobubble characterization methods and applications', authors: 'Li, X., et al.', journal: 'Ultrasonics', year: 2023, stars: 3, reliability: 0.65, risks: ['机制证据薄弱'], tags: ['纳米气泡', '表征'] },
  { id: 3, title: 'Ozone mass transfer in microbubble systems', authors: 'Wang, Y., et al.', journal: 'Water Research', year: 2023, stars: 5, reliability: 0.90, risks: [], tags: ['传质', '臭氧'] },
]

const selected = papers[0]
const folders = ['O₃-MNBs TC 降解研究', '臭氧-微纳米气泡基础', '催化与活化', '气泡表征与仪器', '跨学科参考']
</script>

<template>
  <div class="literature">
    <!-- 左侧文件夹 -->
    <aside class="literature__sidebar">
      <h3 class="literature__section-title">我的文献库</h3>
      <div class="literature__folder" v-for="f in folders" :key="f">
        <span>📁</span> {{ f }}
      </div>
      <h3 class="literature__section-title" style="margin-top: 16px;">文献类型</h3>
      <div class="literature__filter"><input type="checkbox" checked /> 期刊论文</div>
      <div class="literature__filter"><input type="checkbox" checked /> 会议论文</div>
      <div class="literature__filter"><input type="checkbox" /> 综述</div>
    </aside>

    <!-- 中部：论文详情 -->
    <main class="literature__main">
      <h2 class="literature__paper-title">{{ selected.title }}</h2>
      <div class="literature__paper-meta">{{ selected.authors }} · {{ selected.journal }}, {{ selected.year }}</div>
      <div class="literature__paper-tags">
        <span v-for="t in selected.tags" :key="t" class="literature__tag">{{ t }}</span>
      </div>

      <!-- 可信度评分 -->
      <div class="literature__scores">
        <div class="literature__score-item">
          <span class="literature__score-label">可靠性</span>
          <div class="literature__score-bar"><div class="literature__score-fill" :style="{ width: selected.reliability * 100 + '%' }" /></div>
          <span class="literature__score-value">{{ (selected.reliability * 100).toFixed(0) }}%</span>
        </div>
      </div>

      <!-- 摘要 -->
      <div class="literature__section">
        <h3>摘要</h3>
        <p>本研究系统考察了臭氧微纳米气泡（O₃-MNBs）体系对四环素（TC）的降解性能及其影响因素。结果表明：在 pH=7、O₃ 投加量 20 mg·L⁻¹、温度 25 ℃ 条件下，TC 在 60 min 内去除率可达 98.6%，降解过程符合准一级动力学模型。</p>
      </div>

      <!-- 风险提示 -->
      <div class="literature__section" v-if="selected.risks.length">
        <h3>风险提示</h3>
        <div class="literature__risk" v-for="r in selected.risks" :key="r">
          <StatusBadge status="warning" label="注意" /> {{ r }}
        </div>
      </div>
    </main>

    <!-- 右侧引用 -->
    <aside class="literature__right">
      <h3 class="literature__section-title">引用文献 (3)</h3>
      <CitationCard :index="1" authors="Li, X., et al." title="Activation mechanism of ozone microbubbles" journal="Chem. Eng. J., 430" :year="2022" :cited-by="36" style="margin-bottom: 8px;" />
      <CitationCard :index="2" authors="Wang, T., et al." title="Ozone micro/nano-bubbles enhanced degradation" journal="J.Hazard.Mater., 402" :year="2021" :cited-by="29" />
    </aside>
  </div>
</template>

<style scoped>
.literature { display: flex; height: 100%; }
.literature__sidebar { width: 220px; border-right: 1px solid #e5e7eb; padding: 16px; overflow-y: auto; background: #fafbfc; }
.literature__main { flex: 1; padding: 20px 28px; overflow-y: auto; }
.literature__right { width: 260px; border-left: 1px solid #e5e7eb; padding: 16px; overflow-y: auto; background: #fafbfc; }
.literature__section-title { margin: 0 0 10px; font-size: 13px; font-weight: 600; color: #0f172a; }
.literature__folder { font-size: 13px; color: #475569; padding: 6px 8px; border-radius: 4px; cursor: pointer; display: flex; align-items: center; gap: 6px; }
.literature__folder:hover { background: #f1f5f9; }
.literature__filter { font-size: 12px; color: #64748b; display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.literature__paper-title { margin: 0 0 6px; font-size: 18px; font-weight: 700; color: #0f172a; }
.literature__paper-meta { font-size: 13px; color: #64748b; margin-bottom: 8px; }
.literature__paper-tags { display: flex; gap: 6px; margin-bottom: 16px; flex-wrap: wrap; }
.literature__tag { font-size: 12px; padding: 3px 10px; background: #eff6ff; color: #2563eb; border-radius: 4px; }
.literature__scores { margin-bottom: 20px; }
.literature__score-item { display: flex; align-items: center; gap: 10px; }
.literature__score-label { font-size: 13px; color: #64748b; min-width: 48px; }
.literature__score-bar { flex: 1; height: 8px; background: #f1f5f9; border-radius: 4px; overflow: hidden; max-width: 200px; }
.literature__score-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #60a5fa); border-radius: 4px; }
.literature__score-value { font-size: 13px; font-weight: 600; color: #3b82f6; }
.literature__section { margin-bottom: 20px; }
.literature__section h3 { font-size: 14px; font-weight: 600; color: #0f172a; margin: 0 0 8px; }
.literature__section p { font-size: 13px; color: #475569; line-height: 1.7; margin: 0; }
.literature__risk { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #92400e; margin-bottom: 6px; }
</style>
