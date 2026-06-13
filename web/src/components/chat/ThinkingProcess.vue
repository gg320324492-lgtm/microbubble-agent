<script setup>
/**
 * ThinkingProcess.vue — 工具调用 / 思考过程折叠组件（方案 C Stage 4 第二部分）
 *
 * 设计要点：
 * - 流式过程中（state==='streaming'）默认展开，让用户看到实时进度
 * - 流式完成（state==='idle' / 'aborted'）自动折叠为一行摘要
 * - 流式完成时折叠态显示：✓ 已分析意图：xxx · 调用 N 个工具 · 综合后输出（X.Xs · 评分 N/10）
 * - critique.score < 7 时显示 ⚠️ 徽章 + 完整 suggestion（用户能立即看到低分警告）
 * - 流中点击可手动折叠（不强制自动展开）
 * - 桌面 + 移动共用（不做样式差异，避免双套维护）
 *
 * 复用规则：
 * - 不修改 useChatStream.ts（纯渲染组件）
 * - 通过 props.msg 接收 useChatStream 处理后的 ChatMessage 对象
 */
import { ref, computed } from 'vue'

const props = defineProps({
  msg: {
    type: Object,
    required: true,
  },
})

// 用户可手动控制展开（即使流中）
const userExpanded = ref(false)
const userToggled = ref(false)  // 用户是否手动 toggle 过

const toggleExpanded = () => {
  userExpanded.value = !userExpanded.value
  userToggled.value = true
}

// 决定当前是否展开
const isExpanded = computed(() => {
  // 用户手动 toggle 后遵守用户选择
  if (userToggled.value) return userExpanded.value
  // 否则：流中默认展开，完成后折叠
  return props.msg.state === 'streaming'
})

// 折叠态摘要
const summary = computed(() => {
  const m = props.msg
  const toolCount = m.toolTrace?.filter((t) => t.type === 'tool').length || 0
  const intentLabel = m.intent?.category
    ? `意图：${intentZh(m.intent.category)}`
    : ''
  const critiqueScore = m.critique?.score
  const durationSec = m.durationMs ? (m.durationMs / 1000).toFixed(1) : null

  const parts = []
  if (intentLabel) parts.push(intentLabel)
  if (toolCount > 0) parts.push(`调用 ${toolCount} 个工具`)
  if (m.retryCount && m.retryCount > 0) parts.push(`重试 ${m.retryCount} 次`)
  if (durationSec) parts.push(`${durationSec}s`)
  if (critiqueScore != null) parts.push(`评分 ${critiqueScore}/10`)

  return parts.join(' · ') || '思考过程'
})

const hasLowCritique = computed(() => {
  return (props.msg.critique?.score ?? 10) < 7
})

const isAborted = computed(() => props.msg.state === 'aborted')

const intentZh = (cat) => ({
  recommend_person: '推荐人',
  search_info: '找资料',
  explain_concept: '解释概念',
  execute_action: '执行操作',
  data_query: '数据查询',
  casual_chat: '闲聊',
}[cat] || cat)

// 工具项格式化（用于展开态）
const toolItems = computed(() =>
  (props.msg.toolTrace || []).filter((t) => t.type === 'tool')
)
const thinkingItems = computed(() =>
  (props.msg.toolTrace || []).filter((t) => t.type === 'thinking')
)
const planItems = computed(() => props.msg.plan || [])

const formatLabel = (label) => label || ''
</script>

