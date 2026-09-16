<script setup lang="ts">
// 设置页工作区区块 — 当前工作区/未设置态 + 目录选择 + 最近 20 条审计记录（工单 C-1 §4）
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { WorkspaceAuditEntry } from '@shared/types'

const SUGGESTED = 'E:\\microbubble-agent\\desktop-conversion'

const root = ref<string | null>(null)
const audits = ref<WorkspaceAuditEntry[]>([])
const loading = ref(false)

async function refresh(): Promise<void> {
  root.value = (await window.api.workspace.get()).root
  audits.value = await window.api.workspace.auditList(20)
}

async function onPick(): Promise<void> {
  loading.value = true
  try {
    const picked = await window.api.workspace.set()
    if (picked) ElMessage.success(`工作区已设置：${picked}`)
    await refresh()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '设置工作区失败')
  } finally {
    loading.value = false
  }
}

async function onClear(): Promise<void> {
  try {
    await ElMessageBox.confirm('清除后 Agent 将回到纯对话模式（不会删除工作区目录内的任何文件）。确定清除？', '清除工作区', {
      type: 'warning',
      confirmButtonText: '清除',
      cancelButtonText: '取消'
    })
  } catch {
    return // 取消
  }
  try {
    await window.api.workspace.clear()
    ElMessage.success('工作区已清除')
    await refresh()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '清除失败')
  }
}

function fmtTime(ts: number): string {
  return new Date(ts).toLocaleString('zh-CN')
}

onMounted(() => {
  refresh().catch(() => /* 主进程异常时保持初始态 */ undefined)
})
</script>

<template>
  <section class="card block">
    <h2>工作区</h2>

    <div class="ws-head">
      <div class="ws-state">
        <template v-if="root">
          <span class="state-label">当前工作区</span>
          <span class="mono ws-path">{{ root }}</span>
        </template>
        <template v-else>
          <span class="state-label">未设置</span>
          <span class="ws-hint-inline">Agent 尚不可用 — 选择一个目录作为工作区后即可启用文件工具。</span>
        </template>
      </div>
      <div class="ws-actions">
        <button v-if="root" class="clear-btn" data-testid="btn-clear-ws" @click="onClear">清除</button>
        <button class="pick-btn" :disabled="loading" @click="onPick">{{ loading ? '选择中…' : '选择目录' }}</button>
      </div>
    </div>

    <p class="hint">建议将工作区设为 <span class="mono">{{ SUGGESTED }}</span>（GitHub 仓库根）。Agent 仅在该目录内读写；.git/ 为禁区，Agent 也不会执行任何 git 命令。</p>

    <div class="audit">
      <h3>最近审计（{{ audits.length }} 条）</h3>
      <div v-if="audits.length" class="audit-list">
        <div v-for="a in audits" :key="a.id" class="audit-row">
          <span class="tool-name">{{ a.tool }}</span>
          <span class="tool-ok" :class="a.ok ? 'is-ok' : 'is-fail'">{{ a.ok ? '✓' : '✗' }}</span>
          <span class="tool-summary" :title="a.inputSummary">{{ a.inputSummary }}</span>
          <span class="tool-time">{{ fmtTime(a.createdAt) }}</span>
        </div>
      </div>
      <p v-else class="hint">暂无记录 — Agent 调用文件工具后，这里会留下每次操作的审计。</p>
    </div>
  </section>
</template>

<style scoped>
.block {
  padding: var(--space-6);
}
.block h2 {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  margin-bottom: var(--space-4);
}
.ws-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}
.ws-state {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.state-label {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
}
.ws-path {
  word-break: break-all;
}
.ws-hint-inline {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}
.ws-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}
.clear-btn {
  padding: 8px 16px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.clear-btn:hover {
  border-color: var(--color-danger, #d64545);
  color: var(--color-danger, #d64545);
}
.pick-btn {
  flex-shrink: 0;
  padding: 8px 20px;
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-primary);
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.pick-btn:disabled {
  opacity: 0.6;
  cursor: default;
}
.hint {
  margin-top: var(--space-4);
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  line-height: 1.7;
}
.mono {
  font-family: var(--font-family-mono);
  font-size: var(--font-size-xs);
}
.audit {
  margin-top: var(--space-5);
}
.audit h3 {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  margin-bottom: var(--space-2);
  color: var(--color-text-regular);
}
.audit-list {
  display: flex;
  flex-direction: column;
}
.audit-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) 0;
  border-bottom: 1px dashed var(--color-border-light);
  font-size: var(--font-size-xs);
}
.tool-name {
  flex-shrink: 0;
  min-width: 72px;
  font-family: var(--font-family-mono);
  color: var(--color-text-regular);
}
.tool-ok {
  flex-shrink: 0;
  width: 18px;
  text-align: center;
}
.tool-ok.is-ok {
  color: var(--color-success, #22a06b);
}
.tool-ok.is-fail {
  color: var(--color-danger, #d64545);
}
.tool-summary {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-text-secondary);
}
.tool-time {
  flex-shrink: 0;
  color: var(--color-text-secondary);
}
</style>
