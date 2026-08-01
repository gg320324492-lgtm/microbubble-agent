<!--
  ToolTraceItem.vue — W100 +21 工具调用结果可点展开

  折叠态：🔧 name ✓ 12ms [可选 preview]
  展开态：完整 tool_output（JSON 美化）+ 复制按钮
  a11y: role="button" + aria-expanded + keyboard (Enter/Space) + 44px tap target
-->
<template>
  <!-- thinking 类型不可展开，直接渲染 -->
  <div
    v-if="trace.type === 'thinking'"
    class="tti-thinking"
    :class="[`stagger-${Math.min(index + 1, 6)}`]"
    :data-testid="`tti-${index}-thinking`"
  >
    {{ trace.label }}
  </div>

  <!-- tool 类型：可点击展开 -->
  <div
    v-else
    class="tti-tool"
    :class="[
      trace.state,
      { 'tti-expanded': expanded },
      `stagger-${Math.min(index + 1, 6)}`,
    ]"
    :data-testid="`tti-${index}-tool`"
    :data-state="trace.state || 'done'"
  >
    <div
      class="tti-row"
      role="button"
      tabindex="0"
      :aria-expanded="expanded ? 'true' : 'false'"
      :aria-controls="detailId"
      :aria-label="`展开工具调用详情：${trace.name}`"
      @click="toggle"
      @keydown.enter.prevent="toggle"
      @keydown.space.prevent="toggle"
    >
      <span v-if="trace.state === 'running'" class="tti-spinner" aria-hidden="true" />
      <span v-else class="tti-check" aria-hidden="true">🔧</span>
      <span class="tti-name">{{ trace.name }}</span>
      <span v-if="trace.state !== 'running'" class="tti-tick">✓</span>
      <span v-if="trace.duration_ms" class="tti-duration">{{ trace.duration_ms }}ms</span>
      <span class="tti-toggle" aria-hidden="true">{{ expanded ? '▾' : '▸' }}</span>
    </div>

    <!-- 折叠态单行预览（如果有 output） -->
    <div
      v-if="!expanded && trace.tool_output_preview"
      class="tti-preview"
      :data-testid="`tti-${index}-preview`"
    >
      {{ trace.tool_output_preview }}
    </div>

    <!-- 压缩信息徽章（来自 tool_compressed 事件） -->
    <div
      v-if="trace.compression"
      class="tti-compression"
      :data-testid="`tti-${index}-compression`"
    >
      🗜️ {{ trace.compression.summary || `压缩：${trace.compression.original_count} → ${trace.compression.selected_count} 条` }}
    </div>

    <!-- 展开态：完整 JSON + 复制按钮 -->
    <Transition name="tti-detail">
      <div
        v-if="expanded"
        :id="detailId"
        class="tti-detail"
        :data-testid="`tti-${index}-detail`"
        role="region"
        :aria-label="`${trace.name} 调用结果`"
      >
        <div class="tti-detail-header">
          <span class="tti-detail-label">完整输出</span>
          <button
            v-if="hasOutput"
            type="button"
            class="tti-copy"
            :data-testid="`tti-${index}-copy`"
            :aria-label="copyLabel"
            @click.stop="copyOutput"
          >
            {{ copied ? '✓ 已复制' : '📋 复制' }}
          </button>
        </div>
        <pre v-if="hasOutput" class="tti-json"><code>{{ prettyJson }}</code></pre>
        <div v-else class="tti-empty" :data-testid="`tti-${index}-empty`">
          （该工具调用没有返回可展示的 output）
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

interface TraceItem {
  type: 'thinking' | 'tool'
  label?: string
  name?: string
  state?: 'running' | 'done'
  duration_ms?: number
  tool_output?: Record<string, any>
  tool_output_preview?: string
  compression?: {
    original_count: number
    selected_count: number
    summary: string
  }
}

const props = defineProps<{
  trace: TraceItem
  index: number
  /** 移动端紧凑模式：减小 padding + 36px tap target */
  compact?: boolean
}>()

const expanded = ref(false)
const copied = ref(false)

const detailId = computed(() => `tti-detail-${props.index}-${(props.trace.name || 'x').replace(/\W/g, '_')}`)
const hasOutput = computed(() => Boolean(props.trace.tool_output))
const copyLabel = computed(() => (copied.value ? '已复制到剪贴板' : '复制 JSON 到剪贴板'))

const prettyJson = computed(() => {
  if (!props.trace.tool_output) return ''
  try {
    return JSON.stringify(props.trace.tool_output, null, 2)
  } catch {
    return String(props.trace.tool_output)
  }
})

function toggle() {
  expanded.value = !expanded.value
}

async function copyOutput() {
  if (!props.trace.tool_output) return
  try {
    const text = JSON.stringify(props.trace.tool_output, null, 2)
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text)
    } else {
      // 降级：临时 textarea + execCommand
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch (e) {
    // 复制失败也提供可见反馈（不抛错避免打断 UI）
    console.error('[ToolTraceItem] copy failed', e)
  }
}
</script>

