<script setup lang="ts">
/**
 * AI科研助手 — 三栏工作台布局。
 * 左：任务历史 | 中：AI推理 | 右：证据与引用
 */
import CitationCard from '../../components/research/CitationCard.vue'
import EvidenceCard from '../../components/research/EvidenceCard.vue'
import StatusBadge from '../../components/research/StatusBadge.vue'

const sessions = [
  { id: 1, name: '分析降解动力学', active: true },
  { id: 2, name: '文献综述整理', active: false },
  { id: 3, name: '实验变量优化', active: false },
]

const messages = [
  { role: 'user' as const, content: '请分析这组臭氧微纳米气泡在降解四环素（TC）的实验数据，包括动力学拟合、机理讨论和关键影响因素，并给出结论。', time: '16:22' },
  { role: 'assistant' as const, content: '好的，我已经对实验数据和相关文献进行了综合分析，结果如下：', time: '16:22' },
  { role: 'assistant' as const, content: '1. 文献检索与证据汇总\n基于关键词检索到 128 篇相关文献，筛选出与臭氧微纳米气泡（O₃-MNBs）降解四环素机制、动力学及影响因素强相关的 12 篇核心文献。', time: '16:22', toolCall: { name: '文献检索', result: '筛选 12 篇核心文献' } },
  { role: 'assistant' as const, content: '2. 动力学拟合结果\n最佳拟合模型：伪一级动力学模型\nkobs = 0.0243 min⁻¹\nR² = 0.9887\n半衰期 t₁/₂ = 28.5 min', time: '16:22', toolCall: { name: '动力学拟合', result: '一级动力学 R²=0.9887' } },
  { role: 'assistant' as const, content: '3. 机理与结论\n主要活性物种：·OH（占主导），其次为 ¹O₂ 等。\n最优条件预测：粒径 ~150nm，臭氧 20 mg/L，pH 7，温度 25°C，可获得 >95% TC 去除率。', time: '16:22' },
]

const citations = [
  { index: 1, authors: 'Li, X., et al.', title: 'Ozonation with micro-nano bubbles for tetracycline degradation', journal: 'Chemosphere, 286', year: 2022, tags: ['O₃-MNBs', 'TC', '动力学'], citedBy: 128 },
  { index: 2, authors: 'Wang, Y., et al.', title: 'Degradation mechanism of tetracycline by ozone microbubble', journal: 'Water Research, 188', year: 2021, tags: ['机制', 'ROS'], citedBy: 86 },
]

const evidence = [
  { label: 'kLa 测量', value: '0.45 min⁻¹', source: 'Li 2022', confidence: 0.85 },
  { label: 'R² 拟合度', value: '0.9887', source: '实验数据', confidence: 0.95 },
]
</script>

<template>
  <div class="assistant">
    <!-- 左栏：任务历史 -->
    <aside class="assistant__left">
      <h3 class="assistant__section-title">研究会话</h3>
      <div class="assistant__session" v-for="s in sessions" :key="s.id" :class="{ 'assistant__session--active': s.active }">
        <StatusBadge :status="s.active ? 'info' : 'neutral'" :label="s.active ? '当前' : ''" />
        <span>{{ s.name }}</span>
      </div>
    </aside>

    <!-- 中栏：AI推理 -->
    <main class="assistant__center">
      <div class="assistant__messages">
        <div v-for="(msg, i) in messages" :key="i" :class="['assistant__msg', `assistant__msg--${msg.role}`]">
          <div class="assistant__msg-role">{{ msg.role === 'user' ? '你' : 'MB-Researcher Pro' }} <span class="assistant__msg-time">{{ msg.time }}</span></div>
          <div class="assistant__msg-content" style="white-space: pre-line">{{ msg.content }}</div>
          <div v-if="msg.toolCall" class="assistant__tool">
            <span class="assistant__tool-icon">⚙️</span>
            <span>调用: {{ msg.toolCall.name }}</span>
            <StatusBadge status="success" label="完成" />
          </div>
        </div>
      </div>
      <div class="assistant__input">
        <input type="text" placeholder="输入你的问题，支持 @引用 / 数据 / 知识库 …" />
        <button class="assistant__send">运行</button>
      </div>
    </main>

    <!-- 右栏：证据与引用 -->
    <aside class="assistant__right">
      <h3 class="assistant__section-title">引用文献 ({{ citations.length }})</h3>
      <CitationCard v-for="c in citations" :key="c.index" v-bind="c" style="margin-bottom: 8px;" />
      <h3 class="assistant__section-title" style="margin-top: 16px;">证据</h3>
      <EvidenceCard v-for="e in evidence" :key="e.label" v-bind="e" style="margin-bottom: 8px;" />
    </aside>
  </div>
</template>

<style scoped>
.assistant { display: flex; height: 100%; }
.assistant__left { width: 220px; border-right: 1px solid #e5e7eb; padding: 16px; overflow-y: auto; background: #fafbfc; }
.assistant__center { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.assistant__right { width: 280px; border-left: 1px solid #e5e7eb; padding: 16px; overflow-y: auto; background: #fafbfc; }
.assistant__section-title { margin: 0 0 10px; font-size: 13px; font-weight: 600; color: #0f172a; }
.assistant__session { padding: 8px 10px; border-radius: 6px; font-size: 13px; color: #475569; cursor: pointer; display: flex; align-items: center; gap: 6px; margin-bottom: 2px; }
.assistant__session--active { background: #eff6ff; color: #2563eb; font-weight: 500; }
.assistant__messages { flex: 1; overflow-y: auto; padding: 20px 24px; }
.assistant__msg { margin-bottom: 16px; }
.assistant__msg--user .assistant__msg-content { background: #f1f5f9; border-radius: 10px; padding: 12px 16px; font-size: 13px; line-height: 1.6; color: #1e293b; }
.assistant__msg--assistant .assistant__msg-content { font-size: 13px; line-height: 1.7; color: #334155; }
.assistant__msg-role { font-size: 12px; font-weight: 600; color: #64748b; margin-bottom: 4px; }
.assistant__msg-time { font-weight: 400; color: #94a3b8; }
.assistant__tool { margin-top: 6px; display: inline-flex; align-items: center; gap: 6px; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; padding: 4px 10px; font-size: 12px; color: #166534; }
.assistant__tool-icon { font-size: 12px; }
.assistant__input { padding: 12px 24px 16px; border-top: 1px solid #e5e7eb; display: flex; gap: 10px; }
.assistant__input input { flex: 1; border: 1px solid #d1d5db; border-radius: 8px; padding: 10px 14px; font-size: 13px; outline: none; }
.assistant__input input:focus { border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,.15); }
.assistant__send { background: #2563eb; color: #fff; border: none; border-radius: 8px; padding: 10px 20px; font-size: 13px; font-weight: 500; cursor: pointer; }
.assistant__send:hover { background: #1d4ed8; }
</style>