<template>
  <div class="thinking-process" :class="{ 'is-streaming': msg.state === 'streaming', 'is-aborted': isAborted }">
    <!-- 折叠态标题栏 -->
    <button
      class="thinking-header"
      :aria-expanded="isExpanded"
      :aria-label="`${summary}，点击${isExpanded ? '折叠' : '展开'}思考过程`"
      :title="summary"
      type="button"
      @click="toggleExpanded"
    >
      <span class="thinking-icon">
        <span v-if="isAborted">⏹</span>
        <span v-else-if="msg.state === 'streaming'">⏳</span>
        <span v-else>✓</span>
      </span>
      <span class="thinking-summary">{{ summary }}</span>
      <span v-if="hasLowCritique" class="critique-warning" aria-label="自评低分警告">⚠️</span>
      <span class="thinking-toggle">{{ isExpanded ? '▾' : '▸' }}</span>
    </button>

    <!-- 展开态：完整时间线 -->
    <div v-if="isExpanded" class="thinking-body">
      <!-- Intent -->
      <div v-if="msg.intent" class="thinking-section">
        <span class="section-label">🧠 意图</span>
        <span class="section-content">
          {{ intentZh(msg.intent.category) }}
          <small v-if="msg.intent.confidence" class="muted">
            ({{ (msg.intent.confidence * 100).toFixed(0) }}%)
          </small>
        </span>
      </div>

      <!-- Plan -->
      <div v-if="planItems.length" class="thinking-section">
        <span class="section-label">📋 计划</span>
        <ol class="plan-list">
          <li v-for="(p, i) in planItems" :key="i" :class="['plan-item', p.status]">
            {{ p.step }}
            <span v-if="p.tool" class="muted"> → {{ p.tool }}</span>
            <el-tag v-if="p.status === 'running'" size="small" type="warning">执行中</el-tag>
            <el-tag v-else-if="p.status === 'done'" size="small" type="success">完成</el-tag>
          </li>
        </ol>
      </div>

      <!-- Tools -->
      <div v-if="toolItems.length" class="thinking-section">
        <span class="section-label">🔧 工具 ({{ toolItems.length }})</span>
        <ul class="tool-list">
          <li v-for="(t, i) in toolItems" :key="i" :class="['tool-item', t.state]">
            <span class="tool-name">{{ t.name }}</span>
            <el-tag v-if="t.state === 'running'" size="small" type="warning">执行中...</el-tag>
            <el-tag v-else-if="t.state === 'done'" size="small" type="success">
              ✓ {{ t.duration_ms || 0 }}ms
            </el-tag>
            <div v-if="t.compression" class="tool-compression">
              <small class="muted">
                🗜️ 压缩：{{ t.compression.original_count }} → {{ t.compression.selected_count }}
               （{{ t.compression.summary }}）
              </small>
            </div>
          </li>
        </ul>
      </div>

      <!-- Critique -->
      <div v-if="msg.critique" class="thinking-section">
        <span class="section-label">📊 自评</span>
        <span :class="['critique-score', hasLowCritique ? 'low' : 'high']">
          {{ msg.critique.score }}/10
        </span>
        <span v-if="msg.critique.suggestion" class="critique-suggestion">
          {{ msg.critique.suggestion }}
        </span>
      </div>

      <!-- 折叠态的 thinking 项（合并展示） -->
      <div v-if="thinkingItems.length" class="thinking-section thinking-misc">
        <details v-for="(t, i) in thinkingItems" :key="i" class="misc-item">
          <summary>{{ formatLabel(t.label) }}</summary>
        </details>
      </div>

      <!-- 中断状态 -->
      <div v-if="isAborted" class="thinking-section aborted-banner">
        <span>⏹ 用户已中断生成</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.thinking-process {
  margin: 8px 0;
  border: 1px solid var(--color-border, #e4e7ed);
  border-radius: 8px;
  background: #fafbfc;
  font-size: 13px;
  overflow: hidden;
}

.thinking-process.is-streaming {
  border-color: var(--color-primary, #FF7A5C);
  background: #fff8f5;
}

.thinking-process.is-aborted {
  border-color: #f89898;
  background: #fff5f5;
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 12px;
  background: transparent;
  border: 0;
  cursor: pointer;
  font-size: 13px;
  color: #606266;
  text-align: left;
}

.thinking-header:hover {
  background: rgba(255, 122, 92, 0.05);
}

.thinking-icon {
  font-size: 14px;
}

.thinking-summary {
  flex: 1;
  color: #303133;
}

.critique-warning {
  font-size: 16px;
  color: #e6a23c;
}

.thinking-toggle {
  font-size: 12px;
  color: #909399;
  margin-left: auto;
}

.thinking-body {
  padding: 8px 12px 12px;
  border-top: 1px solid var(--color-border-light, #ebeef5);
}

.thinking-section {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 6px;
  font-size: 12px;
}

.section-label {
  color: #909399;
  min-width: 80px;
  flex-shrink: 0;
}

.section-content {
  color: #303133;
}

.muted {
  color: #909399;
}

.plan-list,
.tool-list {
  margin: 0;
  padding-left: 16px;
  flex: 1;
}

.plan-item,
.tool-item {
  margin: 2px 0;
  color: #303133;
}

.plan-item.running {
  color: var(--color-primary, #FF7A5C);
}

.critique-score {
  font-weight: 600;
  padding: 0 6px;
  border-radius: 4px;
}

.critique-score.high {
  color: #67c23a;
  background: #f0f9eb;
}

.critique-score.low {
  color: #f56c6c;
  background: #fef0f0;
}

.critique-suggestion {
  color: #606266;
  font-size: 12px;
  margin-left: 8px;
}

.tool-compression {
  margin-left: 8px;
}

.aborted-banner {
  color: #f56c6c;
  font-weight: 500;
}

.thinking-misc details {
  margin: 2px 0;
}

.thinking-misc summary {
  cursor: pointer;
  color: #606266;
  font-size: 12px;
}
</style>