<style scoped>
.tti-thinking {
  font-size: 12px;
  color: var(--color-text-secondary);
  padding: 2px 0;
}
.tti-thinking.stagger-1 { animation: var(--animation-fadeSlideUp) 0.2s ease-out 0.0s both; }
.tti-thinking.stagger-2 { animation: var(--animation-fadeSlideUp) 0.2s ease-out 0.05s both; }
.tti-thinking.stagger-3 { animation: var(--animation-fadeSlideUp) 0.2s ease-out 0.10s both; }
.tti-thinking.stagger-4 { animation: var(--animation-fadeSlideUp) 0.2s ease-out 0.15s both; }
.tti-thinking.stagger-5 { animation: var(--animation-fadeSlideUp) 0.2s ease-out 0.20s both; }
.tti-thinking.stagger-6 { animation: var(--animation-fadeSlideUp) 0.2s ease-out 0.25s both; }

.tti-tool {
  border-radius: var(--radius-sm, 4px);
  font-size: 12px;
  color: var(--color-text-regular, #606266);
}
.tti-tool.running { color: var(--color-primary, #FF7A5C); }
.tti-tool.tti-expanded {
  background: var(--color-bg-warm, #FFF8F5);
  border-left: 2px solid var(--color-primary, #FF7A5C);
  padding: 4px 0 4px 8px;
  margin: 2px 0;
}
.tti-tool.stagger-1 { animation: var(--animation-fadeSlideUp) 0.2s ease-out 0.0s both; }
.tti-tool.stagger-2 { animation: var(--animation-fadeSlideUp) 0.2s ease-out 0.05s both; }
.tti-tool.stagger-3 { animation: var(--animation-fadeSlideUp) 0.2s ease-out 0.10s both; }
.tti-tool.stagger-4 { animation: var(--animation-fadeSlideUp) 0.2s ease-out 0.15s both; }
.tti-tool.stagger-5 { animation: var(--animation-fadeSlideUp) 0.2s ease-out 0.20s both; }
.tti-tool.stagger-6 { animation: var(--animation-fadeSlideUp) 0.2s ease-out 0.25s both; }

.tti-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 6px;
  min-height: 44px; /* 无障碍 tap target */
  cursor: pointer;
  user-select: none;
  outline: none;
  border-radius: var(--radius-sm, 4px);
  transition: background 150ms ease;
}
.tti-row:hover { background: var(--color-primary-bg, #FFF0ED); }
.tti-row:focus-visible {
  box-shadow: 0 0 0 2px var(--color-primary, #FF7A5C);
}
.tti-tool.compact .tti-row {
  min-height: 36px;
  padding: 6px 4px;
}

.tti-spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid var(--color-primary, #FF7A5C);
  border-top-color: transparent;
  border-radius: 50%;
  animation: var(--animation-spin, spin 0.8s linear infinite);
}
.tti-check { font-size: 12px; }
.tti-name { font-weight: 500; }
.tti-tick { color: var(--color-success, #67C23A); }
.tti-duration { color: var(--color-text-secondary, #909399); font-size: 11px; margin-left: auto; }
.tti-toggle { color: var(--color-text-secondary, #909399); font-size: 11px; min-width: 12px; text-align: right; }

.tti-preview {
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, monospace);
  font-size: 11px;
  color: var(--color-text-secondary, #909399);
  padding: 0 6px 4px 22px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tti-compression {
  font-size: 11px;
  color: var(--color-warning, #E6A23C);
  padding: 2px 6px 2px 22px;
  background: var(--color-warning-bg, #FDF6EC);
  border-radius: var(--radius-sm, 4px);
  margin: 2px 6px;
  display: inline-block;
}

.tti-detail {
  margin: 4px 6px 6px 22px;
  padding: 8px;
  background: var(--color-bg-warm, #FFF8F5);
  border: 1px solid var(--color-border-light, #F0F0F0);
  border-radius: var(--radius-sm, 4px);
}
.tti-detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.tti-detail-label {
  font-size: 11px;
  color: var(--color-text-secondary, #909399);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.tti-copy {
  background: var(--color-primary-bg, #FFF0ED);
  border: 1px solid var(--color-primary-border, rgba(255, 122, 92, 0.2));
  color: var(--color-primary, #FF7A5C);
  border-radius: var(--radius-sm, 4px);
  padding: 2px 8px;
  font-size: 11px;
  cursor: pointer;
  min-height: 24px;
  transition: background 150ms ease;
}
.tti-copy:hover { background: var(--color-primary, #FF7A5C); color: #fff; }
.tti-copy:focus-visible { outline: 2px solid var(--color-primary, #FF7A5C); outline-offset: 1px; }

.tti-json {
  margin: 0;
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, monospace);
  font-size: 11px;
  line-height: 1.5;
  color: var(--color-text-regular, #606266);
  max-height: 320px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.tti-empty {
  font-size: 11px;
  color: var(--color-text-secondary, #909399);
  font-style: italic;
  padding: 4px 0;
}

/* 展开/收起过渡 */
.tti-detail-enter-active {
  transition: opacity var(--duration-fast, 150ms) ease, transform var(--duration-fast, 150ms) ease;
}
.tti-detail-leave-active {
  transition: opacity var(--duration-fast, 150ms) ease, transform var(--duration-fast, 150ms) ease;
}
.tti-detail-enter-from { opacity: 0; transform: translateY(-4px); }
.tti-detail-leave-to { opacity: 0; transform: translateY(-4px); }

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 尊重 prefers-reduced-motion */
@media (prefers-reduced-motion: reduce) {
  .tti-spinner,
  .tti-row,
  .tti-detail-enter-active,
  .tti-detail-leave-active {
    animation: none !important;
    transition: none !important;
  }
}
</style>
