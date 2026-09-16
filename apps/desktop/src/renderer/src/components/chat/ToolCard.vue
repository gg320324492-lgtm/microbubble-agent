<script setup lang="ts">
// 工具卡片 — 工具名 + 输入摘要 + 状态流转 + 可展开详情（工单 C-3）：
// awaiting_confirm 显示行级 diff（新增绿/删除红）+「批准 / 拒绝」（仅 live 卡可操作，
// 持久化还原的未决卡降级为「已取消/未完成」）；rejected 标识；write_file 成功且
// 有备份时提供「回滚此写入」。
import { computed, ref } from 'vue'
import type { FileDiff, ToolCallRecord } from '@shared/types'

const props = defineProps<{ call: ToolCallRecord; live?: boolean; interactive?: boolean }>()

const emit = defineEmits<{
  (e: 'resolve', call: ToolCallRecord, approve: boolean): void
  (e: 'rollback'): void
}>()

const expanded = ref(false)

const isAwaiting = computed(() => props.call.status === 'awaiting_confirm')
const isRejected = computed(() => props.call.status === 'rejected')

const statusLabel = computed(() => {
  switch (props.call.status) {
    case 'running':
      return '运行中'
    case 'ok':
      return '成功'
    case 'error':
      return '失败'
    case 'awaiting_confirm':
      // 持久化还原的未决确认已不可操作 — 降级为已取消展示
      return props.live ? '待确认' : '已取消/未完成'
    case 'rejected':
      return '已拒绝'
  }
})

const inputSummary = computed<string>(() => {
  let text: string
  try {
    text = JSON.stringify(props.call.input) ?? ''
  } catch {
    text = String(props.call.input)
  }
  return text.length > 80 ? `${text.slice(0, 80)}…` : text
})

const diff = computed<FileDiff | null>(() => {
  const d = props.call.data as { diff?: FileDiff } | undefined
  return d && d.diff && Array.isArray(d.diff.lines) ? d.diff : null
})

const writeData = computed<{ backupPath?: string; rolledBack?: boolean } | null>(() => {
  const d = props.call.data as { backupPath?: string; rolledBack?: boolean } | undefined
  return d && d.backupPath ? d : null
})

const showDiff = computed(() => isAwaiting.value || expanded.value || isRejected.value)

const dataText = computed<string>(() => {
  if (props.call.data === undefined) return ''
  try {
    return JSON.stringify(props.call.data, null, 2)
  } catch {
    return String(props.call.data)
  }
})
</script>

<template>
  <div class="tool-card" :class="[`is-${call.status}`]" data-testid="tool-card">
    <button class="tool-head" :aria-expanded="expanded || isAwaiting" @click="expanded = !expanded">
      <span class="tool-status" data-testid="tool-status">
        <span v-if="call.status === 'running'" class="spin" aria-hidden="true">⟳</span>
        <span v-else-if="call.status === 'ok'" class="ok" aria-hidden="true">✓</span>
        <span v-else-if="call.status === 'error'" class="fail" aria-hidden="true">✗</span>
        <span v-else-if="isAwaiting && live" class="confirm-icon" aria-hidden="true">✎</span>
        <span v-else-if="isAwaiting" class="fail" aria-hidden="true">⊘</span>
        <span v-else class="rejected-icon" aria-hidden="true">⊘</span>
        {{ statusLabel }}
      </span>
      <span class="tool-name">{{ call.name }}</span>
      <span class="tool-input">{{ inputSummary }}</span>
      <span class="tool-chevron" aria-hidden="true">{{ expanded ? '▾' : '▸' }}</span>
    </button>

    <!-- 确认面板：diff + 批准/拒绝（仅进行中的 live 卡可操作） -->
    <div v-if="isAwaiting && showDiff" class="confirm-panel" data-testid="confirm-panel">
      <div v-if="diff" class="diff" data-testid="diff">
        <div v-if="diff.kind === 'create'" class="diff-note">新建文件 · 内容预览{{ diff.truncated ? '（超 200 行已截断）' : '' }}</div>
        <div v-if="diff.truncated && diff.kind !== 'create'" class="diff-note">差异超 200 行，仅显示前 200 行</div>
        <div v-for="(line, i) in diff.lines" :key="i" class="diff-line" :class="`diff-${line.kind}`">{{ line.text }}</div>
      </div>
      <div v-if="live" class="confirm-actions">
        <button class="btn-approve" data-testid="btn-approve" @click.stop="emit('resolve', call, true)">批准</button>
        <button class="btn-reject" data-testid="btn-reject" @click.stop="emit('resolve', call, false)">拒绝</button>
      </div>
    </div>

    <!-- 拒绝态标识 -->
    <div v-if="isRejected" class="rejected-note">用户拒绝执行，未改动工作区</div>

    <!-- 回滚（write_file 成功且有备份；已回滚/新建文件不显示） -->
    <div v-if="call.status === 'ok' && interactive && writeData && !writeData.rolledBack" class="rollback-bar">
      <button class="btn-rollback" data-testid="btn-rollback" @click.stop="emit('rollback')">↩ 回滚此写入</button>
    </div>
    <div v-if="call.status === 'ok' && writeData?.rolledBack" class="rolledback-note">已回滚（原内容已恢复）</div>

    <div v-if="expanded && !isAwaiting" class="tool-detail" data-testid="tool-detail">
      <div class="detail-line"><span class="detail-key">结果</span><span>{{ call.summary }}</span></div>
      <pre v-if="dataText" class="detail-data">{{ dataText }}</pre>
    </div>
  </div>
