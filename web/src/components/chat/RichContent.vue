<script setup>
/**
 * RichContent.vue — 结构化富文本块分发器（含折叠 wrapper，方案 C Stage 4）
 *
 * 用法：
 *   <RichContent :block="richBlock" />
 *
 * 折叠行为：
 * - 2026-06-14 收官：默认**展开**（用户第一眼看到真实数据）
 *   - 旧版默认折叠，结果气泡正文是 LLM 废话 + 折叠区反而有真数据，顺序颠倒
 *   - LLM 主动 collapsed_by_default=true 时仍可折叠（留给长列表场景）
 * - 折叠态：显示 block.summary 字段（如果后端传了）或自动生成摘要（如「👥 成员 3 人（27→3）」）
 * - 点击展开：渲染真实 block 组件
 * - 11 个 block 组件不需修改（保留向后兼容，RichContent 在 wrapper 层做折叠）
 */
import { ref, computed } from 'vue'
import { resolveBlock } from './blocks/registry'

const props = defineProps({ block: { type: Object, required: true } })

const isExpanded = ref(true)  // 用户手动展开/折叠后保持；2026-06-14 收官：初始默认展开
const hasUserToggled = ref(false)

// 决定默认折叠还是展开
const shouldBeExpanded = computed(() => {
  if (hasUserToggled.value) return isExpanded.value
  // 2026-06-14 收官：默认展开（让用户第一眼看到真实数据）
  // LLM 主动 collapsed_by_default=true 时才折叠（留给长列表）
  if (props.block.collapsed_by_default === true) return false
  return true
})

const toggle = () => {
  isExpanded.value = !isExpanded.value
  hasUserToggled.value = true
}

// 自动生成 summary（当后端没传 block.summary）
const autoSummary = computed(() => {
  const b = props.block
  const data = b.data || {}
  switch (b.type) {
    case 'member': {
      const n = (data.members || []).length
      if (n === 0) return '👥 成员（无数据）'
      return `👥 成员 ${n} 人`
    }
    case 'knowledge_ref': {
      const n = (data.results || []).length
      return `📚 引用 ${n} 条知识`
    }
    case 'task_list': {
      const tasks = data.tasks || []
      const inProgress = tasks.filter((t) => t.status === 'in_progress').length
      const todo = tasks.filter((t) => t.status === 'todo').length
      return `📋 任务 ${tasks.length} 项（进行中 ${inProgress} · 待办 ${todo}）`
    }
    case 'meeting': {
      const meetings = data.meetings || data.groups?.[0]?.meetings || []
      return `📅 会议 ${meetings.length || 1} 场`
    }
    case 'formula':
      return `📐 公式 ${(data.formulas || []).length || 1} 个`
    case 'hypothesis':
      return `💡 假设 ${(data.items || []).length || 1} 个`
    case 'project':
      return `🎯 项目 ${data.name ? `「${data.name}」` : (data.projects || []).length + ' 个'}`
    case 'transcript':
      return `📝 会议转录`
    case 'chart':
      return `📊 图表「${data.title || '未命名'}」`
    case 'table': {
      const rows = (data.rows || []).length
      return `📊 表格 ${rows} 行`
    }
    case 'fallback':
      return '📦 其他数据'
    default:
      return b.title || `${b.type} 数据`
  }
})

const displaySummary = computed(() => props.block.summary || autoSummary.value)
</script>

<template>
  <div class="rich-content-wrapper" :class="`type-${block.type}`">
    <!-- 折叠态：summary 标题栏（始终显示，让用户点击展开） -->
    <button
      class="rich-summary"
      type="button"
      :aria-expanded="shouldBeExpanded"
      :aria-label="`${displaySummary}，点击${shouldBeExpanded ? '折叠' : '展开'}`"
      :title="displaySummary"
      @click="toggle"
    >
      <span class="rich-summary-text">{{ displaySummary }}</span>
      <span class="rich-summary-toggle">{{ shouldBeExpanded ? '▾ 折叠' : '▸ 展开' }}</span>
    </button>

    <!-- 真实 block 组件：用 v-show 而非 v-if 折叠，保留 DOM 存在性（向后兼容旧测试） -->
    <div class="rich-expanded" v-show="shouldBeExpanded">
      <component :is="resolveBlock(block.type)" :block="block" />
    </div>
  </div>
</template>

<style scoped>
.rich-content-wrapper {
  margin: 8px 0;
  border-radius: 8px;
  overflow: hidden;
}

.rich-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 10px 14px;
  background: var(--color-bg-page);
  border: 1px solid var(--color-border, #e4e7ed);
  border-radius: 8px;
  cursor: pointer;
  text-align: left;
  font-size: 13px;
  color: #303133;
  transition: background 0.2s, border-color 0.2s;
}

.rich-summary:hover {
  background: #ecf5ff;
  border-color: var(--color-primary, #FF7A5C);
}

.rich-summary-text {
  flex: 1;
  font-weight: 500;
}

.rich-summary-toggle {
  color: var(--color-info);
  font-size: 12px;
}

.rich-expanded {
  position: relative;
  background: white;
  border: 1px solid var(--color-border-light, #ebeef5);
  border-radius: 8px;
  padding: 8px;
}

.rich-collapse-btn {
  position: absolute;
  top: 6px;
  right: 6px;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid var(--color-border, #e4e7ed);
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 11px;
  color: #606266;
  cursor: pointer;
  z-index: 1;
}

.rich-collapse-btn:hover {
  background: var(--color-bg-page);
  color: var(--color-primary, #FF7A5C);
}
</style>