</template>

<style scoped>
.tool-card {
  margin: var(--space-2) 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-secondary);
  overflow: hidden;
  font-size: var(--font-size-xs);
}
.tool-card.is-running {
  border-color: rgba(var(--color-primary-rgb), 0.55);
}
.tool-card.is-error,
.tool-card.is-rejected {
  border-color: rgba(214, 69, 69, 0.45);
}
.tool-card.is-awaiting_confirm {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(var(--color-primary-rgb), 0.12);
}
.tool-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-2) var(--space-3);
  border: none;
  background: transparent;
  cursor: pointer;
  text-align: left;
}
.tool-status {
  flex-shrink: 0;
  min-width: 52px;
  color: var(--color-text-secondary);
}
.tool-status .spin {
  display: inline-block;
  animation: toolSpin 1s linear infinite;
  color: var(--color-primary);
}
.tool-status .ok {
  color: var(--color-success, #22a06b);
}
.tool-status .fail,
.rejected-icon {
  color: var(--color-danger, #d64545);
}
.confirm-icon {
  color: var(--color-primary);
}
@keyframes toolSpin {
  to {
    transform: rotate(360deg);
  }
}
.tool-name {
  flex-shrink: 0;
  font-family: var(--font-family-mono);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-regular);
}
.tool-input {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-family-mono);
  color: var(--color-text-secondary);
}
.tool-chevron {
  flex-shrink: 0;
  color: var(--color-text-placeholder);
}
/* 确认面板与 diff */
.confirm-panel {
  border-top: 1px dashed var(--color-border-light);
}
.diff {
  max-height: 240px;
  overflow: auto;
  font-family: var(--font-family-mono);
  font-size: 11px;
  line-height: 1.6;
}
.diff-line {
  padding: 0 var(--space-3);
  white-space: pre-wrap;
  word-break: break-all;
}
.diff-add {
  background: rgba(34, 160, 107, 0.16);
  color: #17694a;
}
.diff-del {
  background: rgba(214, 69, 69, 0.14);
  color: #9c3535;
  text-decoration: line-through;
}
.diff-ctx {
  color: var(--color-text-secondary);
}
.diff-note {
  padding: var(--space-1) var(--space-3);
  color: var(--color-text-secondary);
}
.confirm-actions {
  display: flex;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3) var(--space-3);
}
.btn-approve,
.btn-reject {
  padding: 5px 16px;
  border-radius: var(--radius-md);
  font-size: var(--font-size-xs);
  cursor: pointer;
}
.btn-approve {
  border: none;
  background: var(--color-success, #22a06b);
  color: #fff;
}
.btn-reject {
  border: 1px solid var(--color-danger, #d64545);
  background: transparent;
  color: var(--color-danger, #d64545);
}
.rejected-note,
.rolledback-note {
  padding: 0 var(--space-3) var(--space-2);
  color: var(--color-text-secondary);
}
.rollback-bar {
  padding: 0 var(--space-3) var(--space-2);
}
.btn-rollback {
  padding: 4px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg-card);
  color: var(--color-text-regular);
  font-size: var(--font-size-xs);
  cursor: pointer;
}
.btn-rollback:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.tool-detail {
  padding: var(--space-2) var(--space-3) var(--space-3);
  border-top: 1px dashed var(--color-border-light);
}
.detail-line {
  display: flex;
  gap: var(--space-2);
  color: var(--color-text-regular);
  line-height: 1.6;
}
.detail-key {
  flex-shrink: 0;
  color: var(--color-text-secondary);
}
.detail-data {
  margin: var(--space-2) 0 0;
  max-height: 220px;
  overflow: auto;
  padding: var(--space-2);
  border-radius: var(--radius-sm);
  background: var(--wb-panel-950, #10241d);
  color: var(--wb-panel-text, #d7e7df);
  font-family: var(--font-family-mono);
  font-size: 11px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
